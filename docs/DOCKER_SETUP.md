# Docker 개발 환경 가이드

## 필수 요구사항

- Docker Desktop 설치
- Git
- `.env` 파일 (팀원과 공유 필요)

## 초기 세팅

### 1. 저장소 클론
```bash
git clone <repository-url>
cd trend-ai-studio
```

### 2. 환경변수 파일 설정
```bash
cd backend
# .env 파일 생성하고 아래 내용 붙여넣기
```

필요한 환경변수:
```env
DATABASE_URL=postgresql+asyncpg://...
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
GEMINI_API_KEY=...
```

### 3. Docker 컨테이너 빌드 및 실행
```bash
cd ..
docker-compose up --build
```

첫 실행 시 시간이 걸림 (Playwright 브라우저 다운로드 등)

## 일상 작업 명령어

### 컨테이너 시작
```bash
docker-compose up
```

### 백그라운드 실행
```bash
docker-compose up -d
```

### 로그 확인
```bash
# 전체 로그
docker-compose logs -f

# 백엔드만
docker-compose logs -f backend

# 프론트엔드만
docker-compose logs -f frontend
```

### 컨테이너 중지
```bash
docker-compose down
```

### 컨테이너 재시작
```bash
docker-compose restart
```

## 접속 주소

- Frontend: http://localhost:3001
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs

## 개발 작업

### 컨테이너 내부 접속
```bash
docker exec -it trend-ai-backend bash
```

### 마이그레이션 실행
```bash
docker exec -it trend-ai-backend alembic upgrade head
```

### 크롤러 단독 실행
```bash
docker exec -it trend-ai-backend python -m app.services.crawler.rss
```

### Python 패키지 추가
```bash
# 1. requirements.txt에 패키지 추가
echo "new-package>=1.0.0" >> backend/requirements.txt

# 2. 컨테이너 재빌드
docker-compose up --build backend
```

## 문제 해결

### 포트 충돌
다른 프로세스가 8001 또는 3001 포트를 사용 중일 때:
```bash
# Mac/Linux
lsof -ti:8001 | xargs kill -9
lsof -ti:3001 | xargs kill -9

# 또는 docker-compose.yml에서 포트 변경
```

### 컨테이너 완전 초기화
```bash
docker-compose down -v
docker-compose up --build
```

### 로그 확인이 안 될 때
```bash
docker-compose logs --tail=100 backend
```

## venv vs Docker

| 항목 | venv | Docker |
|------|------|--------|
| Python 버전 통일 | X | O |
| 패키지 버전 충돌 | 가능 | 없음 |
| 초기 설정 시간 | 빠름 | 느림 |
| 팀원 환경 통일 | 어려움 | 쉬움 |
| 디버깅 | 쉬움 | 중간 |
| 프로덕션 배포 | 별도 작업 | 동일 이미지 사용 |

Docker 사용 권장.
