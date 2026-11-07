"""Generate reproducible exploratory figures and compact data summaries."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def calendar_gaps(frame: pd.DataFrame) -> pd.DataFrame:
    """Count consecutive days with no observed PM2.5 per city."""
    rows = []
    for city, group in frame.groupby("city"):
        series = group.set_index("date")["pm25"].reindex(
            pd.date_range(group.date.min(), group.date.max(), freq="D")
        )
        missing = series.isna()
        runs = missing.ne(missing.shift()).cumsum()
        lengths = missing.groupby(runs).sum()
        lengths = lengths[lengths.gt(0)]
        rows.append({
            "city": city, "longest_missing_run": int(lengths.max()) if not lengths.empty else 0,
            "runs_over_3_days": int(lengths.gt(3).sum()),
        })
    return pd.DataFrame(rows)


def source_shift(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare early and late year PM2.5 medians across 2023–2025."""
    rows = []
    for city, group in frame.groupby("city"):
        year = group.date.dt.year
        month = group.date.dt.month
        station_matched = bool(group.loc[year.eq(2025), "station_matched"].fillna(False).any())
        for period, months in (("Jan-Mar", (1, 2, 3)), ("Oct-Dec", (10, 11, 12))):
            medians = {
                y: group.loc[year.eq(y) & month.isin(months), "pm25"].median()
                for y in (2023, 2024, 2025)
            }
            if pd.isna(medians[2025]):
                continue
            ratio24 = medians[2025] / medians[2024] if pd.notna(medians[2024]) and medians[2024] else float("nan")
            ratio23 = medians[2025] / medians[2023] if pd.notna(medians[2023]) and medians[2023] else float("nan")
            rows.append({
                "city": city, "period": period, "median_2023": medians[2023],
                "median_2024": medians[2024], "median_2025": medians[2025],
                "ratio_2025_2024": ratio24, "ratio_2025_2023": ratio23,
                "station_matched": station_matched,
                "shift_flag": any(pd.notna(r) and (r < .6 or r > 1.6) for r in (ratio24, ratio23)),
            })
    return pd.DataFrame(rows)


def baseline(frame: pd.DataFrame) -> pd.DataFrame:
    """Score tomorrow-equals-today on observed adjacent 2024 dates."""
    rows = []
    for city, group in frame.groupby("city"):
        series = group.set_index("date")["pm25"].sort_index()
        actual = series.reindex(series.index + pd.Timedelta(days=1))
        errors = (actual.to_numpy() - series.to_numpy())
        pairs = pd.DataFrame({"date": series.index + pd.Timedelta(days=1), "error": errors})
        pairs = pairs.loc[pairs.date.dt.year.eq(2024) & pairs.error.notna()]
        rows.append({
            "city": city, "n": len(pairs),
            "mae": pairs.error.abs().mean(),
            "rmse": math.sqrt(pairs.error.pow(2).mean()) if len(pairs) else float("nan"),
        })
    return pd.DataFrame(rows)


