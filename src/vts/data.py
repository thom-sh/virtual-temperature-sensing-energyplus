from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

DATE_TIME = "Date/Time"
TEMP_TOKEN = "Zone Mean Air Temperature"


def load_energyplus_csv(path: str | Path, strip_time: bool = True) -> pd.DataFrame:
    df = pd.read_csv(path)
    # EnergyPlus CSV headers can contain incidental trailing spaces. Normalize them once.
    df.columns = [str(c).strip() for c in df.columns]
    if DATE_TIME not in df.columns:
        raise ValueError(f"{path} does not contain a '{DATE_TIME}' column.")
    if strip_time:
        df[DATE_TIME] = df[DATE_TIME].astype(str).str.strip()
    return df


def temperature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if TEMP_TOKEN in c]


def require_columns(df: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing {label} columns: {missing}")


def aligned_pair(
    left: pd.DataFrame,
    right: pd.DataFrame,
    columns: list[str],
    left_suffix: str = "_left",
    right_suffix: str = "_right",
) -> pd.DataFrame:
    require_columns(left, [DATE_TIME, *columns], "left")
    require_columns(right, [DATE_TIME, *columns], "right")
    return left[[DATE_TIME, *columns]].merge(
        right[[DATE_TIME, *columns]],
        on=DATE_TIME,
        suffixes=(left_suffix, right_suffix),
        validate="one_to_one",
    )
