"""Redmine 使用者查詢。"""

from __future__ import annotations

from typing import Any

import httpx

from http_client import request_with_retry


def find_user_by_name(
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
    response = request_with_retry(
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
