"""更新既有 Redmine issue。"""

from __future__ import annotations

from typing import Any

import httpx

from app import mcp
from config import RedmineConfig, RedmineConfigError, build_client
from http_client import request_with_retry


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

        with build_client(config) as client:
            request_with_retry(
                client,
                "PUT",
                f"/issues/{issue_id}.json",
                json_body=payload,
                expected_status=(200, 204),
            )

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
