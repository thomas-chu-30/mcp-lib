"""Issue 與列表的 Markdown 格式化。"""

from __future__ import annotations

from typing import Any


def format_issue(issue: dict[str, Any]) -> str:
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


def format_issue_list(issues: list[dict[str, Any]], base_url: str) -> str:
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
