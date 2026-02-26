# Trend AI Studio - Complete Setup Guide

## Overview
Trend AI Studio는 크롤링한 콘텐츠를 AI로 분석하여 Threads용 게시물을 자동 생성하고 발행하는 플랫폼입니다.

## 플랫폼 워크플로우

```
1. 콘텐츠 크롤링 (Sources)
   ↓
2. AI 분석 및 게시물 생성 (Generate 버튼)
   ↓
3. 사용자 검토 (Review Modal)
   ↓
4. Threads 발행 (Approve & Publish 버튼)
   ↓
5. 게시물 추적 및 분석
```

## 백엔드 API 엔드포인트

### 1. 콘텐츠 조회
```http
GET /api/content/
Query Parameters:
  - status: pending | ready | published | failed
  - content_type: article | video | image
  - limit: 50 (default)
  - offset: 0 (default)
```

### 2. 통계 조회
```http
GET /api/content/stats

Response:
{
  "by_status": {
    "pending": 10,
    "ready": 5,
    "published": 20
  },
  "by_content_type": {...},
  "today": {
    "total_crawled": 15,
    "duplicates": 2,
    "unique": 13
  }
}
```

### 3. 게시물 생성 (AI 워크플로우 실행)
```http
POST /api/content/process/{content_id}

Response:
{
  "status": "success",
  "content_id": "uuid",
  "generated_post": "AI가 생성한 Threads 게시물 텍스트"
}
```

### 4. 게시물 승인 및 Threads 발행
```http
POST /api/content/{content_id}/approve

Response:
{
  "status": "published",
  "content_id": "uuid",
  "message": "Content published to Threads successfully",
  "thread_url": "https://www.threads.net/@username/post/xxx"
}
```

### 5. 게시물 거절
```http
POST /api/content/{content_id}/reject
Body: { "reason": "사유" }

Response:
{
  "status": "rejected",
  "content_id": "uuid",
  "reason": "사유"
}
```

## Threads API 연동 설정

### 1. Meta Developer 계정 생성
1. https://developers.facebook.com/ 접속
2. "내 앱" → "앱 만들기" 클릭
3. 앱 유형: "비즈니스" 선택
4. 앱 정보 입력

### 2. Threads API 제품 추가
1. 앱 대시보드에서 "제품 추가" 클릭
2. "Threads" 찾아서 "설정" 클릭
3. 권한 선택:
   - `threads_basic` - 기본 읽기 권한
   - `threads_content_publish` - 게시물 작성 및 발행
   - `threads_manage_insights` - 분석 데이터 (선택사항)

### 3. 인증 정보 획득

#### 앱 ID 및 Secret
앱 설정 → 기본 → 복사:
- **앱 ID** → `.env`의 `THREADS_APP_ID`
- **앱 시크릿** → `.env`의 `THREADS_APP_SECRET`

#### Access Token 생성 (테스트용 - 1-2시간 유효)
1. Graph API 탐색기: https://developers.facebook.com/tools/explorer/
2. 앱 선택
3. "액세스 토큰 생성" 클릭
4. 권한 선택: `threads_basic`, `threads_content_publish`
5. 토큰 복사 → `.env`의 `THREADS_ACCESS_TOKEN`

#### Long-Lived Token 생성 (프로덕션용 - 60일 유효)
```bash
# 1. 단기 토큰을 장기 토큰으로 교환
curl -X GET "https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret={app-secret}&access_token={short-lived-token}"
```

### 4. 환경 변수 설정
`.env` 파일에 추가:
```env
# Threads API
THREADS_APP_ID=your_app_id
THREADS_APP_SECRET=your_app_secret
THREADS_ACCESS_TOKEN=your_access_token

# Gemini AI (게시물 생성용)
GEMINI_API_KEY=your_gemini_key

# Tavily Search (팩트체크용)
TAVILY_API_KEY=your_tavily_key

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:54322/postgres

# Qdrant Vector DB (유사도 검색용)
QDRANT_URL=http://localhost:6333
```

### 5. 테스트
```python
# backend/test_threads.py
import asyncio
from app.services.threads import ThreadsPublisher

async def test():
    publisher = ThreadsPublisher()
    user_id = await publisher.get_user_id()
    print(f"User ID: {user_id}")

    result = await publisher.create_text_post(
        user_id=user_id,
        text="🤖 테스트 게시물"
    )
    print(f"Success: {result}")

asyncio.run(test())
```

## 프론트엔드 연동

### API 클라이언트 사용
```typescript
// frontend/src/lib/api.ts에 이미 구현됨

// 콘텐츠 목록 조회
const { items } = await contentAPI.listContent({ limit: 10 });

// 게시물 생성
const result = await contentAPI.processContent(content_id);

// 게시물 조회
const detail = await contentAPI.getContent(content_id);

// Threads에 발행
const publishResult = await contentAPI.approveContent(content_id);
```

### 대시보드 워크플로우
1. **콘텐츠 리스트 표시**: `loadData()` 함수가 30초마다 자동 새로고침
2. **Generate 버튼**: 'pending' 상태 콘텐츠에만 표시
3. **모달 표시**: 생성된 게시물, AI 분석, 팩트체크 결과 표시
4. **Approve & Publish**: Threads에 실제 발행

## 실행 방법

### Docker로 실행 (권장)
```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일 편집하여 API 키 입력

# 2. Docker 컨테이너 실행
docker-compose up -d

# 3. 데이터베이스 마이그레이션
docker exec trend-ai-backend alembic upgrade head

# 4. 접속
# Frontend: http://localhost:3001
# Backend: http://localhost:8001/docs
```

### 로컬 개발
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Frontend (새 터미널)
cd frontend
npm install
npm run dev
```

## API Rate Limits
- **시간당**: 250 게시물
- **일일**: 1000 게시물
- **텍스트 길이**: 최대 500자
- **이미지**: 캐러셀당 최대 10개

## 문제 해결

### "Invalid access token"
- 토큰 만료 → OAuth 흐름으로 재생성
- 권한 확인 필요

### "User not authorized"
- Instagram 계정이 Professional/Creator 계정인지 확인
- 앱이 개발 모드가 아닌지 확인

### "Rate limit exceeded"
- 요청 대기 후 재시도
- 게시물 큐잉 시스템 구현 고려

## 추가 리소스
- [Threads API Docs](https://developers.facebook.com/docs/threads)
- [Meta for Developers](https://developers.facebook.com/)
- [프로젝트 README](../README.md)
- [파이프라인 아키텍처](./PIPELINE_ARCHITECTURE.md)
