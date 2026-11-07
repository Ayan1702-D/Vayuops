Ingestion: use source-specific adapters and a configured priority to select each city-date.
Why: preserve all source observations while keeping modeling input deterministic and free of imputation.
Alternative: merge pollutant values across sources; rejected because it obscures provenance and unit differences.
nh3 is absent in 2025 data; it must not be used as a model feature.
OpenAQ calendar dates come from date_from converted from UTC to Asia/Kolkata; the file date is checked only for disagreement.
OpenAQ station filters are optional; unfiltered city values use the median across all available stations.
air_pollution_data is excluded from modeling: overlap gas correlations were 0.08 to 0.18, while PM2.5 correlation was 0.51 with median ratio 0.63; quantities or dates may be misaligned.
city_day remains available for source comparison only.
Modeling scope is limited to the ten backbone cities.
Feature lags and rolling windows use a complete per-city calendar, so a missing date never shifts the lag by row.
Pollutant features use past-only forward fill for at most three days; missing targets and missing current PM2.5 after fill are dropped.
Model splits use target_date; the 2025 OpenAQ test is reported separately by station_matched status.
A: Validation fits use train only; every candidate is refit on train+val for both test splits.
A: Selection uses equal-city macro MAE; pooled and macro metrics both compare against persistence.
A: Paired 14-day block intervals accompany suspect-row exclusions and avoid interpreting a small gain as certain.
B: The fixed grids compare level and delta_log targets, with at most 12 combinations per model.
B: Delta-log outputs are inverted to nonnegative PM2.5 levels before scoring.
B: Tree objectives are limited to configured L2, L1, and Huber options.
C: Open-Meteo IST daily weather is cached; only observations through day t enter features.
C: Diwali windows use cited dates in festivals.yaml, including New Delhi on 2024-11-01.
C: City-month anomaly medians are fit on train rows only; ablation checks each optional group.
Delta-log outputs are clipped in log space and against each city training maximum to contain unstable forecasts.
Configurations above three times persistence validation MAE remain in grid_results.csv but cannot be selected or summarized.
The Markdown report shows one stable configuration per family; results.json and its registry copy retain all detailed metrics.
Headline MAE reduction uses the ratio of macro MAEs; the mean of per-city skills is shown separately.
Configurations with validation MAE above twice persistence are unstable and excluded from selection and summary.
Level+Huber configs underfit because Huber's capped gradients cannot reach the level scale in 140 trees at learning rate 0.05.
