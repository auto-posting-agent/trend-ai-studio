# Trend AI Studio

AI/Stock 트렌드 자동 분석 및 Threads 자동 게시 시스템

## Overview

RSS, 웹사이트에서 AI/주식 관련 트렌드를 자동으로 수집하고, LLM으로 분석/요약하여 Threads에 자동 게시하는 시스템

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLModel, Alembic |
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| Database | PostgreSQL (Supabase Local), pgvector |
| Agent | LangGraph, OpenAI |
| Search | Tavily |
| Scraping | Playwright, feedparser |
| Deploy | Docker |

## Project Structure

```
trend-ai-studio/
├── backend/               # FastAPI 백엔드
│   ├── app/
│   │   ├── api/          # API 라우트
│   │   ├── core/         # 설정, DB
│   │   ├── models/       # SQLModel 모델
│   │   ├── schemas/      # Pydantic 스키마
│   │   ├── services/     # 비즈니스 로직
│   │   └── tasks/        # 스케줄러
│   ├── alembic/          # 마이그레이션
│   └── tests/
├── frontend/             # Next.js 프론트엔드
│   └── src/
├── supabase/             # Supabase 로컬 설정
└── docker-compose.yml
```

## Quick Start

### 1. Supabase Local 시작

```bash
supabase start
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env에 API 키 설정
alembic upgrade head
uvicorn app.main:app --reload
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

### 4. Docker (전체)

```bash
cp .env.example .env
docker-compose up -d
```

## Git Branch Strategy

- `main` - Production
- `dev` - Development
- `feature/*` - Feature branches

## API Documentation

Backend 실행 후: http://localhost:8000/docs

## Workflow

1. **Crawler**: RSS/웹사이트에서 콘텐츠 수집 (1-5분 주기)
2. **Vector DB**: 중복 체크 및 임베딩 저장
3. **Agent**: LangGraph로 분석/요약/콘텐츠 생성
4. **Review**: 대시보드에서 검토 (선택적)
5. **Publish**: Threads API로 게시
6. **Notify**: Discord/Telegram 알림

## Data Schema

| Field | Type | Description |
|-------|------|-------------|
| source_id | UUID | 출처 식별자 |
| title | String | 제목 |
| content | Text | 원문 |
| source_url | String | 원문 링크 |
| published_at | DateTime | 게시 시간 |
| category_hint | Enum | llm, hardware, stock, crypto 등 |
| thread_status | Enum | pending, analyzing, ready, published |
