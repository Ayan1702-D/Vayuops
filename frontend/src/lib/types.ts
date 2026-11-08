export type Split = "val" | "test_a" | "test_b";
export type Health = {
  status: string;
  model_name: string;
  model_version: string;
  data_as_of_date: string;
};
export type Forecast = {
  city: string;
  as_of_date: string;
  target_date: string;
  pm25_forecast: number;
  label: string;
};
export type History = { rows: { date: string; pm25: number | null }[] };
export type Point = {
  date: string;
  station_matched: boolean;
  y_true: number | null;
  y_pred_best: number | null;
  y_pred_persistence: number | null;
};
export type Backtest = { city: string; split: Split; rows: Point[] };
export type Metric = {
  model: string;
  config_id: string;
  split: Split;
  Fit: string;
  mae: number;
  rmse: number;
  macro_mae_skill: number | null;
  unstable?: boolean;
};
export type Models = {
  best_model: string;
  selected_config: { config_id: string; model: string };
  summary_configs: { config_id: string }[];
  model_metrics: Metric[];
};
export type Drift = {
  method: string;
  comparisons: Record<
    string,
    {
      status: string;
      share_drifted: number;
      drifted_features: string[];
      current_period: { start: string; end: string };
    }
  >;
};
export type AllBacktests = Backtest[];
