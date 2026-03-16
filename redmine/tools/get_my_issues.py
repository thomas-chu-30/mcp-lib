"""取得指派給自己的 Redmine 任務列表。"""

from __future__ import annotations

from typing import Any

import httpx

from app import mcp
from config import RedmineConfig, RedmineConfigError, build_client
from formatters import format_issue_list
from http_client import request_with_retry


@mcp.tool()
def get_my_issues(
    limit: int = 20,
    include_closed: bool = False,
    updated_from: str | None = None,
    updated_to: str | None = None,
) -> str:
    """
    取得指派給目前 API token 使用者的 Redmine 任務列表。

    - limit：最多回傳幾筆（預設 20，1～100）
    - include_closed：是否包含已關閉的任務（預設 False，只顯示未關閉）
    - updated_from：只顯示「更新時間」大於等於此日期（YYYY-MM-DD）
    - updated_to：只顯示「更新時間」小於等於此日期（YYYY-MM-DD）

    若同時提供 updated_from 與 updated_to，則會以區間方式篩選
    （大致對應 Redmine 查詢條件中的 updated_on 介於某兩日之間）。
    """
    try:
        limit_normalized = max(1, min(100, limit))
        config = RedmineConfig.from_env()
        with build_client(config) as client:
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
                    params["status_id"] = "open"
                if project_id is not None:
                    params["project_id"] = project_id

                # 依 updated_on 加上時間區間條件（對應 Redmine 查詢）
                if updated_from or updated_to:
                    date_values: list[str] = []
                    if updated_from:
                        date_values.append(updated_from)
                    if updated_to:
                        date_values.append(updated_to)

                    if date_values:
                        params["set_filter"] = 1
                        params["f[]"] = ["updated_on"]

                        if updated_from and updated_to:
                            # updated_on 介於 updated_from 與 updated_to 之間
                            params["op[updated_on]"] = "><"
                        elif updated_from:
                            # updated_on >= updated_from
                            params["op[updated_on]"] = ">="
                        else:
                            # updated_on <= updated_to
                            params["op[updated_on]"] = "<="

                        params["v[updated_on][]"] = date_values

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

            header_lines: list[str] = []
            who = config.self_name or "API Token 對應帳號（assigned_to_id=me）"
            header_lines.append(f"指派對象：{who}")
            if config.project_ids:
                header_lines.append(f"篩選專案：{', '.join(config.project_ids)}")

            header = "\n".join(header_lines) + "\n\n" if header_lines else ""
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
