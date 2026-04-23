# DS Service — Data Science Pipeline

Python 3.11 container for EDA, feature engineering, and MMM modeling.

## Folder structure

```
ds/
├── Dockerfile
├── requirements.txt
├── db_client.py          # DB connection helper (reads/writes via SQLAlchemy)
├── eda.py                # Exploratory data analysis script
├── models/
│   └── baseline.py       # Adstock + saturation transforms + OLS stub
└── notebooks/
    └── 01_eda.ipynb      # Jupyter notebook version of EDA (Sprint 2)
```

## How to run

```bash
# Start the DS container
docker-compose up ds

# Run EDA (requires data loaded in DB first)
docker exec mmm_ds python eda.py

# Run the baseline model pipeline
docker exec mmm_ds python models/baseline.py

# Open Jupyter (optional)
docker exec -it mmm_ds jupyter notebook --ip=0.0.0.0 --allow-root
```

## Features and target variable

| Variable | Type | Source | Notes |
|----------|------|--------|-------|
| `tv_spend` | Predictor | raw_spend_data | Transformed via adstock + saturation |
| `ooh_spend` | Predictor | raw_spend_data | Transformed via adstock + saturation |
| `print_spend` | Predictor | raw_spend_data | Transformed via adstock + saturation |
| `facebook_spend` | Predictor | raw_spend_data | Transformed via adstock + saturation |
| `search_spend` | Predictor | raw_spend_data | Transformed via adstock + saturation |
| `holiday_flag` | Control | dt_prophet_holidays | Separates holiday lift from channel effect |
| `total_revenue` | **Target** | revenue_data | Weekly revenue in USD |

## Assumptions

- Data is from Meta's Robyn open-source demo dataset (simulated, not real company data).
- Adstock decay rates are initialized from literature values and will be tuned in Sprint 2.
- Hill function saturation parameters will be calibrated using df_curve_reach_freq.csv in Sprint 2.
- Baseline model is OLS regression. Bayesian upgrade (PyMC) is a Sprint 4 stretch goal.
- All model outputs are written back to the database via db_client.py, not to local files.
