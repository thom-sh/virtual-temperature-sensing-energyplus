from pathlib import Path

from vts.config import load_config, project_path


def test_project_path_resolves_from_repository_root():
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "configs" / "project.yaml")
    assert project_path(cfg, "models/base/model.idf") == root / "models/base/model.idf"
