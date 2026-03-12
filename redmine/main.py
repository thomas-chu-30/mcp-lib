#!/usr/bin/env python3
"""
Redmine MCP Server

透過 Redmine REST API 讀取、建立與更新 issue（task）。

功能聚焦在「自己的任務」：
- 讀取目前指派給自己的 issue
- 建立新 issue
- 更新既有 issue 的狀態與備註（notes）

Redmine 官方 REST 文件可參考：
- `/issues.json`
- `/projects.json`
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

REQUEST_TIMEOUT = 15.0
MAX_RETRIES = 3
BACKOFF_BASE = 0.5

ENV_BASE_URL = "REDMINE_BASE_URL"
ENV_API_TOKEN = "REDMINE_API_TOKEN"
ENV_PROJECT_IDS = "REDMINE_PROJECT_IDS"
ENV_SELF_NAME = "REDMINE_SELF_NAME"


mcp = FastMCP("redmine")


class RedmineConfigError(RuntimeError):
    """Redmine MCP 的設定錯誤（缺少或錯誤的環境變數）。"""


@dataclass(slots=True)
class RedmineConfig:
    base_url: str
    api_token: str
    project_ids: list[str]
    self_name: str | None

    @classmethod
    def from_env(cls) -> "RedmineConfig":
        base_url = os.environ.get(ENV_BASE_URL, "").strip().rstrip("/")
        api_token = os.environ.get(ENV_API_TOKEN, "").strip()
        raw_project_ids = os.environ.get(ENV_PROJECT_IDS, "")
        self_name = os.environ.get(ENV_SELF_NAME, "").strip() or None

        project_ids: list[str] = []
        if raw_project_ids:
            # 支援逗號或分號分隔，例如 "ss,core;infra"
            for part in raw_project_ids.replace(";", ",").split(","):
                ident = part.strip()
                if ident:
                    project_ids.append(ident)

        if not base_url:
            raise RedmineConfigError(
                f"環境變數 {ENV_BASE_URL} 未設定，請在 ~/.cursor/mcp.json 的 redmine 伺服器下加入 env 設定。"
            )
        if not api_token:
            raise RedmineConfigError(
                f"環境變數 {ENV_API_TOKEN} 未設定，請在 ~/.cursor/mcp.json 的 redmine 伺服器下加入 env 設定。"
            )

        return cls(
            base_url=base_url,
            api_token=api_token,
            project_ids=project_ids,
            self_name=self_name,
        )


def _build_client(config: RedmineConfig) -> httpx.Client:
    headers = {
        "X-Redmine-API-Key": config.api_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return httpx.Client(
        base_url=config.base_url,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )


def _request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    expected_status: int | tuple[int, ...] = (200, 201),
) -> httpx.Response:
    """
    封裝 httpx 請求，提供簡單的重試與錯誤處理。

    - 對 5xx 或連線錯誤進行最多 MAX_RETRIES 次重試（指數退避）
    - 4xx 直接拋錯
    """
    if isinstance(expected_status, int):
        expected = (expected_status,)
    else:
        expected = expected_status

    attempt = 0
    last_exc: Exception | None = None

    while attempt <= MAX_RETRIES:
        try:
            response = client.request(method, url, params=params, json=json_body)
            if response.status_code in expected:
                return response
            if 400 <= response.status_code < 500:
                # 使用者錯誤不重試
                response.raise_for_status()
            # 5xx → 落到下面重試
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            logger.warning("Redmine API 請求失敗（第 %d 次）：%s", attempt + 1, exc)

        attempt += 1
        if attempt > MAX_RETRIES:
            break
        sleep_for = BACKOFF_BASE * (2 ** (attempt - 1))
        time.sleep(sleep_for)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Redmine API 多次重試後仍然失敗。")


def _format_issue(issue: dict[str, Any]) -> str:
    """將單一 Redmine issue 格式化成易讀 Markdown。"""
    issue_id = issue.get("id")
    subject = issue.get("subject") or ""
    status = (issue.get("status") or {}).get("name") or ""
    tracker = (issue.get("tracker") or {}).get("name") or ""
    project = (issue.get("project") or {}).get("name") or ""
    assigned_to = (issue.get("assigned_to") or {}).get("name") or ""
    priority = (issue.get("priority") or {}).get("name") or ""
    author = (issue.get("author") or {}).get("name") or ""
    description = (issue.get("description") or "").strip()

    lines: list[str] = [
        f"## #{issue_id} - {subject}",
        "",
        f"- **專案**：{project}",
        f"- **Tracker**：{tracker}",
        f"- **狀態**：{status}",
        f"- **優先權**：{priority}",
        f"- **指派給**：{assigned_to or '-'}",
        f"- **建立者**：{author}",
        "",
    ]
    if description:
        lines.append("**描述**：")
        lines.append("")
        lines.append(description)
        lines.append("")
    return "\n".join(lines)


def _format_issue_list(issues: list[dict[str, Any]], base_url: str) -> str:
    """將多個 issue 列表格式化成 Markdown。"""
    if not issues:
        return "目前沒有符合條件的 Redmine 任務。"

    lines: list[str] = [
        "# Redmine 任務列表",
        "",
        f"來源：{base_url}",
        "",
    ]
    for issue in issues:
        issue_id = issue.get("id")
        subject = issue.get("subject") or ""
        status = (issue.get("status") or {}).get("name") or ""
        project = (issue.get("project") or {}).get("name") or ""
        assigned_to = (issue.get("assigned_to") or {}).get("name") or ""
        url = f"{base_url}/issues/{issue_id}"

        lines.append(f"## #{issue_id} - {subject}")
        lines.append("")
        lines.append(f"- **專案**：{project}")
        lines.append(f"- **狀態**：{status}")
        lines.append(f"- **指派給**：{assigned_to or '-'}")
        lines.append(f"- **連結**：{url}")
        lines.append("")

    return "\n".join(lines).strip()


def _find_user_by_name(
    client: httpx.Client,
    name: str,
    *,
    limit: int = 1,
) -> dict[str, Any] | None:
    """
    透過 Redmine `/users.json` 以名稱模糊搜尋使用者，回傳第一筆結果。
    若查無資料則回傳 None。
    """
    params: dict[str, Any] = {
        "name": name,
        "limit": max(1, min(100, limit)),
    }
    response = _request_with_retry(
        client,
        "GET",
        "/users.json",
        params=params,
        json_body=None,
        expected_status=200,
    )
    data: dict[str, Any] = response.json()
    users = data.get("users") or []
    if not isinstance(users, list) or not users:
        return None
    user = users[0]
    return user if isinstance(user, dict) else None


@mcp.tool()
def get_my_issues(limit: int = 20, include_closed: bool = False) -> str:
    """
    取得指派給目前 API token 使用者的 Redmine 任務列表。

    - limit：最多回傳幾筆（預設 20，1～100）
    - include_closed：是否包含已關閉的任務（預設 False，只顯示未關閉）
    """
    try:
        limit_normalized = max(1, min(100, limit))
        config = RedmineConfig.from_env()
        with _build_client(config) as client:
            # 支援多個 project_id：如果有設定 ENV_PROJECT_IDS，就逐一查詢並合併
            all_issues: dict[int, dict[str, Any]] = {}
            project_ids = config.project_ids or [None]

            for project_id in project_ids:
                params: dict[str, Any] = {
                    "assigned_to_id": "me",
                    "limit": limit_normalized,
                }
                if include_closed:
                    params["status_id"] = "*"
                else:
                    # 只看未結案
                    params["status_id"] = "open"
                if project_id is not None:
                    params["project_id"] = project_id

                response = _request_with_retry(
                    client,
                    "GET",
                    "/issues.json",
                    params=params,
                    json_body=None,
                    expected_status=200,
                )
                data: dict[str, Any] = response.json()
                issues_chunk = data.get("issues") or []
                if not isinstance(issues_chunk, list):
                    return "Redmine API 回傳格式異常：`issues` 不是列表。"

                for issue in issues_chunk:
                    if isinstance(issue, dict):
                        issue_id = issue.get("id")
                        if isinstance(issue_id, int):
                            all_issues[issue_id] = issue

            issues_list = list(all_issues.values())

            header_lines: list[str] = []
            who = config.self_name or "API Token 對應帳號（assigned_to_id=me）"
            header_lines.append(f"指派對象：{who}")
            if config.project_ids:
                header_lines.append(f"篩選專案：{', '.join(config.project_ids)}")

            header = "\n".join(header_lines) + "\n\n" if header_lines else ""
            body = _format_issue_list(issues_list, config.base_url)
            return f"{header}{body}"
    except RedmineConfigError as e:
        return str(e)
    except httpx.HTTPError as e:
        return f"請求 Redmine API 時發生錯誤：{e!s}"
    except ValueError as e:
        return f"解析 Redmine API 回應時發生錯誤：{e!s}"
    except Exception as e:
        return f"發生未預期的錯誤：{e!s}"


@mcp.tool()
def get_user_issues(
    assignee_name: str,
    limit: int = 20,
    include_closed: bool = False,
) -> str:
    """
    取得指派給指定使用者的 Redmine 任務列表（透過名稱模糊搜尋）。

    - assignee_name：使用者名稱或其一部分（例如 "thomas"）
    - limit：最多回傳幾筆（預設 20，1～100）
    - include_closed：是否包含已關閉的任務（預設 False，只顯示未關閉）
    """
    if not assignee_name.strip():
        return "assignee_name 不可為空。"

    try:
        limit_normalized = max(1, min(100, limit))
        config = RedmineConfig.from_env()
        with _build_client(config) as client:
            user = _find_user_by_name(client, assignee_name.strip(), limit=1)
            if not user:
                return f"在 Redmine 找不到名稱包含「{assignee_name}」的使用者。"

            user_id = user.get("id")
            user_name = user.get("name") or assignee_name
            if not isinstance(user_id, int):
                return f"Redmine 回傳的使用者資料異常，無法取得使用者 ID（name={user_name}）。"

            # 同樣支援多個 project_id
            all_issues: dict[int, dict[str, Any]] = {}
            project_ids = config.project_ids or [None]

            for project_id in project_ids:
                params: dict[str, Any] = {
                    "assigned_to_id": user_id,
                    "limit": limit_normalized,
                }
                if include_closed:
                    params["status_id"] = "*"
                else:
                    params["status_id"] = "open"
                if project_id is not None:
                    params["project_id"] = project_id

                response = _request_with_retry(
                    client,
                    "GET",
                    "/issues.json",
                    params=params,
                    json_body=None,
                    expected_status=200,
                )
                data: dict[str, Any] = response.json()
                issues_chunk = data.get("issues") or []
                if not isinstance(issues_chunk, list):
                    return "Redmine API 回傳格式異常：`issues` 不是列表。"

                for issue in issues_chunk:
                    if isinstance(issue, dict):
                        issue_id = issue.get("id")
                        if isinstance(issue_id, int):
                            all_issues[issue_id] = issue

            issues_list = list(all_issues.values())

            header_lines: list[str] = [
                f"指派對象：{user_name}（ID: {user_id}）",
            ]
            if config.project_ids:
                header_lines.append(f"篩選專案：{', '.join(config.project_ids)}")

            header = "\n".join(header_lines) + "\n\n"
            body = _format_issue_list(issues_list, config.base_url)
            return f"{header}{body}"
    except RedmineConfigError as e:
        return str(e)
    except httpx.HTTPError as e:
        return f"請求 Redmine API 時發生錯誤：{e!s}"
    except ValueError as e:
        return f"解析 Redmine API 回應時發生錯誤：{e!s}"
    except Exception as e:
        return f"發生未預期的錯誤：{e!s}"


@mcp.tool()
def create_issue(
    project_identifier: str,
    subject: str,
    description: str | None = None,
    tracker_id: int = 2,
    status_id: int = 1,
    priority_id: int | None = None,
) -> str:
    """
    在 Redmine 建立一個新的 issue（task）。
    請求格式與 Redmine REST API 一致：POST /issues.json，body 為 {"issue": {...}}。

    參數：
    - project_identifier：專案識別碼（如 `ss`），對應 Redmine 的 project identifier
    - subject：標題
    - description：描述（可選）
    - tracker_id：tracker ID（預設 2，常見為 Feature；1: Bug, 2: Feature, 3: Support）
    - status_id：初始狀態 ID（預設 1，常見為 New/新建）
    - priority_id：優先權 ID（可選）
    """
    if not project_identifier.strip():
        return "project_identifier 不可為空。"
    if not subject.strip():
        return "subject 不可為空。"

    try:
        config = RedmineConfig.from_env()
        # 與 Redmine REST API 一致：僅包含 issue 物件，必要欄位 + 選填欄位
        issue_body: dict[str, Any] = {
            "project_id": project_identifier.strip(),
            "subject": subject.strip(),
            "tracker_id": tracker_id,
            "status_id": status_id,
        }
        if description is not None and description.strip():
            issue_body["description"] = description.strip()
        if priority_id is not None:
            issue_body["priority_id"] = priority_id

        payload: dict[str, Any] = {"issue": issue_body}

        with _build_client(config) as client:
            response = _request_with_retry(
                client,
                "POST",
                "/issues.json",
                json_body=payload,
                expected_status=201,
            )
            data: dict[str, Any] = response.json()
            issue = data.get("issue")
            if not isinstance(issue, dict):
                return "Redmine API 回傳格式異常：`issue` 欄位不存在或不是物件。"
            formatted = _format_issue(issue)
            issue_id = issue.get("id")
            url = f"{config.base_url}/issues/{issue_id}"
            return f"# 建立 Redmine 任務成功\n\n{formatted}\n\n**連結**：{url}"
    except RedmineConfigError as e:
        return str(e)
    except httpx.HTTPError as e:
        return f"請求 Redmine API 時發生錯誤：{e!s}"
    except ValueError as e:
        return f"解析 Redmine API 回應時發生錯誤：{e!s}"
    except Exception as e:
        return f"發生未預期的錯誤：{e!s}"


@mcp.tool()
def update_issue(
    issue_id: int,
    status_id: int | None = None,
    notes: str | None = None,
    subject: str | None = None,
    priority_id: int | None = None,
) -> str:
    """
    更新既有的 Redmine issue（task），常見用法：
    - 改變狀態（例如進行中 / 已完成）
    - 加上備註（notes）

    參數：
    - issue_id：要更新的 issue 編號（數字）
    - status_id：新的狀態 ID（例如 2: In Progress, 3: Resolved, ...）
    - notes：備註（會加到 issue 的 notes）
    - subject：更新後的標題
    - priority_id：新的優先權 ID
    """
    if issue_id <= 0:
        return "issue_id 必須是正整數。"
    if all(v is None for v in (status_id, notes, subject, priority_id)):
        return "至少需要提供一個要更新的欄位（status_id, notes, subject, priority_id）。"

    try:
        config = RedmineConfig.from_env()
        payload: dict[str, Any] = {"issue": {}}
        issue_body = payload["issue"]

        if status_id is not None:
            issue_body["status_id"] = status_id
        if notes:
            issue_body["notes"] = notes.strip()
        if subject:
            issue_body["subject"] = subject.strip()
        if priority_id is not None:
            issue_body["priority_id"] = priority_id

        with _build_client(config) as client:
            _request_with_retry(
                client,
                "PUT",
                f"/issues/{issue_id}.json",
                json_body=payload,
                expected_status=(200, 204),
            )

            # Redmine 對 update 多半不會回傳完整 issue，本工具只回傳簡要說明與連結
            url = f"{config.base_url}/issues/{issue_id}"
            summary_parts: list[str] = []
            if status_id is not None:
                summary_parts.append(f"狀態 → {status_id}")
            if subject:
                summary_parts.append("標題已更新")
            if priority_id is not None:
                summary_parts.append(f"優先權 → {priority_id}")
            if notes:
                summary_parts.append("新增了一則備註")

            summary = "；".join(summary_parts) if summary_parts else "欄位已更新"
            return f"# 更新 Redmine 任務成功\n\n- **Issue ID**：{issue_id}\n- **更新內容**：{summary}\n- **連結**：{url}"
    except RedmineConfigError as e:
        return str(e)
    except httpx.HTTPError as e:
        return f"請求 Redmine API 時發生錯誤：{e!s}"
    except ValueError as e:
        return f"解析 Redmine API 回應時發生錯誤：{e!s}"
    except Exception as e:
        return f"發生未預期的錯誤：{e!s}"


if __name__ == "__main__":
    mcp.run()

