# LightGBM feature ablation

Fixed validation-selected configuration: lightgbm-09-level-l1.
All rows use the same suspect exclusion and split dates.
MAE reduction vs persistence = 1 - macro MAE / persistence macro MAE.

| Features | Split | Fit | Macro MAE | MAE reduction | Mean per-city skill | 95% block interval for mean per-city skill |
|---|---|---|---:|---:|---:|---:|
| base | val | train | 10.225 | 0.051 | 0.036 | [0.003, 0.064] |
| base | test_a | train+val | 10.256 | 0.030 | 0.012 | [-0.020, 0.031] |
| base+weather | val | train | 9.743 | 0.096 | 0.067 | [0.033, 0.087] |
| base+weather | test_a | train+val | 10.136 | 0.041 | 0.018 | [-0.022, 0.037] |
| base+festival | val | train | 10.220 | 0.052 | 0.034 | [0.002, 0.059] |
| base+festival | test_a | train+val | 10.231 | 0.032 | 0.009 | [-0.022, 0.028] |
| base+anomaly | val | train | 10.268 | 0.047 | 0.028 | [-0.002, 0.056] |
| base+anomaly | test_a | train+val | 10.263 | 0.029 | 0.011 | [-0.024, 0.033] |
| all | val | train | 9.846 | 0.086 | 0.053 | [0.012, 0.078] |
| all | test_a | train+val | 10.133 | 0.042 | 0.017 | [-0.023, 0.038] |
