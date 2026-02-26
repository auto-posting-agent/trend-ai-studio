from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dt_parser


def _norm_ws(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _is_http_url(url: str) -> bool:
    scheme = (urlparse(url).scheme or "").lower()
    return scheme in {"http", "https"}


def _abs_url(base: str, maybe_url: str | None) -> str | None:
    if not maybe_url:
        return None
    full = urljoin(base, maybe_url)
    return full if _is_http_url(full) else None


def _strip_fragment(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))


def _pick_meta(soup: BeautifulSoup, key: str) -> str | None:
    for attr in ("property", "name"):
        tag = soup.find("meta", attrs={attr: key})
        if tag and tag.get("content"):
            return _norm_ws(str(tag.get("content")))
    return None


def _extract_jsonld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        txt = script.string or script.get_text()
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue
        if isinstance(data, dict):
            out.append(data)
        elif isinstance(data, list):
            out.extend([x for x in data if isinstance(x, dict)])
    return out


def _extract_article_jsonld(objs: list[dict[str, Any]]) -> dict[str, Any] | None:
    wanted = {"article", "newsarticle", "blogposting"}
    for obj in objs:
        t = obj.get("@type")
        if isinstance(t, str) and t.lower() in wanted:
            return obj
        if isinstance(t, list) and any(isinstance(x, str) and x.lower() in wanted for x in t):
            return obj
    return None


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = dt_parser.parse(raw)
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _extract_author(soup: BeautifulSoup, article_jsonld: dict[str, Any] | None) -> str | None:
    if article_jsonld:
        author = article_jsonld.get("author")
        if isinstance(author, dict):
            name = author.get("name")
            if isinstance(name, str):
                return _norm_ws(name)
        elif isinstance(author, list):
            for item in author:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    return _norm_ws(item["name"])

    for k in ("author", "article:author", "parsely-author"):
        val = _pick_meta(soup, k)
        if val:
            return val
    return None


def _extract_published_at(soup: BeautifulSoup, article_jsonld: dict[str, Any] | None) -> datetime | None:
    if article_jsonld:
        for key in ("datePublished", "dateCreated", "dateModified"):
            val = article_jsonld.get(key)
            parsed = _parse_dt(val if isinstance(val, str) else None)
            if parsed:
                return parsed

    meta_keys = (
        "article:published_time",
        "og:published_time",
        "publish_date",
        "pubdate",
        "date",
        "parsely-pub-date",
    )
    for k in meta_keys:
        parsed = _parse_dt(_pick_meta(soup, k))
        if parsed:
            return parsed

    time_tag = soup.find("time")
    if time_tag:
        parsed = _parse_dt(time_tag.get("datetime") or time_tag.get_text(" ", strip=True))
        if parsed:
            return parsed

    return None


def _extract_main_content(soup: BeautifulSoup) -> str:
    root = soup.find("article") or soup.find("main") or soup.body or soup

    for bad in root.find_all(["script", "style", "noscript"]):
        bad.decompose()

    chunks: list[str] = []
    for el in root.find_all(["h1", "h2", "h3", "p", "li"]):
        text = _norm_ws(el.get_text(" ", strip=True))
        if not text:
            continue
        if len(text) < 2:
            continue
        chunks.append(text)

    dedup: list[str] = []
    seen = set()
    for c in chunks:
        if c in seen:
            continue
        seen.add(c)
        dedup.append(c)

    content = "\n\n".join(dedup).strip()
    return content[:50000]


def _extract_images(base_url: str, soup: BeautifulSoup) -> list[str]:
    root = soup.find("article") or soup.find("main") or soup
    urls: list[str] = []
    seen: set[str] = set()
    for img in root.find_all("img"):
        src = img.get("src") or img.get("data-src")
        full = _abs_url(base_url, src)
        if not full:
            continue
        full = _strip_fragment(full)
        if full in seen:
            continue
        seen.add(full)
        urls.append(full)
    return urls


def _extract_outbound(base_url: str, soup: BeautifulSoup) -> list[str]:
    root = soup.find("article") or soup.find("main") or soup
    base_host = (urlparse(base_url).hostname or "").lower()
    urls: list[str] = []
    seen: set[str] = set()
    for a in root.find_all("a", href=True):
        full = _abs_url(base_url, a.get("href"))
        if not full:
            continue
        host = (urlparse(full).hostname or "").lower()
        if host == base_host:
            continue
        full = _strip_fragment(full)
        if full in seen:
            continue
        seen.add(full)
        urls.append(full)
    return urls


@dataclass
class GenericArticleResult:
    final_url: str
    canonical_url: str
    title: str
    summary_hint: str | None
    content: str
    author: str | None
    published_at: datetime | None
    image_urls: list[str]
    outbound_urls: list[str]
    language: str
    raw_payload: dict[str, Any]


async def crawl_generic_article(url: str, *, trust_env: bool = False) -> GenericArticleResult:
    async with httpx.AsyncClient(
        timeout=25,
        follow_redirects=True,
        trust_env=trust_env,
        headers={
            "User-Agent": "TrendAIStudioBot/0.1 (contact: trendaistudio24@gmail.com)",
            "Accept-Language": "en,ko;q=0.8",
        },
    ) as client:
        res = await client.get(url)
        res.raise_for_status()
        final_url = str(res.url)
        html = res.text

    soup = BeautifulSoup(html, "html.parser")
    jsonld = _extract_jsonld_objects(soup)
    article_jsonld = _extract_article_jsonld(jsonld)

    canonical = (
        _abs_url(final_url, _pick_meta(soup, "og:url"))
        or _abs_url(final_url, (soup.find("link", rel="canonical") or {}).get("href") if soup.find("link", rel="canonical") else None)
        or final_url
    )
    canonical = _strip_fragment(canonical)

    title = (
        _norm_ws(article_jsonld.get("headline")) if article_jsonld and isinstance(article_jsonld.get("headline"), str) else ""
    )
    if not title:
        title = _pick_meta(soup, "og:title") or _norm_ws(soup.title.get_text(" ", strip=True) if soup.title else "") or canonical

    summary_hint = (
        _pick_meta(soup, "description")
        or _pick_meta(soup, "og:description")
        or None
    )
    content = _extract_main_content(soup)
    if len(content) < 40:
        content = title

    language = _norm_ws((soup.find("html") or {}).get("lang") if soup.find("html") else "") or "en"
    language = language.split("-")[0].lower()

    result = GenericArticleResult(
        final_url=final_url,
        canonical_url=canonical,
        title=title,
        summary_hint=summary_hint,
        content=content,
        author=_extract_author(soup, article_jsonld),
        published_at=_extract_published_at(soup, article_jsonld),
        image_urls=_extract_images(canonical, soup),
        outbound_urls=_extract_outbound(canonical, soup),
        language=language,
        raw_payload={
            "extractor": "generic_article_v1",
            "http_status": res.status_code,
            "content_type": res.headers.get("content-type"),
            "final_url": final_url,
            "canonical_url": canonical,
            "jsonld_article": article_jsonld or {},
        },
    )
    return result
