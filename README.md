# Trend AI Studio

AI/Stock 트렌드 자동 분석 및 Threads 자동 게시 시스템

## 개요

RSS, 웹사이트에서 AI/주식 관련 트렌드를 자동으로 수집하고, LLM으로 분석/요약하여 Threads에 자동 게시하는 시스템

## 문서

- [설치 가이드](docs/SETUP.md)
- [기능 명세](docs/FEATURE_SPEC.md)
- [개발 명세](docs/DEV_SPEC.md)
- [역할 분담 가이드](docs/ROLE_GUIDE.md)

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | FastAPI, SQLModel, Alembic |
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| Database | PostgreSQL (Supabase Local), pgvector |
| Agent | LangGraph, Gemini |
| Search | Tavily |
| Scraping | Playwright, feedparser |
| Deploy | Docker |

## 프로젝트 구조

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
├── docs/                 # 문서
├── supabase/             # Supabase 로컬 설정
└── docker-compose.yml
```

## 빠른 시작

```bash
# 1. Supabase 로컬 시작
supabase start

# 2. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # API 키 설정
alembic upgrade head
uvicorn app.main:app --reload

# 3. Frontend
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

자세한 설치 방법은 [설치 가이드](docs/SETUP.md) 참조

## 브랜치 전략

- `main` - 프로덕션
- `dev` - 개발 통합
- `feature/*` - 기능 브랜치

## 워크플로우

```
[소스] -> [크롤러] -> [벡터 DB] -> [에이전트] -> [검토] -> [게시] -> [Threads]
```

1. **Crawler**: RSS/웹사이트에서 콘텐츠 수집 (1-5분 주기)
2. **Vector DB**: 중복 체크 및 임베딩 저장
3. **Agent**: LangGraph로 분석/요약/콘텐츠 생성
4. **Review**: 대시보드에서 검토 (선택적)
5. **Publish**: Threads API로 게시
6. **Notify**: Discord/Telegram 알림

## API 문서

Backend 실행 후: http://localhost:8000/docs
