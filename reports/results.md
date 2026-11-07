# VayuOps model results

## Findings

Selected lightgbm-09-level-l1 (level, l1; groups weather, festival, anomaly) by validation macro MAE. val: headline MAE reduction 8.6% (1 - macro MAE / persistence macro MAE); paired MAE difference 95% interval [-1.19, -0.56] excludes zero; pooled RMSE reduction 2.80. test_a: headline MAE reduction 4.2% (1 - macro MAE / persistence macro MAE); paired MAE difference 95% interval [-0.85, 0.07] includes zero; pooled RMSE reduction 0.25. test_b: headline MAE reduction 8.1% (1 - macro MAE / persistence macro MAE); paired MAE difference 95% interval [-1.24, -0.49] excludes zero; pooled RMSE reduction 2.15. Cities worse than persistence on val: chennai, mumbai. Cities worse than persistence on test_a: chennai, mumbai. Test B used city-level unmatched 2025 features; matched-station n is 0.

MAE reduction vs persistence = 1 - macro MAE / persistence macro MAE.

## Best stable configuration per model family

| Model | Config | Target | Objective | Features | Key params | Selected | Fit (val / test) | Val macro MAE | Val MAE reduction | Val mean per-city skill | Test A macro MAE | Test A MAE reduction | Test A mean per-city skill | Test B macro MAE | Test B MAE reduction | Test B mean per-city skill |
|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| persistence | persistence-00-level-none | level | none | weather, festival, anomaly | {} |  | train / train+val | 10.778 | 0.000 | 0.000 | 10.573 | 0.000 | 0.000 | 9.654 | 0.000 | 0.000 |
| ridge | ridge-04-delta_log-none | delta_log | none | weather, festival, anomaly | {"alpha": 10.0} |  | train / train+val | 10.225 | 0.051 | 0.037 | 10.931 | -0.034 | -0.003 | 9.320 | 0.035 | 0.036 |
| lightgbm | lightgbm-09-level-l1 | level | l1 | weather, festival, anomaly | {"learning_rate": 0.05, "n_estimators": 140, "num_leaves": 31, "objective": "l1"} | Yes | train / train+val | 9.846 | 0.086 | 0.053 | 10.133 | 0.042 | 0.017 | 8.875 | 0.081 | 0.070 |
| xgboost | xgboost-21-level-l1 | level | l1 | weather, festival, anomaly | {"learning_rate": 0.05, "max_depth": 5, "n_estimators": 140, "objective": "l1"} |  | train / train+val | 9.951 | 0.077 | 0.045 | 10.189 | 0.036 | 0.012 | 8.922 | 0.076 | 0.065 |

All configurations, including unstable ones: `reports/grid_results.csv`.

## Paired MAE difference versus persistence

Negative paired differences favor the selected model. Moving-block bootstrap: 14-day blocks, 1,000 resamples.

| Split | MAE reduction | Paired MAE difference | 95% interval | Excludes zero |
|---|---:|---:|---:|---|
| val | 0.086 | -0.934 | [-1.193, -0.560] | True |
| test_a | 0.042 | -0.460 | [-0.849, 0.069] | False |
| test_b | 0.081 | -0.789 | [-1.245, -0.486] | True |

## Selected model by city

| Split | City | n | MAE | RMSE | MAE reduction | RMSE skill |
|---|---|---:|---:|---:|---:|---:|
| val | bengaluru | 175 | 6.146 | 13.084 | 0.136 | 0.175 |
| val | chennai | 181 | 7.447 | 14.016 | -0.098 | -0.084 |
| val | delhi | 182 | 24.341 | 37.872 | 0.124 | 0.150 |
| val | gwalior | 182 | 12.832 | 18.726 | 0.091 | 0.116 |
| val | hyderabad | 179 | 3.950 | 5.011 | 0.039 | 0.069 |
| val | jaipur | 181 | 10.426 | 22.399 | 0.140 | 0.175 |
| val | kolkata | 181 | 7.533 | 10.334 | 0.038 | 0.071 |
| val | lucknow | 182 | 13.448 | 19.711 | 0.140 | 0.125 |
| val | mumbai | 182 | 5.063 | 6.589 | -0.161 | -0.112 |
| val | visakhapatnam | 182 | 7.273 | 10.764 | 0.081 | 0.117 |
| test_a | bengaluru | 184 | 5.798 | 8.291 | 0.059 | 0.046 |
| test_a | chennai | 173 | 12.627 | 17.953 | -0.283 | -0.155 |
| test_a | delhi | 184 | 27.471 | 53.049 | 0.097 | -0.018 |
| test_a | gwalior | 184 | 11.855 | 23.498 | 0.117 | 0.118 |
| test_a | hyderabad | 182 | 4.325 | 6.401 | 0.022 | 0.021 |
| test_a | jaipur | 184 | 7.520 | 10.293 | 0.047 | 0.035 |
| test_a | kolkata | 184 | 8.031 | 11.640 | 0.042 | 0.070 |
| test_a | lucknow | 182 | 12.230 | 19.176 | 0.085 | 0.082 |
| test_a | mumbai | 183 | 2.790 | 3.592 | -0.078 | -0.018 |
| test_a | visakhapatnam | 184 | 8.679 | 12.917 | 0.062 | 0.053 |
| test_b | bengaluru | 337 | 4.445 | 6.541 | 0.029 | 0.063 |
| test_b | chennai | 359 | 7.660 | 13.518 | 0.088 | 0.147 |
| test_b | delhi | 363 | 19.696 | 30.939 | 0.109 | 0.122 |
| test_b | hyderabad | 344 | 5.140 | 9.655 | 0.016 | 0.063 |
| test_b | jaipur | 314 | 8.265 | 13.310 | 0.104 | 0.137 |
| test_b | kolkata | 358 | 9.674 | 17.330 | 0.051 | 0.090 |
| test_b | lucknow | 312 | 9.169 | 14.126 | 0.070 | 0.112 |
| test_b | mumbai | 357 | 6.952 | 12.459 | 0.091 | 0.104 |

## Test B station match

| Matched | n | MAE | Macro MAE | MAE reduction | Mean per-city skill |
|---|---:|---:|---:|---:|---:|
| True | 0 | — | — | — | — |
| False | 2744 | 8.953 | 8.875 | 0.081 | 0.070 |

No matched-station Test B rows (matched n = 0); 2025 uses city-level unmatched features.

Suspect rows excluded: train 30; val 9; test_a 4; test_b 6.

Mean per-city skill is the arithmetic mean of each city's 1 - city MAE / city persistence MAE. It differs from the headline MAE reduction, which uses the ratio of macro MAEs.
