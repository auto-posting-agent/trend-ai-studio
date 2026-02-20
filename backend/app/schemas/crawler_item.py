# schemas.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class SourceType(str, Enum):
    RSS = "rss"
    ATOM = "atom"
    HTML_ARTICLE = "html_article"
    HTML_INDEX = "html_index"
    API = "api"
    GITHUB = "github"
    ARXIV = "arxiv"
    SOCIAL = "social"


class ContentType(str, Enum):
    MODEL_RELEASE = "model_release"
    PRODUCT_UPDATE = "product_update"
    TOOLING = "tooling"
    RESEARCH_PAPER = "research_paper"
    BENCHMARK = "benchmark"
    OPINION = "opinion"
    FUNDING = "funding"
    SECURITY = "security"
    OTHER = "other"


class PipelineStatus(str, Enum):
    PENDING = "PENDING"      # 수집 직후
    ANALYZING = "ANALYZING"  # 에이전트 가공중
    READY = "READY"          # 승인 대기
    PUBLISHED = "PUBLISHED"  # 게시 완료
    FAILED = "FAILED"        # 수집/가공 실패


class NormalizedItem(BaseModel):
    # --- identity / dedup ---
    item_id: str = Field(..., description="우리 시스템 내부 UUID 또는 ULID")
    source_id: str = Field(..., description="출처별 고유 식별자(가능하면 원문 ID), 없으면 URL 기반 해시")
    content_hash: str = Field(..., description="중복 방지용 해시(보통 title+canonical_url+published_at+content 일부)")

    # --- provenance ---
    source_type: SourceType
    source_name: str
    source_url: HttpUrl
    canonical_url: Optional[HttpUrl] = None
    fetched_at: datetime

    # --- content ---
    title: str
    content: str = Field(..., description="본문 텍스트(에이전트 입력용 raw)")
    summary_hint: Optional[str] = Field(None, description="출처가 제공하는 요약/설명(메타 디스크립션 등)")
    language: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None

    # --- media / links ---
    image_urls: List[HttpUrl] = Field(default_factory=list)
    image_positions: List[Dict[str, Any]] = Field(default_factory=list)
    outbound_urls: List[HttpUrl] = Field(default_factory=list)

    # --- classification ---
    content_type: ContentType = ContentType.OTHER
    category_hint: List[str] = Field(default_factory=list, description="['Gemini','Google','Multimodal'] 같은 멀티 힌트")
    tags: List[str] = Field(default_factory=list)

    # --- pipeline ---
    thread_status: PipelineStatus = PipelineStatus.PENDING

    # --- source-specific ---
    metadata: Dict[str, Any] = Field(default_factory=dict, description="소스별 특이 필드")
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="가능하면 원본에서 가져온 구조화 데이터(JSON-LD 등)")
