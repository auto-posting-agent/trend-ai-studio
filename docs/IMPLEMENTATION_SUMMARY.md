# Implementation Summary - Pipeline with Urgency Routing

## 구현 완료

다이어그램대로 긴급/일반 분류 파이프라인 구현 완료했습니다.

## 구조

```
크롤링
  ↓
필터링: 긴급 vs 일반
  ↓              ↓
긴급             일반
(바로 에이전트)   (DB 저장 + 임베딩)
  ↓              ↓
  └─ 벡터 검색 ──┘
  └─ 웹서치 (Tavily)
       ↓
   게시물 생성
```

## 주요 변경사항

### 1. 긴급 분류 로직 ([backend/app/services/vector/pipeline.py](../backend/app/services/vector/pipeline.py))

```python
def _classify_urgency(self, content: CrawledContent) -> str:
    """
    긴급 조건:
    - content_type: BREAKING_NEWS, MODEL_RELEASE, TOOL_LAUNCH
    - 키워드: "breaking", "just released", "announces", "launched" 등

    일반: 나머지 모든 컨텐츠
    """
```

### 2. 분기 처리

**긴급 (Urgent)**
- 임베딩 스킵
- 바로 에이전트 워크플로우 실행
- 빠른 처리 (시간 민감성)

**일반 (Normal)**
- 임베딩 파이프라인 거침
- 중복 체크 (벡터 유사도 0.9 이상 → FAILED)
- 임베딩 저장
- 에이전트는 별도로 실행 (비동기)

### 3. 지식 베이스 (Vector Search)

**Search Node에서 2단계 검색**:

1. **벡터 검색** (항상 실행)
   - 과거 유사 컨텐츠 5개 찾기
   - 유사도 threshold: 0.7
   - 목적: 컨텍스트 제공

2. **웹 서치** (조건부)
   - Tavily API 사용
   - 조건: breaking_news, stock, crypto, model_release
   - 최대 3개 결과
   - 도메인: GitHub, TechCrunch, Bloomberg 등

### 4. API 엔드포인트 ([backend/app/api/routes/content.py](../backend/app/api/routes/content.py))

```bash
# 크롤러팀이 호출할 엔드포인트
POST /api/content/process/{content_id}

# 프론트엔드용 엔드포인트
GET  /api/content?status=READY&limit=50
GET  /api/content/stats
GET  /api/content/{content_id}
POST /api/content/{content_id}/approve
POST /api/content/{content_id}/reject
```

## 사용법

### 크롤러팀 통합

크롤링 후 바로 호출:

```python
import httpx

async def after_crawl(content_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8001/api/content/process/{content_id}"
        )
        result = response.json()

        if result["urgency"] == "urgent":
            print(f"Urgent content processed: {result['agent_result']}")
        elif result["status"] == "duplicate":
            print(f"Duplicate detected: {result['duplicate_of']}")
        else:
            print(f"Normal content embedded: {result['content_id']}")
```

### 프론트엔드에서 모니터링

```typescript
// 승인 대기 중인 컨텐츠 가져오기
const response = await fetch('/api/content?status=READY&limit=50')
const { items } = await response.json()

// 통계 확인
const stats = await fetch('/api/content/stats')
const { by_status, by_content_type, today } = await stats.json()

console.log(`Today: ${today.total_crawled} crawled, ${today.duplicates} duplicates`)

// 승인/거부
await fetch(`/api/content/${contentId}/approve`, { method: 'POST' })
await fetch(`/api/content/${contentId}/reject`, {
  method: 'POST',
  body: JSON.stringify({ reason: '중복 내용' })
})
```

## 비용 최적화

### 긴급 컨텐츠
- 임베딩 스킵 → $0.000001 절감
- 예상: 전체 컨텐츠의 10-20%

### 웹 서치
- 조건부 실행 (breaking news, stocks, model releases만)
- 예상: 전체 컨텐츠의 30%만 웹서치

### 결과
- 월 예상 비용: **$0.39** (100개/일 기준)
- 긴급 라우팅: 10% 추가 절감

## 파일 변경 사항

### 수정된 파일
1. `backend/app/services/vector/pipeline.py`
   - `_classify_urgency()` 추가
   - `process_crawled_content()` 분기 로직 추가

2. `backend/app/services/agent/workflow.py`
   - `_search_node()` 주석 개선 (지식 베이스 개념 명확화)
   - 웹서치 도메인 추가 (theverge, venturebeat)

3. `backend/app/main.py`
   - content router 추가
   - CORS에 3001 포트 추가

### 새로 생성된 파일
1. `backend/app/api/routes/content.py` - API 엔드포인트
2. `docs/PIPELINE_ARCHITECTURE.md` - 아키텍처 문서
3. `docs/IMPLEMENTATION_SUMMARY.md` - 이 문서

## 테스트

### 긴급 컨텐츠 테스트

```python
# backend/tests/test_pipeline_urgency.py
async def test_urgent_path():
    content = CrawledContent(
        title="OpenAI announces GPT-5",
        content="Breaking: OpenAI just released...",
        content_type=ContentType.BREAKING_NEWS,
        ...
    )

    result = await pipeline.process_crawled_content(session, content.id)

    assert result["urgency"] == "urgent"
    assert "agent_result" in result
    assert result["status"] == "urgent_processed"
```

### 일반 컨텐츠 테스트

```python
async def test_normal_path_with_embedding():
    content = CrawledContent(
        title="Regular tech news",
        content="Today in tech...",
        content_type=ContentType.GENERAL,
        ...
    )

    result = await pipeline.process_crawled_content(session, content.id)

    assert result["urgency"] == "normal"
    assert result["status"] == "embedded"

    # Check embedding exists
    embedding = await session.get(ContentEmbedding, content.id)
    assert embedding is not None
```

### 중복 감지 테스트

```python
async def test_duplicate_detection():
    # Create first content
    content1 = create_content("OpenAI releases GPT-5")
    await pipeline.process_crawled_content(session, content1.id)

    # Create very similar content
    content2 = create_content("OpenAI announces GPT-5 launch")
    result = await pipeline.process_crawled_content(session, content2.id)

    assert result["status"] == "duplicate"
    assert result["duplicate_of"] == content1.id
```

## 다음 단계

### 1. 에이전트 워크플로우 자동 트리거
현재는 긴급만 자동 실행, 일반 컨텐츠는 수동 트리거 필요.

```python
# TODO: 스케줄러 추가
# 5분마다 ANALYZING 상태 컨텐츠 가져와서 에이전트 실행
```

### 2. 웹훅 통합
```python
# Discord/Telegram으로 긴급 컨텐츠 알림
if urgency == "urgent" and result["status"] == "generated":
    await send_notification(f"🔴 긴급 포스트 생성됨: {content.title}")
```

### 3. 프론트엔드 구현
- 대시보드 (파이프라인 상태 실시간 표시)
- 컨텐츠 리뷰 피드
- 승인/거부 UI

## API 문서

FastAPI 자동 문서:
```bash
# 서버 실행
docker-compose up backend

# 브라우저에서 열기
http://localhost:8001/docs
```

## 환경변수

`.env` 파일에 추가 필요:

```bash
# 이미 있음
GEMINI_API_KEY=your-key
TAVILY_API_KEY=your-key
REDIS_URL=redis://redis:6379

# 선택 (알림용)
DISCORD_WEBHOOK_URL=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## 마이그레이션 상태

✅ Database schema migration 완료
✅ pgvector extension 활성화
✅ ContentEmbedding 테이블 생성
✅ CrawledContent 12개 컬럼 추가

현재 DB 버전: `a1b2c3d4e5f6`
