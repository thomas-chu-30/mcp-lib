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

from app import mcp
import tools  # noqa: F401 — 載入以註冊所有 tools

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


if __name__ == "__main__":
    mcp.run()
