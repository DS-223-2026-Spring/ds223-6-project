# Frontend Service

React 18 dashboard — marketing managers interact with model results here.

Dashboard: **http://localhost:3000**

## Pages

| Page | Route (tab) | Data source |
|------|-------------|-------------|
| Overview | Default | `GET /results`, `GET /data-summary` |
| Channels | Channels tab | `GET /results`, `GET /channel-weekly` |
| Budget Optimizer | Optimizer tab | `POST /optimize`, `GET/POST/PUT/DELETE /scenarios` |
| Model Settings | Model tab | `GET /model-runs`, `GET /model-types`, `POST /retrain`, `POST /retrain-bayesian` |

## File structure
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
└── ModelSettings.js         — Run history table, retrain buttons (OLS + Bayesian), pipeline info

## Libraries used

| Library | Version | Purpose |
|---------|---------|---------| 
| React | 18.3.1 | UI framework |
| Recharts | 2.12.7 | BarChart, LineChart, tooltips |
| Axios | 1.7.2 | Available (ApiService uses native fetch) |

## ApiService.js — available calls

All API communication is centralised in `ApiService.js`. Components never call `fetch` directly.

```js
ApiService.getHealth()
ApiService.getResults()
ApiService.getModelRuns()
ApiService.triggerRetrain()
ApiService.retrainBayesian(draws = 500)
ApiService.optimize(totalBudget, constraints)
ApiService.getScenarios()
ApiService.saveScenario(name, totalBudget, allocation, predictedRevenue)
ApiService.updateScenario(id, data)
ApiService.deleteScenario(id)
ApiService.getDataSummary()
ApiService.getPredictions(modelRunId)
ApiService.getOrganicSignals()
ApiService.getPipelineRuns()
ApiService.getChannelWeekly()
ApiService.getModelTypes()
```

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
      "recommendation": "under-invested",
      "roi_lower_90": null,
      "roi_upper_90": null
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