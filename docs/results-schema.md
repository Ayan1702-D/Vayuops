# Results schema

`reports/results.json` is the machine-readable companion to `reports/results.md`. The registry exports the same JSON bytes to `backend/app/assets/results.json`.

Top-level keys retained from the previous report:

| Key | Meaning |
|---|---|
| `best_model` | Selected model family. |
| `best_config` | Selected configuration ID, target mode, objective and parameters. |
| `validation_macro_mae`, `validation_macro_skill` | Selected validation values; macro skill is the mean of per-city MAE skills. |
| `model_metrics` | One record per configuration and split, including `Fit`, pooled and macro MAE/RMSE, MAE and RMSE skills, `macro_mae_skill`, and `unstable`. Unstable configurations remain here. |
| `per_city` | Selected configuration's city metrics for validation, test A and test B. |
| `test_b_station_match` | Selected configuration split by matched status; an empty matched group has `n=0` and null metrics. |
| `bootstrap` | Paired MAE difference (model minus persistence) estimate, 95% moving-block interval and zero-exclusion flag per split. Negative favors the model. |
| `suspect_exclusions` | Count removed for each city and split. |
| `split_dates`, `split_counts` | Inclusive target-date cutoffs and post-exclusion counts. |
| `feature_groups`, `findings` | Enabled groups and a plain-English summary. |

Added keys: `summary_configs` and `validation_mae_reduction`. `summary_configs` holds at most one stable validation winner per model family, with a selected marker. A configuration is unstable when its pooled validation MAE is more than twice persistence's pooled validation MAE. It cannot be selected or appear in the Markdown summary.

`reports/grid_results.csv` contains exactly one row per `(config_id, split, Fit)`, including family, target mode, objective, feature groups, key parameters, `unstable`, pooled metrics, macro metrics, and `mae_reduction`. `Fit` is `train` for validation and `train+val` for both tests.

`macro_mae_skill = 1 - model_macro_mae / persistence_macro_mae`. This differs from `macro_skill`, the mean of the per-city skills. RMSE skill uses the analogous RMSE ratio. The delta-log back-transform clips deltas to [-2, 2] and resulting levels to [0, 1.5 times that city's maximum train PM2.5].


The headline MAE reduction is `1 - macro MAE / persistence macro MAE`. `macro_skill` remains the mean of per-city skills and is labeled separately in both Markdown reports. `reports/ablation.md` computes MAE reduction from each row's macro MAE and the corresponding split's persistence macro MAE.

`backend/app/assets/metadata.json` contains only `selected_config`, `persistence` (three split rows), `summary_configs`, `split_dates`, and `features`. The full grid remains in `reports/grid_results.csv`.
