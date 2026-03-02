from pathlib import Path

from core.paths import PROJECT_ROOT, get_data_dir


def test_get_data_dir_default(monkeypatch):
    monkeypatch.delenv("AI_LIFE_OS_DATA_DIR", raising=False)
    assert get_data_dir() == PROJECT_ROOT / "data"


def test_get_data_dir_env(monkeypatch):
    monkeypatch.setenv("AI_LIFE_OS_DATA_DIR", "C:/tmp/ai-life-os-data")
    assert get_data_dir() == Path("C:/tmp/ai-life-os-data")
