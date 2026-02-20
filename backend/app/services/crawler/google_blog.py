# crawler_google_blog.py
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from schemas import NormalizedItem, SourceType, ContentType, PipelineStatus


MONTH_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\b"
)

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def _abs_url(base: str, maybe: str) -> Optional[str]:
    if not maybe:
        return None
    full = urljoin(base, maybe)
    scheme = (urlparse(full).scheme or "").lower()
    if scheme not in {"http", "https"}:
        return None
    return full

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _pick_meta(soup: BeautifulSoup, key: str) -> Optional[str]:
    """
    key examples:
      - ('property', 'og:title')
      - ('name', 'description')
    """
    # support both name= and property=
    for attr in ("property", "name"):
        tag = soup.find("meta", attrs={attr: key})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None

def _extract_jsonld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        txt = script.string
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue

        # JSON-LD can be dict or list
        if isinstance(data, dict):
            out.append(data)
        elif isinstance(data, list):
            out.extend([x for x in data if isinstance(x, dict)])
    return out

def _find_article_jsonld(jsonlds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    # look for common article types
    wanted = {"NewsArticle", "BlogPosting", "Article"}
    for obj in jsonlds:
        t = obj.get("@type")
        if isinstance(t, list):
            if any(x in wanted for x in t):
                return obj
        elif isinstance(t, str) and t in wanted:
            return obj
    return None

def _extract_main_text(soup: BeautifulSoup) -> str:
    """
    Heuristic: find <article>, then take headings + paragraphs + lists.
    """
    article = soup.find("article")
    if not article:
        # fallback: main content area
        article = soup.find("main") or soup

    # remove obvious noise
    for tag in article.find_all(["script", "style", "noscript"]):
        tag.decompose()

    chunks: List[str] = []
    for el in article.find_all(["h1", "h2", "h3", "p", "li"]):
        text = _norm_ws(el.get_text(" ", strip=True))
        if not text:
            continue
        # skip nav-like junk
        if text.lower() in {"share", "copy link", "mail"}:
            continue
        chunks.append(text)

    # de-duplicate adjacent repeats
    cleaned: List[str] = []
    for c in chunks:
        if cleaned and cleaned[-1] == c:
            continue
        cleaned.append(c)

    return "\n\n".join(cleaned).strip()

def _extract_images_with_positions(base_url: str, soup: BeautifulSoup) -> Tuple[List[str], List[Dict[str, Any]]]:
    article = soup.find("article") or soup.find("main") or soup
    flow_tags = ["h1", "h2", "h3", "p", "li", "img"]

    text_blocks: List[Tuple[int, str]] = []
    image_blocks: List[Dict[str, Any]] = []

    for idx, el in enumerate(article.find_all(flow_tags)):
        if el.name == "img":
            src = el.get("src") or el.get("data-src")
            full = _abs_url(base_url, src) if src else None
            if not full:
                continue
            image_blocks.append(
                {
                    "url": full,
                    "dom_index": idx,
                    "alt": _norm_ws(el.get("alt", "")) or None,
                }
            )
            continue

        text = _norm_ws(el.get_text(" ", strip=True))
        if not text:
            continue
        if text.lower() in {"share", "copy link", "mail"}:
            continue
        text_blocks.append((idx, text))

    for img in image_blocks:
        dom_index = img["dom_index"]
        before_text = None
        after_text = None

        for t_idx, t_text in reversed(text_blocks):
            if t_idx < dom_index:
                before_text = t_text
                break
        for t_idx, t_text in text_blocks:
            if t_idx > dom_index:
                after_text = t_text
                break

        img["before_text"] = before_text
        img["after_text"] = after_text

    # unique preserve order for existing image_urls field
    seen = set()
    image_urls = []
    for block in image_blocks:
        u = block["url"]
        if u in seen:
            continue
        seen.add(u)
        image_urls.append(u)

    return image_urls, image_blocks

def _extract_outbound_links(base_url: str, soup: BeautifulSoup) -> List[str]:
    article = soup.find("article") or soup
    base_host = (urlparse(base_url).hostname or "").lower()

    share_hosts = {
        "twitter.com",
        "x.com",
        "www.facebook.com",
        "facebook.com",
        "www.linkedin.com",
        "linkedin.com",
    }

    def _is_share_url(parsed) -> bool:
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
        if host in share_hosts:
            return True
        return (
            "/intent/tweet" in path
            or "/sharer" in path
            or "/sharearticle" in path
        )

    def _normalized_no_fragment(u: str) -> str:
        p = urlparse(u)
        return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))

    links = []
    for a in article.find_all("a", href=True):
        href = a["href"]
        full = _abs_url(base_url, href)
        if not full:
            continue
        parsed = urlparse(full)
        host = (parsed.hostname or "").lower()

        # keep outbound links only (exclude same-site navigation links)
        if host == base_host:
            continue
        # remove social/share-style links
        if _is_share_url(parsed):
            continue
        links.append(_normalized_no_fragment(full))

    seen = set()
    uniq = []
    for u in links:
        if u in seen:
            continue
        seen.add(u)
        uniq.append(u)
    return uniq

