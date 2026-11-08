"use client";
import { useCallback, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Activity, ArrowRight } from "lucide-react";
import { api, allBacktests } from "@/lib/api";
import type { Split, Point, Backtest } from "@/lib/types";
import { Resource } from "./Resource";
import { SeriesChart } from "./Charts";
const pct = (n: number | null | undefined) =>
  n == null ? "Unavailable" : (n * 100).toFixed(1) + "%";
const num = (n: number | null) => (n == null ? "—" : n.toFixed(1));
const title = (s: string) =>
  s.replaceAll("_", " ").replace(/\b\w/g, (x) => x.toUpperCase());
const splits: Split[] = ["val", "test_a", "test_b"];
const colors = ["#0d9488", "#6366f1", "#d97706"];
const overview = async (s: AbortSignal) => {
  const [health, models, drift] = await Promise.all([
    api.health(s),
    api.models(s),
    api.drift(s),
  ]);
  return { health, models, drift };
};
const modelData = async (s: AbortSignal) => ({
  models: await api.models(s),
  backtests: await allBacktests(s),
});
const monitorData = async (s: AbortSignal) => ({
  drift: await api.drift(s),
  backtests: await allBacktests(s),
});
function Heading({
  eyebrow,
  title: heading,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="heading">
      <div className="eyebrow">{eyebrow}</div>
      <h1>{heading}</h1>
      <p>{description}</p>
    </div>
  );
}
function Badge({ drifted }: { drifted: boolean }) {
  return (
    <span className={"badge " + (drifted ? "warning" : "good")}>
      <span className="status-dot" />
      {drifted ? "Drift detected" : "Within drift threshold"}
    </span>
  );
}
function skill(rows: Point[]) {
  const valid = rows.filter(
    (x) =>
      x.y_true != null && x.y_pred_best != null && x.y_pred_persistence != null,
  );
  const base = valid.reduce(
    (s, x) => s + Math.abs(x.y_true! - x.y_pred_persistence!),
    0,
  );
  return base
    ? 1 -
        valid.reduce((s, x) => s + Math.abs(x.y_true! - x.y_pred_best!), 0) /
          base
    : null;
}
export function Overview() {
  return (
    <>
      <Heading
        eyebrow="THE BIG PICTURE"
        title="A clearer view of the air."
        description="Next-day PM2.5 forecasting across Indian cities. Follow the predictions, the evidence, and the data behind them."
      />
      <Resource load={overview}>
        {({ health, models, drift }) => {
          const selected = models.model_metrics.filter(
            (x) => x.config_id === models.selected_config.config_id,
          );
          const drifted = Object.values(drift.comparisons).some(
            (x) => x.status === "drifted",
          );
          return (
            <>
              <div className="kpis">
                {[
                  [
                    "Selected model",
                    title(health.model_name),
                    "Chosen by validation macro MAE",
                  ],
                  ...(["test_a", "test_b"] as Split[]).map((s) => [
                    title(s) + " MAE reduction",
                    pct(selected.find((x) => x.split === s)?.macro_mae_skill),
                    "Versus persistence · macro MAE",
                  ]),
                  [
                    "Data as of",
                    health.data_as_of_date,
                    "Static historical snapshot",
                  ],
                ].map(([label, value, note]) => (
                  <article className="panel kpi" key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                    <small>{note}</small>
                  </article>
                ))}
              </div>
              <div className="overview-grid">
                <section className="feature-panel">
                  <span className="eyebrow">FROM MEASUREMENT TO FORECAST</span>
                  <h2>
                    Tomorrow’s air.
                    <br />
                    Grounded in yesterday’s evidence.
                  </h2>
                  <p>
                    VayuOps brings city-level air quality data into one
                    reproducible forecasting pipeline. Models predict the next
                    calendar day’s PM2.5 concentration and are evaluated against
                    a simple persistence baseline.
                  </p>
                  <Link className="primary" href="/forecast">
                    Explore city forecasts <ArrowRight size={17} />
                  </Link>
                  <div className="pipeline">
                    <span>Observe</span>
                    <span>→</span>
                    <span>Predict</span>
                    <span>→</span>
                    <span>Evaluate</span>
                  </div>
                </section>
                <section className="panel">
                  <Activity className="accent" />
                  <h2>Keep the evidence in view</h2>
                  <Badge drifted={drifted} />
                  <p>
                    Distribution changes can affect how well a trained model
                    generalizes. Inspect drift alongside historical prediction
                    error.
                  </p>
                  <Link className="text-link" href="/monitoring">
                    Open monitoring <ArrowUpRight size={16} />
                  </Link>
                  <hr />
                  <a
                    className="text-link"
                    href="https://github.com/Ayan1702-D/Vayuops"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Explore the project on GitHub <ArrowUpRight size={16} />
                  </a>
                </section>
              </div>
              <p className="fine">
                MAE reduction = 1 − model macro MAE / persistence macro MAE.
                Positive values indicate improvement. Predictions refer to the
                saved snapshot date.
              </p>
            </>
          );
        }}
      </Resource>
    </>
  );
}
export function ForecastPage() {
  return (
    <>
      <Heading
        eyebrow="CITY EXPLORER"
        title="Follow the forecast."
        description="Observed PM2.5 and the next-day prediction from the saved data snapshot. All concentrations are in µg/m³."
      />
      <Resource load={api.cities}>
        {({ cities }) =>
          cities.length ? (
            <ForecastCity cities={cities} />
          ) : (
            <p className="empty">No cities are available in this snapshot.</p>
          )
        }
      </Resource>
    </>
  );
}
function ForecastCity({ cities }: { cities: string[] }) {
  const [city, setCity] = useState(cities[0]);
  const [split, setSplit] = useState<Split>("test_a");
  const load = useCallback(
    async (s: AbortSignal) => ({
      history: await api.history(city, s),
      forecast: await api.forecast(city, s),
      backtest: await api.backtest(city, split, s),
    }),
    [city, split],
  );
  return (
    <>
      <div className="controls">
        <label>
          City
          <select aria-label="City" value={city} onChange={(e) => setCity(e.target.value)}>
            {cities.map((x) => (
              <option key={x} value={x}>
                {title(x)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Evaluation period
          <select
            aria-label="Evaluation period" value={split}
            onChange={(e) => setSplit(e.target.value as Split)}
          >
            {splits.map((x) => (
              <option key={x} value={x}>
                {title(x)}
              </option>
            ))}
          </select>
        </label>
        <span className="badge">Static data snapshot</span>
      </div>
      <Resource load={load}>
        {({ history, forecast, backtest }) => {

          const chart: object[] = [
            ...history.rows.map((x) => ({
              ...x,
              prediction: x.date === forecast.as_of_date ? x.pm25 : null,
            })),
            {
              date: forecast.target_date,
              pm25: null,
              prediction: forecast.pm25_forecast,
            },
          ];
          return (
            <>
              <section className="panel">
                <div className="section-head">
                  <div>
                    <h2>{title(city)} · Recent history</h2>
                    <p>
                      As of {forecast.as_of_date} · Forecast for{" "}
                      {forecast.target_date}
                    </p>
                  </div>
                  <div className="forecast-value">
                    {num(forecast.pm25_forecast)} <small>µg/m³</small>
                  </div>
                </div>
                {(
                  <SeriesChart
                    data={chart}
                    series={[
                      { key: "pm25", name: "Observed", color: colors[0] },
                      {
                        key: "prediction",
                        name: "Next-day forecast",
                        color: colors[1],
                        dashed: true,
                      },
                    ]}
                  />
                )}
                <p className="fine">
                  The forecast uses the latest available city observation, which
                  may predate today.
                </p>
              </section>
              <section className="panel">
                <h2>How predictions held up</h2>
                <p>{title(split)} · Actual and selected-model predictions</p>
                <SeriesChart
                  data={backtest.rows}
                  series={[
                    { key: "y_true", name: "Actual", color: colors[0] },
                    { key: "y_pred_best", name: "Predicted", color: colors[1] },
                  ]}
                />
                <h3>Last 7 evaluated predictions</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Actual</th>
                        <th>Predicted</th>
                        <th>Absolute error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {backtest.rows
                        .slice(-7)
                        .reverse()
                        .map((x) => (
                          <tr key={x.date}>
                            <td>{x.date}</td>
                            <td>{num(x.y_true)}</td>
                            <td>{num(x.y_pred_best)}</td>
                            <td>
                              {num(
                                x.y_true != null && x.y_pred_best != null
                                  ? Math.abs(x.y_true - x.y_pred_best)
                                  : null,
                              )}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
                {!backtest.rows.length && (
                  <p className="empty">
                    No evaluated predictions for this city and split.
                  </p>
                )}
              </section>
            </>
          );
        }}
      </Resource>
    </>
  );
}
export function ModelsPage() {
  const [split, setSplit] = useState<Split>("test_a");
  return (
    <>
      <Heading
        eyebrow="MODEL BENCHMARK"
        title="Performance, in perspective."
        description="Compare model families on the same evaluation periods and fit scopes."
      />
      <Resource load={modelData}>
        {({ models, backtests }) => {
          const ids = new Set(models.summary_configs.map((x) => x.config_id));
          const rows = models.model_metrics.filter(
            (x) => ids.has(x.config_id) && !x.unstable,
          );
          const matched = backtests
            .filter((x) => x.split === "test_b")
            .flatMap((x) => x.rows)
            .filter((x) => x.station_matched).length;
          return (
            <>
              <section className="panel">
                <h2>Model comparison</h2>
                <p>
                  MAE and RMSE in µg/m³. Lower is better. MAE reduction uses
                  macro MAE relative to persistence.
                </p>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        {[
                          "Model",
                          "Split",
                          "Fit",
                          "MAE",
                          "RMSE",
                          "MAE reduction",
                        ].map((x) => (
                          <th key={x}>{x}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((x) => (
                        <tr key={x.config_id + x.split}>
                          <td>
                            {title(x.model)}{" "}
                            {x.config_id ===
                              models.selected_config.config_id && (
                              <span className="selected">Selected</span>
                            )}
                          </td>
                          <td>{title(x.split)}</td>
                          <td>{x.Fit}</td>
                          <td>{num(x.mae)}</td>
                          <td>{num(x.rmse)}</td>
                          <td>{pct(x.macro_mae_skill)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!rows.length && (
                  <p className="empty">No stable model results available.</p>
                )}
              </section>
              <section className="panel">
                <div className="section-head">
                  <div>
                    <h2>Selected model · Per-city skill</h2>
                    <p>
                      1 − city MAE / city persistence MAE. Negative values mean
                      persistence performed better.
                    </p>
                  </div>
                  <label>
                    Split
                    <select
                      aria-label="Evaluation period" value={split}
                      onChange={(e) => setSplit(e.target.value as Split)}
                    >
                      {splits.map((x) => (
                        <option key={x}>{x}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="bars">
                  {backtests
                    .filter((x) => x.split === split)
                    .map((x) => {
                      const value = skill(x.rows);
                      return (
                        <div className="bar-row" key={x.city}>
                          <span>{title(x.city)}</span>
                          <div className="bar-track">
                            <div
                              style={{
                                width:
                                  Math.min(100, Math.abs(value ?? 0) * 100) +
                                  "%",
                                background:
                                  (value ?? 0) < 0 ? "#d97706" : "#0d9488",
                              }}
                            />
                          </div>
                          <strong>{pct(value)}</strong>
                        </div>
                      );
                    })}
                </div>
              </section>
              <aside className="note">
                <h3>Reading test_b</h3>
                <p>
                  Test B evaluates 2025 OpenAQ observations. Matched rows use
                  configured stations, while unmatched rows aggregate available
                  stations at city level.{" "}
                  {matched === 0
                    ? "There are zero matched rows in this snapshot. Test B uses city-level unmatched features."
                    : `This snapshot contains ${matched} matched rows.`}
                </p>
              </aside>
            </>
          );
        }}
      </Resource>
    </>
  );
}
function monthly(backtests: Backtest[]) {
  const map = new Map<
    string,
    { date: string; split: Split; error: number; n: number }
  >();
  for (const b of backtests)
    for (const p of b.rows) {
      if (p.y_true == null || p.y_pred_best == null) continue;
      const month = p.date.slice(0, 7);
      const key = month + b.split;
      const row = map.get(key) ?? {
        date: month,
        split: b.split,
        error: 0,
        n: 0,
      };
      row.error += Math.abs(p.y_true - p.y_pred_best);
      row.n++;
      map.set(key, row);
    }
  return [...map.values()]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((x) => ({ date: x.date, [x.split]: x.error / x.n }));
}
export function MonitoringPage() {
  return (
    <>
      <Heading
        eyebrow="DATA & MODEL HEALTH"
        title="Watch for change."
        description="Track distribution drift and prediction error as the evaluation period changes."
      />
      <Resource load={monitorData}>
        {({ drift, backtests }) => {
          const data = monthly(backtests);
          return (
            <>
              <div className="drift-grid">
                {Object.entries(drift.comparisons).map(([name, item]) => (
                  <section className="panel" key={name}>
                    <div className="eyebrow">{title(name)}</div>
                    <h2>
                      {(item.share_drifted * 100).toFixed(0)}% of features
                      drifted
                    </h2>
                    <Badge drifted={item.status === "drifted"} />
                    <p>
                      {item.current_period.start} → {item.current_period.end}
                    </p>
                    <div className="tags">
                      {item.drifted_features.length ? (
                        item.drifted_features.map((x) => (
                          <span key={x}>{x.toUpperCase()}</span>
                        ))
                      ) : (
                        <span>No features exceeded the threshold</span>
                      )}
                    </div>
                  </section>
                ))}
              </div>
              <section className="panel">
                <h2>Monthly prediction error</h2>
                <p>
                  Pooled MAE for the selected model · µg/m³ · Colored segments
                  identify each split.
                </p>
                <SeriesChart
                  data={data}
                  series={splits.map((s, i) => ({
                    key: s,
                    name: title(s),
                    color: colors[i],
                  }))}
                  boundaries={splits
                    .map((s) => data.find((x) => s in x)?.date)
                    .filter((x): x is string => !!x)}
                />
                <p className="fine">
                  Calculated from available backtest observations. Missing
                  months are omitted. Drift method: {drift.method}. Drift is
                  measured against train features.
                </p>
              </section>
            </>
          );
        }}
      </Resource>
    </>
  );
}
