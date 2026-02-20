<p align="center">
  <h1 align="center">Trend AI Studio</h1>
  <p align="center">AI/Stock 트렌드 자동 분석 및 Threads 자동 게시 시스템</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=next.js&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/PostgreSQL-Supabase-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/LangGraph-Agent-FF6F00?style=flat-square&logo=langchain&logoColor=white" alt="LangGraph" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Gemini-LLM-8E75B2?style=flat-square&logo=google&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/Threads-API-000000?style=flat-square&logo=threads&logoColor=white" alt="Threads" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker" />
</p>

---

## 개요

RSS, 웹사이트에서 AI/주식 관련 트렌드를 자동으로 수집하고, LLM으로 분석/요약하여 Threads에 자동 게시하는 시스템

## 문서

| 문서 | 설명 |
|------|------|
| [설치 가이드](docs/SETUP.md) | 환경 설정 및 실행 방법 |
| [기능 명세](docs/FEATURE_SPEC.md) | 시스템 기능 상세 |
| [개발 명세](docs/DEV_SPEC.md) | 기술 스택 및 API 명세 |
| [역할 분담](docs/ROLE_GUIDE.md) | 개발 역할 분담 가이드 |

## 기술 스택

<table>
  <tr>
    <td align="center" width="96">
      <img src="https://skillicons.dev/icons?i=fastapi" width="48" height="48" alt="FastAPI" />
      <br>FastAPI
    </td>
    <td align="center" width="96">
      <img src="https://skillicons.dev/icons?i=nextjs" width="48" height="48" alt="Next.js" />
      <br>Next.js
    </td>
    <td align="center" width="96">
      <img src="https://skillicons.dev/icons?i=postgres" width="48" height="48" alt="PostgreSQL" />
      <br>PostgreSQL
    </td>
    <td align="center" width="96">
      <img src="https://skillicons.dev/icons?i=supabase" width="48" height="48" alt="Supabase" />
      <br>Supabase
    </td>
    <td align="center" width="96">
      <img src="https://skillicons.dev/icons?i=docker" width="48" height="48" alt="Docker" />
      <br>Docker
    </td>
    <td align="center" width="96">
      <img src="https://skillicons.dev/icons?i=tailwind" width="48" height="48" alt="Tailwind" />
      <br>Tailwind
    </td>
  </tr>
</table>

## 프로젝트 구조

```
trend-ai-studio/
├── backend/               # FastAPI 백엔드
│   ├── app/
│   │   ├── api/          # API 라우트
│   │   ├── models/       # SQLModel 모델
│   │   ├── services/     # 비즈니스 로직
│   │   │   ├── agent/    # LangGraph 워크플로우
│   │   │   ├── crawler/  # RSS, Playwright
│   │   │   └── vector/   # 임베딩
│   │   └── tasks/        # 스케줄러
│   └── alembic/          # 마이그레이션
├── frontend/             # Next.js 프론트엔드
├── docs/                 # 문서
└── docker-compose.yml
```

## 빠른 시작

### 1. Supabase 로컬 시작

```bash
supabase start
```

### 2. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # API 키 설정
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

> 자세한 설치 방법은 [설치 가이드](docs/SETUP.md) 참조

## 워크플로우

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌─────────┐
│  소스   │ -> │ 크롤러  │ -> │ 벡터 DB  │ -> │ 에이전트│ -> │  게시   │
└─────────┘    └─────────┘    └──────────┘    └─────────┘    └─────────┘
     │              │              │               │              │
   RSS/Web      수집/저장      중복체크        분석/생성      Threads
```

| 단계 | 설명 |
|------|------|
| Crawler | RSS/웹사이트에서 콘텐츠 수집 (1-5분 주기) |
| Vector DB | 중복 체크 및 임베딩 저장 |
| Agent | LangGraph로 분석/요약/콘텐츠 생성 |
| Review | 대시보드에서 검토 (선택적) |
| Publish | Threads API로 게시 |
| Notify | Discord/Telegram 알림 |

## 브랜치 전략

| 브랜치 | 용도 |
|--------|------|
| `main` | 프로덕션 |
| `dev` | 개발 통합 |
| `feature/*` | 기능 개발 |

## API 문서

Backend 실행 후: http://localhost:8000/docs

---

<p align="center">
  <sub>Built with FastAPI + LangGraph + Threads API</sub>
</p>
