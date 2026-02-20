# Trend AI Studio - Frontend

Next.js 기반 AI 트렌드 분석 대시보드

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State**: React Query (TanStack Query)
- **UI Components**: shadcn/ui (추후 추가)

## Setup

### 1. 환경 변수

```bash
cp .env.example .env.local
```

### 2. 의존성 설치

```bash
npm install
```

### 3. 개발 서버 실행

```bash
npm run dev
```

http://localhost:3000 에서 확인

## Project Structure

```
frontend/
├── src/
│   ├── app/                 # App Router 페이지
│   │   ├── layout.tsx
│   │   ├── page.tsx         # 메인 대시보드
│   │   ├── threads/         # 스레드 관리
│   │   └── sources/         # 소스 관리
│   ├── components/
│   │   ├── ui/              # 공통 UI 컴포넌트
│   │   └── features/        # 기능별 컴포넌트
│   ├── lib/
│   │   ├── api.ts           # API 클라이언트
│   │   └── utils.ts
│   └── types/               # TypeScript 타입
├── public/
└── package.json
```

## Scripts

```bash
# 개발
npm run dev

# 빌드
npm run build

# 프로덕션 실행
npm start

# 린트
npm run lint
```

## Features (예정)

- 대시보드: 크롤링 현황, 게시 통계
- 소스 관리: RSS/웹사이트 추가/삭제
- 스레드 관리: 생성된 콘텐츠 검토/수정/게시
- 스케줄러: 자동화 설정
- 알림 설정: Discord/Telegram 연동
