"""註冊所有 Redmine MCP tools（import 時會執行 @mcp.tool() 裝飾器）。"""

from tools.create_issue import create_issue
from tools.get_my_issues import get_my_issues
from tools.get_user_issues import get_user_issues
from tools.update_issue import update_issue

__all__ = [
    "get_my_issues",
    "get_user_issues",
    "create_issue",
    "update_issue",
]
