# Frontend Service

React 18 dashboard — marketing managers interact with model results here.

Dashboard: **http://localhost:3000**

## Pages

| Page | Route (tab) | Data source |
|------|-------------|-------------|
| Overview | Default | `GET /results`, `GET /data-summary` |
| Channels | Channels tab | `GET /results` |
| Budget Optimizer | Optimizer tab | `POST /optimize`, `GET/POST/DELETE /scenarios` |
| Model Settings | Model tab | `GET /model-runs`, `POST /retrain` |

## File structure

```
front/src/
├── App.js                       — Sidebar nav, health badge, page routing
├── index.js                     — React entry point
├── components/
│   ├── ApiService.js            — All API calls (centralised)
│   ├── MetricCard.js            — Reusable KPI card
│   └── LoadingSpinner.js        — Loading indicator
└── pages/
    ├── Overview.js              — ROI bar chart, contribution chart, recommendations
    ├── ChannelDeepDive.js       — Saturation curve, adstock decay chart
    ├── BudgetOptimizer.js       — Budget sliders, live optimizer, scenario table
    └── ModelSettings.js         — Run history table, retrain button, pipeline info
```

## Libraries used

| Library | Version | Purpose |
|---------|---------|---------|
| React | 18.3.1 | UI framework |
| Recharts | 2.12.7 | BarChart, LineChart, tooltips |
| Axios | 1.7.2 | Available (ApiService uses native fetch) |

## API data shapes expected

### GET /results
```json
{
  "model_version": "v2.0-ols-organic",
  "r_squared": 0.8923,
  "channels": [
    {
      "channel": "search",
      "roi_estimate": 3.40,
      "contribution_pct": 28.5,
      "recommendation": "under-invested"
    }
  ]
}
```

### POST /optimize request
```json
{ "total_budget": 100000, "constraints": { "tv": { "min": 5000 } } }
```

### POST /optimize response
```json
{
  "total_budget": 100000,
  "allocation": { "search": 42000, "facebook": 26000, "tv": 15000, "ooh": 10000, "print": 7000 },
  "predicted_revenue": 318500
}
```

## How to run

```bash
docker-compose up front
# Dashboard: http://localhost:3000
```
