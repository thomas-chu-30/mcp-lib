"""在 Redmine 建立新 issue。"""

from __future__ import annotations

from typing import Any

import httpx

from app import mcp
from config import (
    DEFAULT_ASSIGNEE_NAME,
    RedmineConfig,
    RedmineConfigError,
    build_client,
)
from formatters import format_issue
from http_client import request_with_retry
from users import find_user_by_name


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

        with build_client(config) as client:
            assignee_id: int | None = config.self_id
            if assignee_id is None:
                assignee_name = config.self_name or DEFAULT_ASSIGNEE_NAME
                assignee = find_user_by_name(client, assignee_name, limit=1)
                if assignee and isinstance(assignee.get("id"), int):
                    assignee_id = assignee["id"]
            if assignee_id is not None:
                issue_body["assigned_to_id"] = assignee_id

            response = request_with_retry(
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
            formatted = format_issue(issue)
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
