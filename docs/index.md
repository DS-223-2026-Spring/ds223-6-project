# MMM Platform

Marketing Mix Modeling Platform — containerized analytics application.

## Services

| Service | Port | Purpose |
|---------|------|---------|
| `db` | 5432 | PostgreSQL database |
| `ds` | — | Data science pipeline |
| `back` | 8000 | FastAPI backend ([Swagger](http://localhost:8000/docs)) |
| `front` | 3000 | React dashboard |
| `orch` | 4200 | Prefect orchestration UI |
| `docs` | 8080 | This documentation |

## Quick start

```bash
cp .env.example .env
docker-compose up --build
```
