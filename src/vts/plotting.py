from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .data import DATE_TIME


def _short(zone: str) -> str:
    return zone.split(":", 1)[0]


def plot_zone_comparison(
    series: dict[str, pd.DataFrame],
    zones: list[str],
    output_path: str | Path,
    title: str,
    *,
    columns: int = 3,
) -> None:
    if not zones:
        return
    rows = math.ceil(len(zones) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(6 * columns, 4 * rows), sharex=True)
    axes = [axes] if rows == columns == 1 else list(getattr(axes, "flat", [axes]))

    for idx, zone in enumerate(zones):
        ax = axes[idx]
        for label, df in series.items():
            ax.plot(range(len(df)), df[zone].astype(float).to_numpy(), label=label)
        ax.set_title(_short(zone))
        ax.set_ylabel("Temperature (°C)")
        ax.grid(True, alpha=0.25)

    for idx in range(len(zones), len(axes)):
        axes[idx].set_visible(False)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=max(1, len(labels)))
    fig.suptitle(title)
    fig.tight_layout(rect=[0, 0.05, 1, 0.96])
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
