# Trend AI Studio - Backend

FastAPI 기반 AI 트렌드 분석 및 Threads 자동 게시 백엔드

## Tech Stack

- **Framework**: FastAPI 0.115+
- **ORM**: SQLModel (Pydantic + SQLAlchemy)
- **Database**: PostgreSQL (Supabase Local)
- **Vector Search**: pgvector
- **Migration**: Alembic
- **Agent**: LangGraph
- **Search**: Tavily
- **Scraping**: Playwright, feedparser
- **Task Queue**: APScheduler

## Setup

### 1. Supabase Local 설치

```bash
# Supabase CLI 설치
brew install supabase/tap/supabase

# 프로젝트 루트에서 초기화
supabase init

# 로컬 Supabase 시작
supabase start
```

로컬 Supabase 정보:
- API URL: http://localhost:54321
- DB URL: postgresql://postgres:postgres@localhost:54322/postgres
- Studio: http://localhost:54323

### 2. Python 환경 설정

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경 변수

```bash
cp .env.example .env
# .env 파일에 API 키 입력
```

### 4. Playwright 브라우저 설치

```bash
playwright install chromium
```

### 5. 마이그레이션

```bash
# 마이그레이션 생성
alembic revision --autogenerate -m "description"

# 마이그레이션 적용
alembic upgrade head
```

### 6. 서버 실행

```bash
uvicorn app.main:app --reload
```

API 문서: http://localhost:8000/docs

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── routes/          # API 엔드포인트
│   ├── core/
│   │   ├── config.py        # 환경 설정
│   │   └── database.py      # DB 연결
│   ├── models/              # SQLModel 모델
│   ├── schemas/             # Pydantic 스키마 (요청/응답)
│   ├── services/
│   │   ├── agent/           # LangGraph 워크플로우
│   │   ├── crawler/         # RSS, Playwright
│   │   ├── publisher/       # Threads API
│   │   └── vector/          # 임베딩
│   └── tasks/               # 스케줄러
├── alembic/                 # 마이그레이션
├── tests/
└── requirements.txt
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| GET | /api/threads | 스레드 목록 |
| POST | /api/threads | 스레드 생성 |
| POST | /api/threads/{id}/publish | Threads에 게시 |
| GET | /api/sources | 소스 목록 |
| POST | /api/sources | 소스 추가 |
| POST | /api/sources/{id}/crawl | 수동 크롤링 |
| GET | /api/scheduler/status | 스케줄러 상태 |

## Development

```bash
# 테스트 실행
pytest

# 코드 포맷팅
ruff format .

# 린트
ruff check .
```
