# Frontend Service — React Dashboard

React 18 dashboard for the MMM Platform.
Dev server at http://localhost:3000

## Folder structure

```
front/
├── Dockerfile
├── package.json
├── public/
│   └── index.html
└── src/
    ├── App.js                        # Main app with navigation and page routing
    ├── index.js                      # React entry point
    └── components/
        ├── ApiService.js             # All backend API calls (centralized)
        ├── MetricCard.js             # Reusable KPI summary card
        └── LoadingSpinner.js         # Loading state indicator
```

## Reusable components

| Component | Props | Purpose |
|-----------|-------|---------|
| `MetricCard` | `label`, `value`, `sub` | KPI number card for the overview dashboard |
| `LoadingSpinner` | `message` | Loading indicator during API calls |
| `ApiService` | — | Centralized fetch wrapper for all backend endpoints |

## Data the frontend needs from the backend

### Overview page
- `GET /results` → `{ model_version, r_squared, channels: [{ channel, roi_estimate, contribution_pct }] }`
- `GET /health`  → `{ status, database }`

### Channel deep dive (Sprint 3)
- `GET /results` → `channels[]` with `roi_estimate`, `contribution_pct`, `coefficient`

### Budget optimizer (Sprint 4)
- `POST /optimize` with `{ total_budget: float, constraints?: { channel: { min, max } } }`
- Returns `{ allocation: { channel: amount }, predicted_revenue: float }`
- `POST /scenarios` to save a result
- `GET /scenarios` to list saved results
- `PUT /scenarios/{id}` to rename
- `DELETE /scenarios/{id}` to remove

### Model settings (Sprint 4)
- `GET /model-runs` → `{ runs: [{ id, model_version, status, r_squared, run_at }] }`
- `POST /retrain` to trigger a new run

## How to run

```bash
docker-compose up front
# Dashboard: http://localhost:3000
```
