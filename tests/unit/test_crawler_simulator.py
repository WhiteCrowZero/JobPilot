from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SIMULATOR_PATH = PROJECT_ROOT / "simulator" / "producer.py"


def _load_simulator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("jobpilot_crawler_simulator", SIMULATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load crawler simulator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_simulator_has_no_backend_or_database_imports() -> None:
    source = SIMULATOR_PATH.read_text(encoding="utf-8")

    assert "job_pilot" not in source
    assert "sqlalchemy" not in source


def test_simulator_fixtures_cover_duplicate_and_changed_content() -> None:
    simulator = _load_simulator()
    load_message = cast(Callable[[str], dict[str, object]], simulator.load_scenario_message)

    new_message = load_message("new-job")
    duplicate_content = load_message("duplicate-content")
    changed_content = load_message("changed-content")

    assert new_message["message_id"] != duplicate_content["message_id"]
    assert new_message["raw_payload"] == duplicate_content["raw_payload"]
    assert changed_content["message_id"] != new_message["message_id"]
    assert changed_content["raw_payload"] != new_message["raw_payload"]