def draw(frame: pd.DataFrame, out: Path) -> list[str]:
    """Save six figures and return one summary line per figure."""
    notes = []
    cities = sorted(frame.city.unique())
    months = pd.period_range(frame.date.min(), frame.date.max(), freq="M")
    heat = pd.DataFrame(index=cities, columns=months, dtype=float)
    for (city, month), group in frame.groupby(["city", frame.date.dt.to_period("M")]):
        start = max(month.start_time, frame.loc[frame.city.eq(city), "date"].min())
        end = min(month.end_time.normalize(), frame.loc[frame.city.eq(city), "date"].max())
        heat.loc[city, month] = group.pm25.notna().sum() / ((end - start).days + 1)
    fig, ax = plt.subplots(figsize=(16, 4))
    image = ax.imshow(heat.astype(float), aspect="auto", vmin=0, vmax=1, cmap="viridis")
    ax.set_yticks(range(len(cities)), cities)
    ax.set_xticks(range(0, len(months), 6), [str(months[i]) for i in range(0, len(months), 6)], rotation=45)
    ax.set_title("PM2.5 daily coverage by city and month")
    fig.colorbar(image, ax=ax, label="Share")
    fig.tight_layout()
    fig.savefig(out / "coverage_heatmap.png", dpi=140)
    plt.close(fig)
    notes.append(f"- coverage_heatmap.png: {len(cities)} cities, {len(months)} months; mean observed coverage {heat.stack().mean():.1%}.")

    fig, axes = plt.subplots(5, 2, figsize=(16, 13), sharex=True)
    for ax, city in zip(axes.flat, cities):
        group = frame.loc[frame.city.eq(city)].sort_values("date")
        for year_group, color in ((group[group.date.lt("2025-01-01")], "steelblue"), (group[group.date.ge("2025-01-01")], "darkorange")):
            ax.plot(year_group.date, year_group.pm25, color=color, linewidth=.55)
        ax.axvline(pd.Timestamp("2025-01-01"), color="black", linestyle="--", linewidth=.8)
        ax.set_title(city)
    fig.suptitle("Daily PM2.5; orange marks the 2025 source")
    fig.tight_layout()
    fig.savefig(out / "timeseries_cities.png", dpi=140)
    plt.close(fig)
    notes.append(f"- timeseries_cities.png: {len(cities)} city panels; 2025 source begins {frame.loc[frame.date.dt.year.eq(2025), 'date'].min():%Y-%m-%d}.")

    fig, axes = plt.subplots(5, 2, figsize=(16, 13), sharex=True)
    for ax, city in zip(axes.flat, cities):
        group = frame.loc[frame.city.eq(city)]
        arrays = [group.loc[group.date.dt.month.eq(month), "pm25"].dropna() for month in range(1, 13)]
        ax.boxplot(arrays, showfliers=False)
        ax.set_title(city)
    fig.suptitle("Monthly PM2.5 seasonality")
    fig.tight_layout()
    fig.savefig(out / "seasonality.png", dpi=140)
    plt.close(fig)
    monthly_medians = frame.groupby(frame.date.dt.month)["pm25"].median()
    notes.append(
        f"- seasonality.png: 10 city boxplot panels; lowest overall monthly median "
        f"{monthly_medians.idxmin()} ({monthly_medians.min():.1f}), highest "
        f"{monthly_medians.idxmax()} ({monthly_medians.max():.1f}) ug/m3."
    )

    covid = frame.loc[
        frame.date.dt.year.between(2020, 2024)
        & ((frame.date.dt.month.eq(3) & frame.date.dt.day.ge(25))
           | frame.date.dt.month.eq(4)
           | (frame.date.dt.month.eq(5) & frame.date.dt.day.le(31)))
    ].copy()
    comparison = covid.groupby(["city", covid.date.dt.year])["pm25"].median().unstack()
    fig, ax = plt.subplots(figsize=(14, 5))
    comparison.plot.bar(ax=ax, width=.8)
    ax.set_title("Median PM2.5, March 25–May 31, by year")
    ax.set_ylabel("PM2.5 (ug/m3)")
    fig.tight_layout()
    fig.savefig(out / "covid_2020.png", dpi=140)
    plt.close(fig)
    notes.append(f"- covid_2020.png: 2020 window median across cities {comparison[2020].median():.1f} ug/m3; same window 2024 {comparison[2024].median():.1f}.")

    fig, axes = plt.subplots(5, 2, figsize=(16, 13), sharex=True)
    years = list(range(2020, 2026))
    for ax, city in zip(axes.flat, cities):
        group = frame.loc[frame.city.eq(city)]
        arrays = [group.loc[group.date.dt.year.eq(year), "pm25"].dropna() for year in years]
        ax.boxplot(arrays, showfliers=False)
        ax.set_title(city)
        ax.set_xticks(range(1, 7), years)
    fig.suptitle("Yearly PM2.5 distributions")
    fig.tight_layout()
    fig.savefig(out / "yearly_distribution.png", dpi=140)
    plt.close(fig)
    yearly_medians = frame.groupby(frame.date.dt.year)["pm25"].median()
    notes.append(
        f"- yearly_distribution.png: 10 city panels; overall median "
        f"2020 {yearly_medians[2020]:.1f}, 2025 {yearly_medians[2025]:.1f} ug/m3."
    )

    fig, ax = plt.subplots(figsize=(11, 5))
    lag_one = {}
    for city in cities:
        series = frame.loc[frame.city.eq(city)].set_index("date")["pm25"].sort_index()
        values = [series.corr(series.shift(lag, freq="D")) for lag in range(1, 15)]
        ax.plot(range(1, 15), values, marker=".", label=city)
        lag_one[city] = values[0]
    ax.set(xlabel="Calendar-day lag", ylabel="Pearson autocorrelation", title="Observed-day PM2.5 autocorrelation")
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "acf.png", dpi=140)
    plt.close(fig)
    notes.append(f"- acf.png: lags 1–14 without gap filling; median city lag-1 correlation {pd.Series(lag_one).median():.2f}.")
    return notes


def main(root: Path) -> str:
    """Read clean data, write EDA outputs, and return the compact summary."""
    frame = pd.read_parquet(root / "data" / "processed" / "clean.parquet")
    frame["date"] = pd.to_datetime(frame["date"])
    out = root / "reports" / "eda"
    out.mkdir(parents=True, exist_ok=True)
    notes = draw(frame, out)
    gaps = calendar_gaps(frame)
    shifts = source_shift(frame)
    persistence = baseline(frame)
    gaps.to_csv(out / "gaps.csv", index=False)
    shifts.to_csv(out / "source_shift.csv", index=False)
    persistence.to_csv(out / "persistence_baseline.csv", index=False)
    notes.extend([
        f"- gaps.csv: longest missing PM2.5 run {gaps.longest_missing_run.max()} days; {gaps.runs_over_3_days.sum()} runs exceed 3 days.",
        f"- source_shift.csv: {len(shifts)} city-period comparisons; {shifts.shift_flag.sum()} flagged ratios outside 0.6–1.6.",
        f"- persistence_baseline.csv: 2024 next-day baseline for {len(persistence)} cities; median MAE {persistence.mae.median():.2f}, median RMSE {persistence.rmse.median():.2f}.",
    ])
    summary = "# EDA summary\n\n" + "\n".join(notes) + "\n"
    (out / "summary.md").write_text(summary, encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(main(Path(__file__).resolve().parents[3]), end="")

