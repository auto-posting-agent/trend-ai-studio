# Feature Specification

> Last Updated: 2026-02-21

## Overview

AI/Stock 트렌드를 자동으로 수집, 분석, 생성하여 Threads에 자동 게시하는 시스템

## Target Topics

| Category | Sources |
|----------|---------|
| AI/LLM | OpenAI, Anthropic, Google AI 블로그, arXiv, Hacker News |
| Hardware | NVIDIA, AMD, Apple 뉴스 |
| Startup | TechCrunch, The Verge, ProductHunt |
| Stock | Bloomberg, Reuters, 증권사 리포트 |
| Crypto | CoinDesk, The Block |

## Core Features

### 1. Content Crawler

자동으로 다양한 소스에서 콘텐츠 수집

| Feature | Description |
|---------|-------------|
| RSS Crawler | RSS 피드 파싱 (feedparser) |
| Web Scraper | 동적 웹사이트 크롤링 (Playwright) |
| Scheduling | 1-5분 주기 자동 크롤링 (APScheduler) |
| Deduplication | URL 기반 중복 방지 |
| Cookie Auth | 봇 탐지 우회를 위한 쿠키 인증 |

### 2. Vector Search & Context

과거 포스팅과의 중복 방지 및 맥락 검색

| Feature | Description |
|---------|-------------|
| Embedding | Gemini text-embedding-004 |
| Vector DB | Supabase pgvector |
| Similarity Search | 유사 콘텐츠 검색 (threshold: 0.7) |
| Dedup Check | 이미 게시한 내용 중복 체크 |

### 3. AI Agent Workflow

LangGraph 기반 콘텐츠 분석 및 생성 파이프라인

| Node | Description |
|------|-------------|
| Search | Tavily로 추가 컨텍스트 검색 |
| Analyze | 트렌드 분석, 중요도 판단 |
| Generate | 페르소나 기반 콘텐츠 생성 |
| Image | 이미지 캡처/가공 (선택적) |

### 4. Threads Publisher

Meta Threads API를 통한 자동 게시

| Feature | Description |
|---------|-------------|
| Text Post | 텍스트 게시 (auto_publish_text) |
| Image Post | 이미지 첨부 게시 |
| Scheduling | 예약 게시 |
| Analytics | 게시물 성과 조회 |

### 5. Dashboard (Frontend)

관리 및 모니터링 대시보드

| Feature | Description |
|---------|-------------|
| Source Management | 크롤링 소스 추가/삭제/수정 |
| Content Review | 생성된 콘텐츠 검토/수정 |
| Manual Publish | 수동 게시 승인 |
| Statistics | 크롤링/게시 통계 |
| Scheduler Control | 스케줄러 시작/중지 |

### 6. Notification

게시 완료/에러 알림

| Channel | Description |
|---------|-------------|
| Discord | Webhook으로 알림 전송 |
| Telegram | Bot API로 알림 전송 |

## Data Flow

```
[Sources] -> [Crawler] -> [Vector DB] -> [Agent] -> [Review] -> [Publisher] -> [Threads]
                              |              |           |
                              v              v           v
                         [Dedup Check]  [Generate]  [Notification]
```

## Thread Status Lifecycle

```
PENDING -> ANALYZING -> READY -> SCHEDULED -> PUBLISHED
                          |
                          v
                       FAILED
```

| Status | Description |
|--------|-------------|
| PENDING | 크롤링 직후, 미처리 상태 |
| ANALYZING | AI 에이전트 처리 중 |
| READY | 게시 승인 대기 |
| SCHEDULED | 예약 게시 설정됨 |
| PUBLISHED | 게시 완료 |
| FAILED | 처리/게시 실패 |

## Persona (Content Style)

choi.openai 스타일 참고:
- 짧고 임팩트 있는 문장
- 핵심 정보 요약
- 적절한 이모지 사용
- 출처 명시
- 이미지/캡처 활용

## Rate Limits

| Service | Limit |
|---------|-------|
| Threads API Search | 500 queries / 7 days |
| Threads API Embedding | 5M requests / 24h |
| Tavily | Plan별 상이 |
| Gemini | 60 RPM (Free tier) |
