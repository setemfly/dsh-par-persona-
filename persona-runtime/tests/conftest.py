from __future__ import annotations

from pathlib import Path

import pytest

from par.config.settings import RuntimeConfig, load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def project_root() -> Path:
    return ROOT


@pytest.fixture()
def config(tmp_path: Path) -> RuntimeConfig:
    base = load_config(ROOT / "configs" / "runtime.yaml")
    return base.model_copy(update={"root": ROOT, "data_dir": str(tmp_path), "provider": "fake"})
