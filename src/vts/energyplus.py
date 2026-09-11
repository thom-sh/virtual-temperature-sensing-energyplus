from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EnergyPlusRunner:
    executable: Path
    weather_file: Path

    def validate(self) -> None:
        if not self.executable.is_file():
            raise FileNotFoundError(
                f"EnergyPlus executable not found: {self.executable}. "
                "Set ENERGYPLUS_HOME or edit configs/project.yaml."
            )
        if not self.weather_file.is_file():
            raise FileNotFoundError(f"Weather file not found: {self.weather_file}")

    def run(self, idf_file: str | Path, output_dir: str | Path) -> Path:
        self.validate()
        idf_file = Path(idf_file).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path = output_dir / "energyplus_console.log"

        cmd = [
            str(self.executable),
            "-w", str(self.weather_file),
            "-d", str(output_dir),
            "-r",
            str(idf_file),
        ]
        with log_path.open("w", encoding="utf-8") as log:
            subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)

        csv_path = output_dir / "eplusout.csv"
        if not csv_path.is_file():
            raise RuntimeError(f"EnergyPlus completed but did not create {csv_path}")
        return csv_path
