# 역할 분담 가이드

> 최종 수정: 2026-02-21

## 브랜치 전략

```
main          <- 프로덕션
  └── dev     <- 개발 통합
       ├── feature/crawler      <- 동료
       └── feature/agent        <- 본인
```

```bash
# dev 브랜치 생성
git checkout -b dev
git push -u origin dev

# 각자 feature 브랜치 생성
git checkout -b feature/crawler   # 동료
git checkout -b feature/agent     # 본인
```

---

## 동료 담당: Crawler

### 브랜치
```bash
git checkout -b feature/crawler
```

### 작업 파일
```
backend/app/services/crawler/
├── base.py              # 수정: 크롤러 공통 로직
├── rss.py               # 구현: RSS 크롤러
└── playwright_scraper.py # 구현: Playwright 크롤러

backend/app/tasks/
└── scheduler.py         # 수정: APScheduler 크롤링 작업 등록

backend/app/api/routes/
├── sources.py           # 수정: 소스 CRUD API 구현
└── scheduler.py         # 수정: 스케줄러 API 구현
```

### 구현 목록

1. **RSS 크롤러** (`rss.py`)
   - feedparser로 RSS 피드 파싱
   - CrawledContent 모델에 맞게 데이터 변환
   - 중복 URL 체크

2. **Playwright 크롤러** (`playwright_scraper.py`)
   - 동적 웹사이트 크롤링
   - 쿠키 인증 처리
   - 이미지 URL 추출

3. **스케줄러** (`scheduler.py`)
   - APScheduler로 주기적 크롤링
   - 소스별 interval 설정
   - 크롤링 후 DB 저장

4. **API 구현** (`sources.py`, `scheduler.py`)
   - 소스 CRUD
   - 수동 크롤링 트리거
   - 스케줄러 시작/중지

### Mock 데이터로 테스트

```python
# backend/app/services/crawler/rss.py
async def crawl(self, url: str, config: dict | None = None) -> List[CrawledContent]:
    # TODO: 실제 구현 전 mock 데이터 반환
    return [
        CrawledContent(
            source_id="test-source",
            title="OpenAI releases GPT-5",
            content="OpenAI has announced...",
            source_url="https://example.com/news/1",
            published_at=datetime.utcnow(),
            category_hint=CategoryHint.LLM,
        )
    ]
```

---

## 본인 담당: Agent Workflow

### 브랜치
```bash
git checkout -b feature/agent
```

### 작업 파일
```
backend/app/services/agent/
├── workflow.py          # 수정: LangGraph 워크플로우 구현
├── nodes/
│   ├── search.py        # 생성: Tavily 검색 노드
│   ├── analyze.py       # 생성: 분석 노드
│   └── generate.py      # 생성: 콘텐츠 생성 노드
└── prompts/
    ├── analyze.py       # 생성: 분석 프롬프트
    └── generate.py      # 생성: 생성 프롬프트 (페르소나)

backend/app/services/vector/
└── embedder.py          # 수정: 임베딩 및 유사도 검색 완성

backend/app/services/publisher/
└── threads.py           # 수정: Threads API 연동 완성

backend/app/api/routes/
└── threads.py           # 수정: 스레드 API 구현
```

### 구현 목록

1. **LangGraph 워크플로우** (`workflow.py`)
   - Search -> Analyze -> Generate 파이프라인
   - 상태 관리

2. **검색 노드** (`nodes/search.py`)
   - Tavily API로 추가 컨텍스트 검색
   - 관련 뉴스/정보 수집

3. **분석 노드** (`nodes/analyze.py`)
   - 트렌드 중요도 판단
   - 카테고리 분류
   - 중복 콘텐츠 필터링 (Vector Search)

4. **생성 노드** (`nodes/generate.py`)
   - 페르소나 기반 콘텐츠 생성
   - Few-shot 프롬프트

5. **Vector Embedder** (`embedder.py`)
   - Gemini 임베딩
   - pgvector 유사도 검색
   - 중복 체크

6. **Threads Publisher** (`threads.py`)
   - 텍스트/이미지 게시
   - 에러 핸들링

### Mock 데이터로 테스트

```python
# 크롤러 없이 테스트
mock_content = CrawledContent(
    source_id="test",
    title="Test Article",
    content="This is test content about AI trends...",
    source_url="https://example.com/test",
    published_at=datetime.utcnow(),
)

workflow = TrendAgentWorkflow()
result = await workflow.run(mock_content.content)
```

---

## 공통 작업

### DB 마이그레이션 (둘 다)
```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### 테스트 실행
```bash
pytest
```

### 코드 포맷팅
```bash
ruff format .
ruff check .
```

---

## 작업 순서

### Week 1
| 본인 | 동료 |
|------|------|
| Vector Embedder 완성 | RSS 크롤러 구현 |
| LangGraph 기본 구조 | Sources API 구현 |

### Week 2
| 본인 | 동료 |
|------|------|
| Search/Analyze 노드 | Playwright 크롤러 |
| Generate 노드 (프롬프트) | 스케줄러 구현 |

### Week 3
| 본인 | 동료 |
|------|------|
| Threads Publisher | 크롤러 테스트/버그 수정 |
| 통합 테스트 | 통합 테스트 |

---

## 통합 포인트

크롤러 -> 에이전트 연결:

```python
# backend/app/tasks/scheduler.py
async def process_crawled_content(content: CrawledContent):
    # 1. Vector DB에 저장 (중복 체크)
    embedder = VectorEmbedder(session)
    similar = await embedder.search_similar(content.title)

    if similar and similar[0]["similarity"] > 0.9:
        return  # 중복, 스킵

    await embedder.embed_and_store(content.id, content.content)

    # 2. Agent 워크플로우 실행
    workflow = TrendAgentWorkflow()
    result = await workflow.run(content.content)

    # 3. Thread 생성
    thread = Thread(
        source_content_id=content.id,
        content=result["generated_content"],
        status=ThreadStatus.READY,
    )
    session.add(thread)
    await session.commit()
```

---

## 커뮤니케이션

- PR 생성 시 상대방 리뷰 요청
- 스키마 변경 시 반드시 공유
- 매일 진행상황 공유 (Discord/Slack)
