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

백엔드만 실행:

```bash
cp .env.example .env
docker compose up --build backend
```

백엔드와 프론트엔드를 같은 MSA 네트워크에서 실행:

```bash
docker compose --profile msa up --build
```

기본 프론트엔드 경로는 `../WhyHouse_Front`입니다. 다른 위치를 사용할 때는 `.env`의 `FRONTEND_CONTEXT`를 수정합니다.

## Documents

- [Project Summary](docs/project-summary.md)
- [Backend Architecture](docs/backend-architecture.md)
- [API Contract](docs/api-contract.md)
- [Data Scope](docs/data-scope.md)
