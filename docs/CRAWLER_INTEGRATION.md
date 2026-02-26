# Crawler Team Integration Guide

## 크롤러팀 통합 가이드

크롤링 후 파이프라인에 컨텐츠를 넘기는 방법입니다.

## 통합 방법

### 1. HTTP API 호출 (권장)

크롤링 완료 후 바로 API 호출:

```python
import httpx
from app.models.source import CrawledContent

async def after_crawl_complete(content: CrawledContent):
    """
    크롤링 완료 후 파이프라인에 전달
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"http://localhost:8001/api/content/process/{content.id}",
                timeout=60.0  # Agent 실행 시간 고려
            )

            result = response.json()

            if result["urgency"] == "urgent":
                print(f"✅ 긴급 컨텐츠 즉시 처리됨: {content.title}")
                print(f"   상태: {result['agent_result']['status']}")

            elif result["status"] == "duplicate":
                print(f"⚠️  중복 감지: {content.title}")
                print(f"   원본: {result['duplicate_of']}")

            elif result["status"] == "embedded":
                print(f"📦 일반 컨텐츠 임베딩 완료: {content.title}")
                # 에이전트는 별도 스케줄러가 실행

        except httpx.TimeoutError:
            print(f"⏱️  타임아웃 (에이전트 실행 중일 수 있음): {content.title}")

        except Exception as e:
            print(f"❌ 파이프라인 호출 실패: {e}")
```

### 2. 직접 함수 호출 (같은 프로세스인 경우)

```python
from app.services.vector.pipeline import EmbeddingPipeline
from app.core.database import get_session

async def process_crawled_content_directly(content_id: str):
    """
    같은 FastAPI 앱 내에서 직접 호출
    """
    async for session in get_session():
        pipeline = EmbeddingPipeline()
        result = await pipeline.process_crawled_content(session, content_id)
        return result
```

## 필수 필드 설정

크롤링 시 이 필드들을 반드시 설정해주세요:

```python
content = CrawledContent(
    # 필수 필드
    id=str(uuid.uuid4()),
    source_id="source-uuid",
    title="Article title",
    content="Full article text...",
    source_url="https://...",  # UNIQUE - 중복 방지용
    published_at=datetime.utcnow(),

    # 분류 필드 (파이프라인 최적화용)
    content_type=ContentType.BREAKING_NEWS,  # 긴급 분류에 사용
    category_hint=CategoryHint.LLM,

    # 메타데이터 (있으면 좋음)
    source_type=SourceType.HTML_ARTICLE,
    source_name="TechCrunch",
    canonical_url="https://...",
    fetched_at=datetime.utcnow(),
    author="John Doe",
    language="en",
    tags=["AI", "GPT", "OpenAI"],

    # 컨텐츠 구조 (선택)
    image_urls=["https://..."],
    outbound_urls=["https://..."],

    # 원본 데이터 보존
    raw_payload={"og_title": "...", "og_description": "..."}
)
```

## 응답 처리

### 긴급 컨텐츠

```json
{
  "status": "urgent_processed",
  "urgency": "urgent",
  "agent_result": {
    "status": "generated",
    "content": ["Thread text..."],
    "link": "https://...",
    "hashtags": ["AI"]
  }
}
```

### 일반 컨텐츠

```json
{
  "status": "embedded",
  "urgency": "normal",
  "content_id": "uuid"
}
```

### 중복 감지

```json
{
  "status": "duplicate",
  "duplicate_of": "original-uuid"
}
```

## 에러 처리

```python
async def safe_process(content_id: str):
    try:
        response = await client.post(f"/api/content/process/{content_id}")
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"컨텐츠를 찾을 수 없음: {content_id}")
        elif e.response.status_code == 500:
            print(f"서버 에러: {e.response.json()}")

    except httpx.TimeoutError:
        print(f"타임아웃 - 백그라운드에서 처리 중일 수 있음")

    except Exception as e:
        print(f"알 수 없는 에러: {e}")
```

## 권장 워크플로우

```python
async def crawl_and_process():
    # 1. 크롤링
    raw_data = await crawl_source("https://techcrunch.com")

    # 2. DB 저장
    content = CrawledContent(
        title=raw_data["title"],
        content=raw_data["content"],
        ...
    )
    session.add(content)
    await session.commit()

    # 3. 파이프라인 트리거 (비동기)
    # 방법 A: Fire and forget
    asyncio.create_task(trigger_pipeline(content.id))

    # 방법 B: 결과 대기
    result = await trigger_pipeline(content.id)
    if result["status"] == "duplicate":
        # 중복이면 DB에서 삭제 또는 마킹
        await session.delete(content)
        await session.commit()
```

## 배치 처리

여러 컨텐츠를 한번에 크롤링한 경우:

```python
async def batch_crawl_and_process():
    contents = await crawl_multiple_sources()

    # DB에 저장
    for content in contents:
        session.add(content)
    await session.commit()

    # 파이프라인에 병렬 전달
    tasks = [
        trigger_pipeline(content.id)
        for content in contents
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 결과 처리
    for content, result in zip(contents, results):
        if isinstance(result, Exception):
            print(f"처리 실패: {content.title} - {result}")
        elif result.get("status") == "duplicate":
            print(f"중복: {content.title}")
```

## 성능 고려사항

### 긴급 컨텐츠
- 동기 처리 (응답 대기: 3-5초)
- 즉시 에이전트 실행
- Tavily 웹서치 포함 시 최대 10초

### 일반 컨텐츠
- 비동기 처리 권장
- 임베딩만: 1-2초
- 에이전트는 별도 스케줄러가 처리

### 추천 설정

```python
# 타임아웃 설정
URGENT_TIMEOUT = 15.0  # 긴급 컨텐츠
NORMAL_TIMEOUT = 5.0   # 일반 컨텐츠 (임베딩만)

# 동시 처리 제한
MAX_CONCURRENT_PIPELINE = 10  # 동시에 10개까지만
```

## 모니터링

파이프라인 상태 확인:

```bash
# 통계 확인
curl http://localhost:8001/api/content/stats

# 응답:
{
  "by_status": {
    "PENDING": 5,
    "ANALYZING": 12,
    "READY": 3,
    "PUBLISHED": 45,
    "FAILED": 8
  },
  "by_content_type": {
    "BREAKING_NEWS": 10,
    "MODEL_RELEASE": 5,
    "GENERAL": 45
  },
  "today": {
    "total_crawled": 68,
    "duplicates": 8,
    "unique": 60
  }
}
```

## 문제 해결

### 중복이 너무 많이 감지됨
- 유사도 threshold를 조정: `threshold=0.9` → `0.95`
- `backend/app/services/vector/pipeline.py` 수정

### 긴급 분류가 잘못됨
- 키워드 목록 확인: `pipeline.py`의 `urgent_keywords`
- `ContentType` 확인: BREAKING_NEWS, MODEL_RELEASE 등

### 파이프라인이 느림
- 일반 컨텐츠는 비동기 처리 (fire and forget)
- 긴급만 동기 처리

## 질문/이슈

파이프라인 관련 문제는 에이전트팀(이성민)에게 문의:
- 중복 감지 threshold 조정
- 긴급 분류 로직 수정
- 성능 최적화

DB 스키마 관련은 크롤러팀 담당:
- CrawledContent 필드 추가/수정
- 인덱스 추가
