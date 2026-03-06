#!/usr/bin/env python3
"""
Hacker News MCP Server

提供工具抓取 https://news.ycombinator.com/ 熱門內容，
以 Algolia API 搜尋 AI 與科技相關項目（前 20 則）並將標題翻譯成中文。
Algolia 失敗時會退回 Firebase API + 關鍵字過濾。皆不需 API key。
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

# 查詢筆數：可由環境變數 HN_TOP_COUNT 設定（預設 20，範圍 1～50）
DEFAULT_TOP_COUNT = 20
TOP_COUNT_MIN, TOP_COUNT_MAX = 1, 50

import httpx
from deep_translator import GoogleTranslator
from mcp.server.fastmcp import FastMCP

# 關閉 MCP 以外日誌的噪音
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
REQUEST_TIMEOUT = 15.0
ALGOLIA_MIN_POINTS = 50  # 只取熱度較高的文章
TRANSLATION_SOURCE = "en"
TRANSLATION_TARGET = "zh-TW"

# AI / 科技相關關鍵字（標題包含任一個即視為符合）
AI_TECH_KEYWORDS = frozenset({
    "ai", "artificial intelligence", "llm", "gpt", "openai", "claude", "anthropic",
    "machine learning", " ml ", " neural", "deep learning", "transformer", "embedding",
    "tech", "technology", "software", "programming", "coding", "developer",
    "api", "open source", "linux", "python", "rust", "javascript", "vue", "react",
    "cloud", "kubernetes", "docker", "database", "security", "cyber",
    "robot", "automation", "algorithm", "computer", "chip", "gpu", "nvidia", "amd",
    "quantum", "crypto", "blockchain", "web3", "ar ", "vr ", "metaverse",
})

# 排除用語：標題若以這些為主（易誤判為科技），則不列入
NOT_TECH_PHRASES = frozenset({
    "bubble tea", "lip gloss", "brand age", "the brand age",
    "bubbles are available", "next generations of bubble",
    "airfoil",  # 標題 "Airfoil" 會因含 "ai" 被 Algolia 搜到
})

mcp = FastMCP("hacker-news")


def _get_top_count_from_env() -> int:
    """從環境變數 HN_TOP_COUNT 讀取筆數，無效或未設則回傳預設值。"""
    raw = os.environ.get("HN_TOP_COUNT", str(DEFAULT_TOP_COUNT)).strip()
    try:
        n = int(raw)
        return max(TOP_COUNT_MIN, min(TOP_COUNT_MAX, n))
    except ValueError:
        return DEFAULT_TOP_COUNT


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


def _fetch_algolia(
    query: str,
    *,
    tags: str = "story",
    min_points: int = ALGOLIA_MIN_POINTS,
    hits_per_page: int = 15,
    created_after_ts: int | None = None,
) -> list[dict[str, Any]]:
    """用 Algolia API 依關鍵字搜尋 HN，回傳 hit 列表（含 title, url, points, author, num_comments, objectID）。"""
    numeric_filters = f"points>{min_points}"
    if created_after_ts is not None:
        numeric_filters += f",created_at_i>{created_after_ts}"
    params: dict[str, str | int] = {
        "query": query,
        "tags": tags,
        "numericFilters": numeric_filters,
        "hitsPerPage": hits_per_page,
    }
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        r = client.get(ALGOLIA_SEARCH, params=params)
        r.raise_for_status()
        data: dict[str, Any] = r.json()
    return data.get("hits") or []


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


def _is_ai_or_tech(title: str) -> bool:
    """檢查標題是否與 AI 或科技相關（關鍵字匹配），並排除易誤判的用語。"""
    if not title:
        return False
    lower = title.lower()
    if any(phrase in lower for phrase in NOT_TECH_PHRASES):
        return False
    return any(kw in lower for kw in AI_TECH_KEYWORDS)


def _algolia_hit_to_story(hit: dict[str, Any], rank: int) -> Story:
    """將 Algolia 的單筆 hit 轉成 Story 並翻譯標題。"""
    title = (hit.get("title") or "").strip()
    title_zh = _translate_to_chinese(title)
    url = hit.get("url")
    url = url.strip() or None if isinstance(url, str) else None
    return Story(
        rank=rank,
        item_id=int(hit.get("objectID") or hit.get("story_id") or 0),
        title=title,
        title_zh=title_zh,
        url=url,
        score=int(hit.get("points") or 0),
        by=str(hit.get("author") or "?"),
        descendants=int(hit.get("num_comments") or 0),
        type="story",
    )


def _collect_via_algolia(count: int = 10, created_after_ts: int | None = None) -> list[Story]:
    """用 Algolia 搜尋「AI」與「software」兩類，合併去重後依分數取前 count 則。"""
    seen: dict[str, dict[str, Any]] = {}  # objectID -> hit（保留分數較高者）
    kwargs: dict[str, Any] = {"hits_per_page": count + 25}
    if created_after_ts is not None:
        kwargs["created_after_ts"] = created_after_ts

    for query in ("AI", "software"):
        try:
            for hit in _fetch_algolia(query, **kwargs):
                oid = str(hit.get("objectID") or "")
                if not oid:
                    continue
                title = (hit.get("title") or "").strip()
                if not title:
                    continue
                if any(phrase in title.lower() for phrase in NOT_TECH_PHRASES):
                    continue
                existing = seen.get(oid)
                if existing is None or int(hit.get("points") or 0) > int(existing.get("points") or 0):
                    seen[oid] = hit
        except Exception:
            continue

    # 依分數排序，取前 count 筆
    sorted_hits = sorted(seen.values(), key=lambda h: int(h.get("points") or 0), reverse=True)[:count]
    stories: list[Story] = []
    for i, hit in enumerate(sorted_hits, start=1):
        stories.append(_algolia_hit_to_story(hit, rank=i))
    return stories


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


def _collect_top_stories_firebase(count: int = 10, ai_tech_only: bool = True) -> list[Story]:
    """用 Firebase API 抓熱門 ID，再逐筆取 item、依關鍵字篩選（備援方案）。"""
    ids = _fetch_top_story_ids(limit=80 if ai_tech_only else count + 5)
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
            if kind != "story" and kind != "link":
                continue
            title = data.get("title") or ""
            if not title:
                continue
            if ai_tech_only and not _is_ai_or_tech(title):
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


def _collect_top_stories(count: int = 10, ai_tech_only: bool = True) -> list[Story]:
    """優先使用 Algolia 搜尋 AI/科技，失敗時退回 Firebase + 關鍵字過濾。"""
    if ai_tech_only:
        try:
            stories = _collect_via_algolia(count=count)
            if stories:
                return stories
        except Exception:
            pass
    return _collect_top_stories_firebase(count=count, ai_tech_only=ai_tech_only)


def _format_output(
    stories: list[Story],
    ai_tech_only: bool = True,
    count: int = DEFAULT_TOP_COUNT,
) -> str:
    """將故事列表格式化成易讀的 Markdown 文字。"""
    subtitle = f"AI 與科技相關，前 {count} 則" if ai_tech_only else f"前 {count} 則"
    lines = [
        f"# Hacker News 熱門精選（{subtitle}，已翻譯為中文）",
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
    抓取 Hacker News 的 AI 與科技相關熱門內容（以 Algolia 搜尋），
    回傳筆數由環境變數 HN_TOP_COUNT 決定（預設 20），並將標題翻譯成繁體中文。失敗時改以 Firebase API 備援。
    """
    try:
        count = _get_top_count_from_env()
        stories = _collect_top_stories(count=count, ai_tech_only=True)
        if not stories:
            return "目前無法取得符合條件的 Hacker News 內容（AI/科技），請稍後再試。"
        return _format_output(stories, ai_tech_only=True, count=count)
    except httpx.HTTPError as e:
        return f"請求 Hacker News API 時發生錯誤：{e!s}"
    except json.JSONDecodeError as e:
        return f"解析 API 回應時發生錯誤：{e!s}"
    except Exception as e:
        return f"發生未預期的錯誤：{e!s}"


