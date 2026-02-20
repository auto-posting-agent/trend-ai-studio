# 설치 가이드

> 최종 수정: 2026-02-21

## 필수 조건

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose
- Supabase CLI

## 1. Supabase 로컬 설정

### 1.1 Supabase CLI 설치

```bash
# macOS
brew install supabase/tap/supabase

# npm
npm install -g supabase
```

### 1.2 로컬 Supabase 시작

```bash
# 프로젝트 루트에서
supabase start
```

실행 후 출력되는 정보:
- API URL: `http://localhost:54321`
- DB URL: `postgresql://postgres:postgres@localhost:54322/postgres`
- Studio URL: `http://localhost:54323`
- anon key: 출력된 값 복사

### 1.3 pgvector 확장 활성화

Supabase Studio (`http://localhost:54323`) 접속 후 SQL Editor에서:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## 2. 백엔드 설정

### 2.1 Python 가상환경

```bash
cd backend
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 2.2 의존성 설치

```bash
pip install -r requirements.txt
```

### 2.3 Playwright 브라우저 설치

```bash
playwright install chromium
```

### 2.4 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일 수정:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:54322/postgres
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=<supabase start 출력값>
GEMINI_API_KEY=<발급받은 키>
TAVILY_API_KEY=<발급받은 키>
THREADS_ACCESS_TOKEN=<발급받은 토큰>
```

### 2.5 데이터베이스 마이그레이션

```bash
# 마이그레이션 생성
alembic revision --autogenerate -m "initial"

# 마이그레이션 적용
alembic upgrade head
```

### 2.6 서버 실행

```bash
uvicorn app.main:app --reload --port 8000
```

API 문서: `http://localhost:8000/docs`

## 3. 프론트엔드 설정

### 3.1 의존성 설치

```bash
cd frontend
npm install
```

### 3.2 환경 변수 설정

```bash
cp .env.example .env.local
```

### 3.3 개발 서버 실행

```bash
npm run dev
```

`http://localhost:3000` 에서 확인

## 4. Docker 설정 (선택)

전체 스택을 Docker로 실행:

```bash
# 프로젝트 루트에서
docker-compose up -d
```

개별 서비스:
```bash
docker-compose up backend -d
docker-compose up frontend -d
```

## 5. API 키 발급

### Gemini API
1. https://aistudio.google.com/apikey 접속
2. API Key 생성

### Tavily API
1. https://tavily.com 가입
2. Dashboard에서 API Key 복사

### Threads API
1. https://developers.facebook.com 접속
2. 앱 생성 -> Threads API 추가
3. Access Token 발급

## 문제 해결

### Supabase 연결 실패
```bash
supabase stop
supabase start
```

### Alembic 마이그레이션 충돌
```bash
# 모든 마이그레이션 삭제 후 재생성
rm -rf alembic/versions/*
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

### 포트 충돌
```bash
# 사용 중인 포트 확인
lsof -i :8000
lsof -i :3000
```
