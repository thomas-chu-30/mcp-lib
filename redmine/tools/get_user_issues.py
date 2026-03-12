"""取得指派給指定使用者的 Redmine 任務列表。"""

from __future__ import annotations

from typing import Any

import httpx

from app import mcp
from config import RedmineConfig, RedmineConfigError, build_client
from formatters import format_issue_list
from http_client import request_with_retry
from users import find_user_by_name


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
        with build_client(config) as client:
            user = find_user_by_name(client, assignee_name.strip(), limit=1)
            if not user:
                return f"在 Redmine 找不到名稱包含「{assignee_name}」的使用者。"

            user_id = user.get("id")
            user_name = user.get("name") or assignee_name
            if not isinstance(user_id, int):
                return f"Redmine 回傳的使用者資料異常，無法取得使用者 ID（name={user_name}）。"

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

                response = request_with_retry(
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
            body = format_issue_list(issues_list, config.base_url)
            return f"{header}{body}"
    except RedmineConfigError as e:
        return str(e)
    except httpx.HTTPError as e:
        return f"請求 Redmine API 時發生錯誤：{e!s}"
    except ValueError as e:
        return f"解析 Redmine API 回應時發生錯誤：{e!s}"
    except Exception as e:
        return f"發生未預期的錯誤：{e!s}"
