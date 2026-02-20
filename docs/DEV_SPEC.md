# 개발 명세

> 최종 수정: 2026-02-21

## 기술 스택

| 구분 | 기술 | 용도 |
|------|------|------|
| Framework | FastAPI | 고성능 비동기 백엔드 |
| ORM | SQLModel | Pydantic + SQLAlchemy 통합 |
| Migration | Alembic | DB 스키마 마이그레이션 |
| Orchestration | LangGraph | 에이전트 워크플로우 |
| Database | Supabase (PostgreSQL) | 메타데이터, 설정 저장 |
| Vector Search | pgvector | 유사도 검색, 중복 방지 |
| Search | Tavily | LLM 전용 실시간 웹 검색 |
| Scraper | Playwright | 동적 웹사이트 크롤링 |
| LLM | Gemini | 텍스트 생성, 임베딩 |
| Frontend | Next.js 15 | 대시보드 UI |
| Deploy | Docker | 컨테이너 배포 |

## 데이터 스키마

### sources 테이블

| 필드 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| name | String | 소스 이름 |
| url | String | 소스 URL |
| source_type | Enum | rss, playwright, api |
| category_hint | Enum | llm, hardware, stock 등 |
| crawl_interval_minutes | Int | 크롤링 주기 (분) |
| enabled | Boolean | 활성화 여부 |
| config | JSON | 소스별 설정 |
| last_crawled_at | DateTime | 마지막 크롤링 시간 |
| created_at | DateTime | 생성 시간 |
| updated_at | DateTime | 수정 시간 |

### crawled_contents 테이블

| 필드 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| source_id | UUID | FK -> sources |
| title | String | 제목 |
| content | Text | 원문 전체 |
| summary_manual | Text | 출처 제공 요약문 |
| image_urls | JSON | 이미지 URL 리스트 |
| source_url | String | 원문 링크 (unique) |
| published_at | DateTime | 원문 게시 시간 |
| metadata | JSON | 좋아요, 작성자 등 |
| category_hint | Enum | 카테고리 힌트 |
| thread_status | Enum | pending, analyzing, ready 등 |
| created_at | DateTime | 생성 시간 |
| updated_at | DateTime | 수정 시간 |

### threads 테이블

| 필드 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| source_content_id | UUID | FK -> crawled_contents |
| content | Text | 생성된 스레드 내용 |
| image_urls | JSON | 첨부 이미지 |
| status | Enum | pending, ready, published 등 |
| scheduled_at | DateTime | 예약 게시 시간 |
| published_at | DateTime | 실제 게시 시간 |
| threads_post_id | String | Threads 게시물 ID |
| metadata | JSON | 추가 정보 |
| created_at | DateTime | 생성 시간 |
| updated_at | DateTime | 수정 시간 |

### content_embeddings 테이블

| 필드 | 타입 | 설명 |
|------|------|------|
| content_id | UUID | PK, FK -> crawled_contents |
| embedding | vector(768) | Gemini 임베딩 |
| metadata | JSON | 추가 정보 |

## API 엔드포인트

### Sources

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | /api/sources | 소스 목록 |
| POST | /api/sources | 소스 추가 |
| GET | /api/sources/{id} | 소스 상세 |
| PUT | /api/sources/{id} | 소스 수정 |
| DELETE | /api/sources/{id} | 소스 삭제 |
| POST | /api/sources/{id}/crawl | 수동 크롤링 |

### Threads

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | /api/threads | 스레드 목록 |
| POST | /api/threads | 스레드 생성 |
| GET | /api/threads/{id} | 스레드 상세 |
| PUT | /api/threads/{id} | 스레드 수정 |
| DELETE | /api/threads/{id} | 스레드 삭제 |
| POST | /api/threads/{id}/publish | 게시 |

### Scheduler

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | /api/scheduler/status | 상태 조회 |
| POST | /api/scheduler/start | 시작 |
| POST | /api/scheduler/stop | 중지 |

## 디렉토리 구조

```
backend/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── sources.py      # 소스 API
│   │       ├── threads.py      # 스레드 API
│   │       └── scheduler.py    # 스케줄러 API
│   ├── core/
│   │   ├── config.py           # 환경 설정
│   │   └── database.py         # DB 연결
│   ├── models/
│   │   ├── source.py           # Source, CrawledContent 모델
│   │   └── thread.py           # Thread 모델
│   ├── schemas/
│   │   ├── source.py           # 요청/응답 스키마
│   │   └── thread.py           # 요청/응답 스키마
│   ├── services/
│   │   ├── agent/
│   │   │   ├── workflow.py     # LangGraph 워크플로우
│   │   │   ├── nodes/          # 워크플로우 노드
│   │   │   └── prompts/        # 프롬프트 템플릿
│   │   ├── crawler/
│   │   │   ├── base.py         # 크롤러 베이스
│   │   │   ├── rss.py          # RSS 크롤러
│   │   │   └── playwright.py   # Playwright 크롤러
│   │   ├── publisher/
│   │   │   └── threads.py      # Threads API
│   │   └── vector/
│   │       └── embedder.py     # 임베딩, 유사도 검색
│   └── tasks/
│       └── scheduler.py        # APScheduler
├── alembic/                    # 마이그레이션
└── tests/
```

## LangGraph 워크플로우

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                           v
                    ┌─────────────┐
                    │   Search    │  <- Tavily 검색
                    └──────┬──────┘
                           │
                           v
                    ┌─────────────┐
                    │   Analyze   │  <- 중요도 분석, 중복 체크
                    └──────┬──────┘
                           │
               ┌───────────┼───────────┐
               │           │           │
               v           v           v
           [Skip]      [Generate]  [Need More]
                           │           │
                           │           └──> Search
                           v
                    ┌─────────────┐
                    │     END     │
                    └─────────────┘
```

## 환경 변수

| 변수 | 설명 | 필수 |
|------|------|------|
| DATABASE_URL | PostgreSQL 연결 URL | O |
| SUPABASE_URL | Supabase API URL | O |
| SUPABASE_ANON_KEY | Supabase anon key | O |
| GEMINI_API_KEY | Gemini API 키 | O |
| TAVILY_API_KEY | Tavily API 키 | O |
| THREADS_ACCESS_TOKEN | Threads 액세스 토큰 | O |
| DISCORD_WEBHOOK_URL | Discord 웹훅 | X |
| TELEGRAM_BOT_TOKEN | Telegram 봇 토큰 | X |
| TELEGRAM_CHAT_ID | Telegram 채팅 ID | X |