def _format_output_past_week(stories: list[Story], count: int) -> str:
    """將過去一週的故事列表格式化成易讀的 Markdown。"""
    lines = [
        "# Hacker News 過去一週重要科技新聞（依熱度排序，已翻譯為中文）",
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
def get_hacker_news_past_week() -> str:
    """
    抓取 Hacker News 過去一週內、AI 與科技相關且熱度較高的內容（以 Algolia 依 created_at 篩選），
    回傳前 15 則並依分數排序，標題翻譯成繁體中文。用於取得「最近一週最重要的科技新聞」。
    """
    try:
        count = min(15, max(1, _get_top_count_from_env()))
        created_after_ts = int(time.time()) - (7 * 24 * 3600)
        stories = _collect_via_algolia(count=count, created_after_ts=created_after_ts)
        if not stories:
            return "過去一週內沒有符合條件的 Hacker News 內容（AI/科技、熱度門檻），請稍後再試或放寬條件。"
        return _format_output_past_week(stories, count=count)
    except httpx.HTTPError as e:
        return f"請求 Hacker News API 時發生錯誤：{e!s}"
    except json.JSONDecodeError as e:
        return f"解析 API 回應時發生錯誤：{e!s}"
    except Exception as e:
        return f"發生未預期的錯誤：{e!s}"


if __name__ == "__main__":
    mcp.run()
