import json
import os
import stat

import pytest

from utils.file_io import atomic_write_json


def test_atomic_write_json_creates_and_replaces_file(tmp_path):
    target = tmp_path / "prediction_BTC_USDT.json"
    target.write_text('{"old": true}')

    payload = {"symbol": "BTC/USDT", "forecast": [{"price": 100.0}]}
    atomic_write_json(target, payload, indent=2)

    loaded = json.loads(target.read_text())
    assert loaded == payload


def test_atomic_write_json_applies_world_readable_mode_on_posix(tmp_path):
    if os.name != "posix":
        pytest.skip("Permission mode check is POSIX-only.")

    target = tmp_path / "history_BTC_USDT.json"
    atomic_write_json(target, {"ok": True})

    file_mode = stat.S_IMODE(target.stat().st_mode)
    assert file_mode == 0o644


def test_atomic_write_json_cleans_temp_file_and_keeps_previous_content_on_failure(
    tmp_path,
):
    target = tmp_path / "prediction_ETH_USDT.json"
    target.write_text('{"stable": true}')

    # set() is not JSON serializable.
    with pytest.raises(TypeError):
        atomic_write_json(target, {"broken": {1, 2, 3}})

    assert json.loads(target.read_text()) == {"stable": True}
    assert not list(tmp_path.glob(f".{target.name}.*"))
