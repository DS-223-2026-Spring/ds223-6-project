# /data

Shared data folder mounted into both the `ds` and `orch` containers.

Place the three Robyn CSV files here before running the pipeline:

- `dt_simulated_weekly.csv`
- `dt_prophet_holidays.csv`
- `df_curve_reach_freq.csv`

Download from: https://github.com/facebookexperimental/Robyn/tree/main/demo/data

This folder is listed in `.gitignore` — CSV files are NOT committed to git.
