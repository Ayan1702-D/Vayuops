"""Compare pollutant features with Evidently 0.7.17.

If its API fails or times out twice, use reference-binned PSI and SciPy's
two-sample KS test instead. The fallback writes a compact HTML report too.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from vayuops_ml.split import split_by_target_date


FEATURES = ("pm25", "pm10", "no2", "so2", "co", "o3")
PSI_THRESHOLD = 0.2
KS_P_THRESHOLD = 0.05


def numeric_values(series: pd.Series) -> np.ndarray:
    """Return finite numeric observations without changing the input."""
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    return values[np.isfinite(values)]


def psi(reference: pd.Series, current: pd.Series) -> float | None:
    """Population stability index using deciles from the reference distribution."""
    ref, cur = numeric_values(reference), numeric_values(current)
    if not len(ref) or not len(cur):
        return None
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, 11)))
    if len(edges) == 1:
        edges = np.array([edges[0] - 1e-9, edges[0] + 1e-9])
    edges[0], edges[-1] = -np.inf, np.inf
    ref_count = np.histogram(ref, bins=edges)[0].astype(float)
    cur_count = np.histogram(cur, bins=edges)[0].astype(float)
    ref_share = (ref_count + 0.5) / (len(ref) + 0.5 * len(ref_count))
    cur_share = (cur_count + 0.5) / (len(cur) + 0.5 * len(cur_count))
    return float(np.sum((cur_share - ref_share) * np.log(cur_share / ref_share)))


def fallback_drift(reference: pd.DataFrame, current: pd.DataFrame) -> dict[str, dict]:
    """Flag features when both PSI and the KS test indicate distribution drift."""
    result = {}
    for feature in FEATURES:
        ref, cur = numeric_values(reference[feature]), numeric_values(current[feature])
        score = psi(reference[feature], current[feature])
        p_value = float(ks_2samp(ref, cur).pvalue) if len(ref) and len(cur) else None
        result[feature] = {
            "psi": round(score, 6) if score is not None else None,
            "ks_p_value": round(p_value, 8) if p_value is not None else None,
            "drifted": bool(score is not None and p_value is not None
                            and score > PSI_THRESHOLD and p_value < KS_P_THRESHOLD),
        }
    return result


def pollutant_frame(features: pd.DataFrame) -> pd.DataFrame:
    """Select the day-t pollutant values used by the next-day model."""
    return features[[f"{name}_t" for name in FEATURES]].rename(
        columns={f"{name}_t": name for name in FEATURES}
    )


def period(frame: pd.DataFrame) -> dict[str, str | None]:
    dates = pd.to_datetime(frame["target_date"], errors="coerce").dropna()
    return {
        "start": dates.min().date().isoformat() if len(dates) else None,
        "end": dates.max().date().isoformat() if len(dates) else None,
    }


def city_psi(reference: pd.DataFrame, current: pd.DataFrame) -> dict[str, float | None]:
    result = {}
    for city in sorted(current["city"].dropna().astype(str).unique()):
        ref = reference.loc[reference["city"].eq(city), "pm25_t"]
        cur = current.loc[current["city"].eq(city), "pm25_t"]
        score = psi(ref, cur)
        result[city] = round(score, 6) if score is not None else None
    return result


def evidently_worker(root: Path) -> None:
    """Run pinned Evidently in a subprocess so a stalled import can be timed out."""
    from evidently import Report
    from evidently.presets import DataDriftPreset

    features = pd.read_parquet(root / "data/processed/features.parquet")
    splits, _, _ = split_by_target_date(features)
    reference = pollutant_frame(splits["train"])
    output = root / "reports/drift"
    output.mkdir(parents=True, exist_ok=True)
    for name in ("test_a", "test_b"):
        current = pollutant_frame(splits[name])
        snapshot = Report([
            DataDriftPreset(columns=list(FEATURES), method="psi", threshold=PSI_THRESHOLD)
        ]).run(current_data=current, reference_data=reference)
        snapshot.save_html(str(output / f"{name}.html"))
        metrics = snapshot.dict()["metrics"]
        feature_results = {}
        for metric in metrics:
            config = metric.get("config", {})
            column = config.get("column")
            if column in FEATURES:
                value = metric.get("value")
                if isinstance(value, (int, float)):
                    feature_results[column] = {
                        "psi": round(float(value), 6),
                        "drifted": bool(value > PSI_THRESHOLD),
                    }
        if set(feature_results) != set(FEATURES):
            raise ValueError(f"Evidently returned incomplete drift metrics for {name}")
        (output / f"{name}.evidently.json").write_text(
            json.dumps(feature_results), encoding="utf-8"
        )


def fallback_html(name: str, metrics: dict[str, dict], path: Path) -> None:
    rows = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in
                          (feature, item["psi"], item["ks_p_value"], item["drifted"])) + "</tr>"
        for feature, item in metrics.items()
    )
    path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Drift: "
        + html.escape(name) + "</title></head><body><h1>Drift: " + html.escape(name)
        + "</h1><p>Evidently failed twice; fallback: PSI &gt; 0.2 and KS p &lt; 0.05."
        + "</p><table border='1'><tr><th>Feature</th><th>PSI</th>"
        + "<th>KS p</th><th>Drifted</th></tr>" + rows + "</table></body></html>",
        encoding="utf-8",
    )


def run(root: Path, *, evidently_timeout: int = 30) -> dict:
    """Write two comparison reports and copy the summary into backend assets."""
    features = pd.read_parquet(root / "data/processed/features.parquet")
    splits, _, _ = split_by_target_date(features)
    output = root / "reports/drift"
    output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "vayuops_ml.drift", "--evidently-worker", str(root)]
    errors = []
    method = "evidently"
    for _ in range(2):
        try:
            attempt = subprocess.run(command, capture_output=True, text=True,
                                     timeout=evidently_timeout, check=False)
            if attempt.returncode == 0:
                break
            errors.append(attempt.stderr.strip()[-500:] or f"exit {attempt.returncode}")
        except subprocess.TimeoutExpired:
            errors.append(f"timed out after {evidently_timeout}s")
    else:
        method = "psi_ks_fallback"
        print("Evidently failed twice; using PSI + SciPy KS fallback: " + "; ".join(errors))

    summary: dict = {"method": method, "reference_period": period(splits["train"]),
                     "comparisons": {}}
    reference = pollutant_frame(splits["train"])
    for name in ("test_a", "test_b"):
        current = pollutant_frame(splits[name])
        if method == "evidently":
            metrics = json.loads((output / f"{name}.evidently.json").read_text(encoding="utf-8"))
            (output / f"{name}.evidently.json").unlink()
        else:
            metrics = fallback_drift(reference, current)
            fallback_html(name, metrics, output / f"{name}.html")
        drifted = [feature for feature in FEATURES if metrics[feature]["drifted"]]
        share = len(drifted) / len(FEATURES)
        summary["comparisons"][name] = {
            "status": "drifted" if share >= 0.5 else "no_drift",
            "share_drifted": round(share, 4),
            "drifted_features": drifted,
            "per_feature": metrics,
            "per_city_pm25_psi": city_psi(splits["train"], splits[name]),
            "reference_period": period(splits["train"]),
            "current_period": period(splits[name]),
        }
    summary_path = output / "drift_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    assets = root / "backend/app/assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(summary_path, assets / summary_path.name)
    print(f"Drift reports: {output}; method={method}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare test features to train features")
    parser.add_argument("--evidently-worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.evidently_worker is not None:
        evidently_worker(args.evidently_worker)
    else:
        run(Path(__file__).resolve().parents[3])


if __name__ == "__main__":
    main()
