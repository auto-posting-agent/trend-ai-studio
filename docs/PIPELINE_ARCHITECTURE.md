# Pipeline Architecture

## Overview

Automated content pipeline for Threads auto-posting with urgency-based routing and AI-powered content generation.

## Pipeline Flow

```
크롤링 (Crawler Team)
  ↓
DB 저장 (CrawledContent)
  ↓
필터링: 긴급 vs 일반
  ↓              ↓
긴급             일반
  ↓              ↓
  │          임베딩 파이프라인
  │              ├─ 해시 생성
  │              ├─ 중복 체크 (벡터 유사도)
  │              └─ 임베딩 저장
  │              ↓
  └──────────────┘
         ↓
  에이전트 워크플로우
         ↓
    Search Node
    ├─ 벡터 검색 (지식 베이스)
    └─ 웹 서치 (Tavily, 조건부)
         ↓
    Analyze Node
    (Gemini Flash)
         ↓
  should_publish?
    ↙         ↘
  YES         NO
   ↓          ↓
Generate    SKIP
(Gemini Pro)
   ↓
게시물 생성
```

## Components

### 1. Urgency Classification

**Urgent (긴급)**
- Breaking news
- Major model releases
- Tool launches
- Keywords: "breaking", "just released", "announces", etc.

**Path**: Skip embedding → Direct to agent
**Reason**: Immediate processing for time-sensitive content

**Normal (일반)**
- Regular updates
- Community posts
- General news

**Path**: Full pipeline with embedding
**Reason**: Duplicate detection and knowledge base building

### 2. Embedding Pipeline

**File**: `backend/app/services/vector/pipeline.py`

**Process**:
1. Fetch content from DB
2. Generate SHA256 hash
3. Classify urgency
4. **If urgent**: Go to agent immediately
5. **If normal**:
   - Check duplicates via vector search (threshold: 0.9)
   - If duplicate: Mark as FAILED
   - If unique: Embed and store in pgvector
   - Then proceed to agent

### 3. Agent Workflow

**File**: `backend/app/services/agent/workflow.py`

**Nodes**:

#### Search Node
```python
# Phase 1: Vector Search (지식 베이스)
- Query: Raw content
- Limit: 5 similar posts
- Threshold: 0.7 similarity
- Purpose: Get context from past content

# Phase 2: Web Search (Tavily)
- Conditional: Only for breaking news, stocks, crypto, model releases
- Mode: Basic (cost-efficient)
- Max results: 3
- Domains: GitHub, TechCrunch, Bloomberg, etc.
```

#### Analyze Node
```python
# Model: Gemini 2.0 Flash (cost-effective)
# Input:
- Raw content
- Similar posts (from vector search)
- Web search results (if available)

# Output:
{
  "should_publish": true/false,
  "skip_reason": "...",
  "content_type": "...",
  "key_points": [...],
  "suggested_angle": "...",
  "target_audience": "...",
  "urgency": "high/medium/low"
}
```

#### Generate Node
```python
# Model: Gemini 1.5 Pro (quality)
# Only runs if should_publish = true

# Output:
{
  "main_thread": "...",
  "follow_up_thread": "...",  # Optional
  "link": "...",
  "hashtags": [...]
}
```

## Cost Optimization

### Urgency Routing
- Urgent content (10-20% of total): Skip embedding → Save $0.000001 per item
- Normal content: Full pipeline with duplicate detection

### Web Search
Only enabled for:
- Breaking news
- Stock/crypto updates
- Model releases

**Estimated savings**: 70% reduction in Tavily costs

### Model Selection
- Analysis: Gemini 2.0 Flash ($0.00001 per request)
- Generation: Gemini 1.5 Pro ($0.0001 per request)

### Caching
- Redis cache for embeddings (7-day TTL)
- Avoids re-embedding similar content

## Database Schema

### CrawledContent
```python
id: str
title: str
content: str
content_hash: str  # SHA256 for duplicate detection
source_type: SourceType  # HTML_ARTICLE, RSS_ENTRY, etc.
content_type: ContentType  # BREAKING_NEWS, MODEL_RELEASE, etc.
category_hint: CategoryHint  # LLM, HARDWARE, STOCK, etc.
thread_status: ThreadStatus  # PENDING → ANALYZING → READY → PUBLISHED
extra_data: dict  # Metadata like duplicate_of
```

### ContentEmbedding
```python
content_id: str  # FK to CrawledContent
embedding: Vector(768)  # pgvector
extra_data: dict  # Metadata (title, source_url, category, etc.)
created_at: datetime
```

## Integration Points

### Crawler Team
After crawling, call:
```python
from app.services.vector.pipeline import EmbeddingPipeline

pipeline = EmbeddingPipeline()
result = await pipeline.process_crawled_content(session, content_id)
```

**Response**:
```json
{
  "status": "urgent_processed",  // or "embedded" or "duplicate"
  "urgency": "urgent",  // or "normal"
  "agent_result": {...}  // If urgent
}
```

### Frontend
Monitor pipeline via:
```python
GET /api/content?status=ANALYZING
GET /api/content?status=READY
GET /api/stats
```

## Monitoring

### Key Metrics
- Crawled per day
- Duplicates detected
- Urgent vs Normal ratio
- Publish rate (% of analyzed content published)
- API costs per day
- Average processing time

### Cost Tracking
```python
from app.services.monitoring import WorkflowMonitor

monitor = WorkflowMonitor()
await monitor.log_execution(
    content_id=...,
    status="generated",
    duration=2.5,
    api_costs={
        "gemini_flash": 0.00001,
        "gemini_pro": 0.0001,
        "tavily": 0.001,
        "embedding": 0.000001
    }
)
```

## Error Handling

### Duplicate Detection
- Vector similarity > 0.9 → Mark as FAILED
- Store duplicate_of in extra_data

### Analysis Failure
- Catch exceptions → Set should_publish = false
- Skip reason: "analysis_error"

### Generation Failure
- Catch exceptions → Return error status
- Retry logic with exponential backoff (max 3 attempts)

## Testing

### Unit Tests
```bash
pytest backend/tests/test_pipeline.py -v
```

### Integration Test
```python
# Test urgent path
content = create_urgent_content()
result = await pipeline.process_crawled_content(session, content.id)
assert result["urgency"] == "urgent"
assert "agent_result" in result

# Test normal path with duplicate
content1 = create_normal_content()
content2 = create_similar_content()
await pipeline.process_crawled_content(session, content1.id)
result = await pipeline.process_crawled_content(session, content2.id)
assert result["status"] == "duplicate"
```

## Future Enhancements

1. **Dynamic Urgency Scoring**: ML model to predict urgency score (0-1)
2. **A/B Testing**: Test different prompts and measure engagement
3. **Personalization**: User preferences for content types
4. **Multi-language**: Support Korean, Japanese content
5. **Image Generation**: Auto-generate thumbnails/infographics
