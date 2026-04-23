# How to Run

## Prerequisites

- Docker Desktop installed
- Git installed

## First time setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd mmm-platform

# 2. Copy environment file
cp .env.example .env

# 3. Place CSV files in /data folder
#    dt_simulated_weekly.csv
#    dt_prophet_holidays.csv
#    df_curve_reach_freq.csv

# 4. Start all services
docker-compose up --build
```

## Load the data

```bash
docker exec mmm_db python load_data.py
```

## Run the model

```bash
docker exec mmm_ds python models/baseline.py
```

## Run the full pipeline via Prefect

```bash
docker exec mmm_orch python pipeline_flow.py
```

## URLs

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API (Swagger) | http://localhost:8000/docs |
| Prefect UI | http://localhost:4200 |
| Docs | http://localhost:8080 |

## Useful commands

```bash
docker-compose ps                    # check all services
docker-compose logs -f ds            # live logs for one service
docker-compose down -v               # stop and delete data
docker-compose up --build back       # rebuild one service
```