def _guess_published_at(soup: BeautifulSoup, jsonld_article: Optional[Dict[str, Any]]) -> Optional[datetime]:
    # 1) JSON-LD datePublished
    if jsonld_article:
        dp = jsonld_article.get("datePublished") or jsonld_article.get("dateCreated")
        if isinstance(dp, str) and dp.strip():
            try:
                return dateparser.parse(dp).astimezone(timezone.utc)
            except Exception:
                pass

    # 2) meta article:published_time
    meta_time = _pick_meta(soup, "article:published_time")
    if meta_time:
        try:
            return dateparser.parse(meta_time).astimezone(timezone.utc)
        except Exception:
            pass

    # 3) visible month day year somewhere near top
    text = soup.get_text(" ", strip=True)
    m = MONTH_RE.search(text)
    if m:
        try:
            return dateparser.parse(m.group(0)).replace(tzinfo=timezone.utc)
        except Exception:
            pass

    return None

def _guess_author(soup: BeautifulSoup, jsonld_article: Optional[Dict[str, Any]]) -> Optional[str]:
    if jsonld_article:
        author = jsonld_article.get("author")
        # author can be dict or list
        if isinstance(author, dict):
            name = author.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        if isinstance(author, list):
            for a in author:
                if isinstance(a, dict) and isinstance(a.get("name"), str):
                    return a["name"].strip()

    # meta author
    meta_author = _pick_meta(soup, "author")
    if meta_author:
        return meta_author.strip()

    # fallback: look for a short "byline-ish" string in the header
    # (Google blog often shows something like "The Gemini Team")
    # We'll search a small set of candidates
    candidates = soup.find_all(string=re.compile(r"\bTeam\b|\bGoogle\b", re.I))
    for c in candidates[:30]:
        s = _norm_ws(str(c))
        if 2 <= len(s) <= 60 and ("team" in s.lower()):
            return s

    return None

def _classify(url: str, title: str, text: str) -> Tuple[ContentType, List[str]]:
    u = url.lower()
    t = (title + " " + text[:500]).lower()

    hints: List[str] = []
    if "gemini" in u or "gemini" in t:
        hints.append("Gemini")
    if "google" in u or "google" in t:
        hints.append("Google")

    if any(k in t for k in ["announcing", "released", "launch", "rolling out", "preview", "pro is here"]):
        ctype = ContentType.MODEL_RELEASE
    else:
        ctype = ContentType.PRODUCT_UPDATE

    # refine: if lots of benchmark mentions
    if any(k in t for k in ["benchmark", "arc-agi", "score", "eval"]):
        hints.append("Benchmark")
    if any(k in t for k in ["multimodal", "vision", "image", "video"]):
        hints.append("Multimodal")

    # unique hints
    hints_uniq = []
    seen = set()
    for h in hints:
        if h in seen:
            continue
        seen.add(h)
        hints_uniq.append(h)

    return ctype, hints_uniq

