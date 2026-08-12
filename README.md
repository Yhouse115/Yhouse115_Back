# WhyHouse Backend

아이 관점의 아파트 생활 인프라와 보행 안전 인사이트를 제공하기 위한 FastAPI 백엔드입니다. 이 레포는 단순 CRUD보다 거리, 반경, 경로, 안전 요소 계산을 담당하는 API 서버를 목표로 합니다.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

## Test

```bash
pytest
```

## Docker Compose

백엔드 레포에서 전체 로컬 스택 실행:

```bash
cp .env.example .env
docker compose up -d --build
```

기본적으로 백엔드 레포와 프론트 레포가 같은 상위 폴더 아래에 있다고 가정합니다.

```text
workspace/
  Yhouse115_Back/
  Yhouse115_Front/
```

프론트 폴더는 `../Yhouse115_Front` 경로에 있어야 합니다.

실행되는 서비스:

- `whyhouse-database`: local PostGIS/Postgres
- `whyhouse-backend`: FastAPI backend
- `whyhouse-frontend`: Vite frontend

DB 연결 확인:

```bash
curl http://localhost:8000/api/v1/system/dependencies
```

종료:

```bash
docker compose down
```

## Runtime Integrations

- Supabase: `.env`의 `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`을 채웁니다.
- Local DB: 기본 compose 값은 `postgresql://whyhouse:whyhouse@database:5432/whyhouse`입니다.
- Naver Maps: `.env`의 `NAVER_MAPS_CLIENT_ID`, `NAVER_MAPS_CLIENT_SECRET`을 채웁니다.
- CI: `.github/workflows/ci.yml`에서 pytest와 Docker image build를 실행합니다.

## Documents

- [Project Summary](docs/project-summary.md)
- [Backend Architecture](docs/backend-architecture.md)
- [API Contract](docs/api-contract.md)
- [Data Scope](docs/data-scope.md)
- [Runtime Integrations](docs/runtime-integrations.md)
