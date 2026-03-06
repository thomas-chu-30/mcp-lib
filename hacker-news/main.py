#!/usr/bin/env python3
"""
Hacker News MCP Server

提供工具抓取 https://news.ycombinator.com/ 熱門內容，
取前 10 則重要項目並將標題翻譯成中文。
使用 HN 官方 Firebase API，無需 API key。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from deep_translator import GoogleTranslator
from mcp.server.fastmcp import FastMCP

# 關閉 MCP 以外日誌的噪音
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
REQUEST_TIMEOUT = 15.0
TRANSLATION_SOURCE = "en"
TRANSLATION_TARGET = "zh-TW"

mcp = FastMCP("hacker-news")


@dataclass
class Story:
    """單一則 HN 項目（故事／連結）。"""

    rank: int
    item_id: int
    title: str
    title_zh: str
    url: str | None
    score: int
    by: str
    descendants: int  # 評論數
    type: str


def _fetch_top_story_ids(limit: int = 15) -> list[int]:
    """從 HN API 取得熱門故事 ID 列表（多取幾筆以便過濾 job 等）。"""
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        r = client.get(HN_TOP)
        r.raise_for_status()
        ids: list[int] = r.json()
    return ids[:limit]


def _fetch_item(client: httpx.Client, item_id: int) -> dict[str, Any] | None:
    """取得單一 item 詳情。"""
    try:
        r = client.get(HN_ITEM.format(id=item_id))
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _translate_to_chinese(text: str) -> str:
    """將英文標題翻譯成繁體中文，失敗時回傳原文。"""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        t = GoogleTranslator(source=TRANSLATION_SOURCE, target=TRANSLATION_TARGET)
        return t.translate(text) or text
    except Exception:
        return text


def _collect_top_stories(count: int = 10) -> list[Story]:
    """抓取前 count 則重要故事（依 HN 排名），並翻譯標題。"""
    ids = _fetch_top_story_ids(limit=count + 5)
    stories: list[Story] = []
    seen = 0

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for iid in ids:
            if len(stories) >= count:
                break
            data = _fetch_item(client, iid)
            if not data:
                continue
            kind = (data.get("type") or "story").lower()
            # 只收 story/link，跳過 job、poll 等
            if kind != "story" and kind != "link":
                continue
            title = data.get("title") or ""
            if not title:
                continue
            seen += 1
            title_zh = _translate_to_chinese(title)
            url = data.get("url")
            if isinstance(url, str):
                url = url.strip() or None
            else:
                url = None
            score = int(data.get("score") or 0)
            by = str(data.get("by") or "?")
            descendants = int(data.get("descendants") or 0)
            stories.append(
                Story(
                    rank=seen,
                    item_id=int(data.get("id") or iid),
                    title=title,
                    title_zh=title_zh,
                    url=url,
                    score=score,
                    by=by,
                    descendants=descendants,
                    type=kind,
                )
            )

    return stories


def _format_output(stories: list[Story]) -> str:
    """將故事列表格式化成易讀的 Markdown 文字。"""
    lines = [
        "# Hacker News 熱門精選（前 10 則，已翻譯為中文）",
        "",
        "來源：https://news.ycombinator.com/",
        "",
    ]
    for s in stories:
        link = s.url or f"https://news.ycombinator.com/item?id={s.item_id}"
        lines.append(f"## {s.rank}. {s.title_zh}")
        lines.append("")
        lines.append(f"- **英文標題**：{s.title}")
        lines.append(f"- **連結**：{link}")
        lines.append(f"- **分數**：{s.score} | **作者**：{s.by} | **評論數**：{s.descendants}")
        lines.append("")
    return "\n".join(lines).strip()


@mcp.tool()
def get_hacker_news_top10() -> str:
    """
    抓取 Hacker News 首頁熱門內容，整理出前 10 則重要項目，
    並將每則標題翻譯成繁體中文後回傳。
    使用官方 Firebase API，不需 API key。
    """
    try:
        stories = _collect_top_stories(count=10)
        if not stories:
            return "目前無法取得 Hacker News 熱門內容，請稍後再試。"
        return _format_output(stories)
    except httpx.HTTPError as e:
        return f"請求 Hacker News API 時發生錯誤：{e!s}"
    except json.JSONDecodeError as e:
        return f"解析 API 回應時發生錯誤：{e!s}"
    except Exception as e:
        return f"發生未預期的錯誤：{e!s}"


if __name__ == "__main__":
    mcp.run()