async def crawl_google_blog_article(url: str) -> NormalizedItem:
    async with httpx.AsyncClient(
        timeout=20,
        headers={
            "User-Agent": "TrendAIStudioBot/0.1 (contact: trendaistudio24@gmail.com)",
            "Accept-Language": "en,ko;q=0.8",
        },
        follow_redirects=True,
    ) as client:
        r = await client.get(url)
        r.raise_for_status()
        html = r.text

    soup = BeautifulSoup(html, "html.parser")

    jsonlds = _extract_jsonld(soup)
    article_jsonld = _find_article_jsonld(jsonlds)

    title = (
        (article_jsonld.get("headline") if article_jsonld else None)
        or _pick_meta(soup, "og:title")
        or (soup.find("h1").get_text(strip=True) if soup.find("h1") else None)
        or "Untitled"
    )
    title = _norm_ws(title)

    canonical = (
        (article_jsonld.get("mainEntityOfPage") if article_jsonld else None)
        or soup.find("link", rel="canonical")["href"] if soup.find("link", rel="canonical") else None
    )
    if isinstance(canonical, dict):  # sometimes JSON-LD uses {"@id": "..."}
        canonical = canonical.get("@id")
    canonical = canonical or url

    summary_hint = _pick_meta(soup, "og:description") or _pick_meta(soup, "description")

    published_at = _guess_published_at(soup, article_jsonld)
    author = _guess_author(soup, article_jsonld)

    content_text = _extract_main_text(soup)
    image_urls, image_positions = _extract_images_with_positions(canonical, soup)
    outbound_urls = _extract_outbound_links(canonical, soup)

    content_type, category_hint = _classify(canonical, title, content_text)

    # dedup: canonical + title + date + first 800 chars
    dedup_basis = f"{canonical}\n{title}\n{published_at.isoformat() if published_at else ''}\n{content_text[:800]}"
    content_hash = _sha256(dedup_basis)

    # source_id: prefer canonical; stable across runs
    source_id = _sha256(canonical)

    item = NormalizedItem(
        item_id=str(uuid.uuid4()),
        source_id=source_id,
        content_hash=content_hash,
        source_type=SourceType.HTML_ARTICLE,
        source_name="Google Blog (Innovation & AI)",
        source_url=url,
        canonical_url=canonical,
        fetched_at=_now_utc(),
        title=title,
        content=content_text,
        summary_hint=summary_hint,
        language="en",
        author=author,
        published_at=published_at,
        image_urls=image_urls,
        image_positions=image_positions,
        outbound_urls=outbound_urls,
        content_type=content_type,
        category_hint=category_hint,
        tags=["google", "ai", "gemini"],
        thread_status=PipelineStatus.PENDING,
        metadata={
            "site": "blog.google",
            "section": "Innovation & AI / Models & Research",
        },
        raw_payload={
            "jsonld": article_jsonld or {},
        },
    )
    return item

if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Crawl a Google blog article and save as normalized JSON.")
    parser.add_argument("url", help="Target article URL")
    parser.add_argument(
        "--out",
        help="Output file path (default: outputs/google_blog/<timestamp>_<sourceid>.json)",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Also print JSON to stdout",
    )
    args = parser.parse_args()

    item = asyncio.run(crawl_google_blog_article(args.url))
    payload = item.model_dump_json(indent=2, exclude_none=True)

    if args.out:
        out_path = Path(args.out)
    else:
        ts = _now_utc().strftime("%Y%m%dT%H%M%SZ")
        out_path = Path("outputs") / "google_blog" / f"{ts}_{item.source_id[:12]}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload, encoding="utf-8")
    print(f"Saved: {out_path}")

    if args.print_json:
        print(payload)
