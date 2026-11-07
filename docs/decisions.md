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
