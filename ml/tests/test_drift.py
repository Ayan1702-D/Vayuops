"""Synthetic drift checks independent of Evidently's import time."""

import numpy as np
import pandas as pd

from vayuops_ml.drift import FEATURES, fallback_drift, psi


def frame(values: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({feature: values for feature in FEATURES})


def test_shifted_frame_is_flagged() -> None:
    reference = frame(np.arange(100, dtype=float))
    current = frame(np.arange(100, dtype=float) + 1000)
    result = fallback_drift(reference, current)
    assert all(item["drifted"] for item in result.values())
    assert all(item["psi"] > 0.2 for item in result.values())


def test_unshifted_frame_is_not_flagged() -> None:
    reference = frame(np.arange(100, dtype=float))
    result = fallback_drift(reference, reference.copy())
    assert not any(item["drifted"] for item in result.values())
    assert psi(reference["pm25"], reference["pm25"]) == 0
