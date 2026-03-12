"""HTTP 請求封裝與重試邏輯。"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 0.5


def request_with_retry(
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
    對 5xx 或連線錯誤進行最多 MAX_RETRIES 次重試（指數退避）；4xx 直接拋錯。
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
                response.raise_for_status()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            logger.warning("Redmine API 請求失敗（第 %d 次）：%s", attempt + 1, exc)

        attempt += 1
        if attempt > MAX_RETRIES:
            break
        time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Redmine API 多次重試後仍然失敗。")
