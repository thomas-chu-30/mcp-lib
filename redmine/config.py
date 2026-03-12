"""Redmine 設定與 HTTP client 建構。"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

ENV_BASE_URL = "REDMINE_BASE_URL"
ENV_API_TOKEN = "REDMINE_API_TOKEN"
ENV_PROJECT_IDS = "REDMINE_PROJECT_IDS"
ENV_SELF_NAME = "REDMINE_SELF_NAME"
ENV_SELF_ID = "REDMINE_SELF_ID"

REQUEST_TIMEOUT = 15.0

# 未設定環境變數時，建立 issue 預設指派給此名稱（可改為你的 Redmine 顯示名稱）
DEFAULT_ASSIGNEE_NAME = "Thomas Chu"


class RedmineConfigError(RuntimeError):
    """Redmine MCP 的設定錯誤（缺少或錯誤的環境變數）。"""


@dataclass(slots=True)
class RedmineConfig:
    base_url: str
    api_token: str
    project_ids: list[str]
    self_name: str | None
    self_id: int | None

    @classmethod
    def from_env(cls) -> RedmineConfig:
        base_url = os.environ.get(ENV_BASE_URL, "").strip().rstrip("/")
        api_token = os.environ.get(ENV_API_TOKEN, "").strip()
        raw_project_ids = os.environ.get(ENV_PROJECT_IDS, "")
        self_name = os.environ.get(ENV_SELF_NAME, "").strip() or None
        self_id: int | None = None
        raw_self_id = os.environ.get(ENV_SELF_ID, "").strip()
        if raw_self_id:
            try:
                self_id = int(raw_self_id)
                if self_id <= 0:
                    self_id = None
            except ValueError:
                pass

        project_ids: list[str] = []
        if raw_project_ids:
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
            self_id=self_id,
        )


def build_client(config: RedmineConfig) -> httpx.Client:
    """依設定建立 httpx.Client。"""
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
