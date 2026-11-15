"""Coordinate transforms, calibration files, settings, window scrub."""

import json

import pytest


CAL = [{"game": [0.0, 0.0], "map": [0.0, 0.0]},
       {"game": [1000.0, -2000.0], "map": [-1.0, 0.5]}]


def test_transform_round_trip(mod):
    for gx, gz in [(0, 0), (500.0, -1234.0), (-9999.0, 8888.0)]:
        lng, lat = mod.game_to_lnglat(gx, gz, CAL)
        bx, bz = mod.lnglat_to_game(lng, lat, CAL)
        assert (bx, bz) == pytest.approx((gx, gz), abs=1e-6)
    assert mod.game_to_lnglat(1000.0, -2000.0, CAL) == pytest.approx(
        (-1.0, 0.5))


def test_degenerate_calibration_is_identity(mod):
    same = [{"game": [5.0, 5.0], "map": [0, 0]},
            {"game": [5.0, 9.0], "map": [1, 1]}]
    assert mod._build_coord_transform(same) == (1.0, 0.0, 1.0, 0.0)
    assert mod.game_to_lnglat(3.0, 4.0, same) == (3.0, 4.0)


def test_default_calibration_when_no_file(mod):
    for realm in ("pywel", "abyss"):
        assert mod._load_calibration(realm) == mod.DEFAULT_CALIBRATIONS[realm]


def test_calibration_save_load(mod):
    mod._save_calibration(CAL, "abyss")
    assert mod._load_calibration("abyss") == CAL
    assert mod._load_calibration("pywel") == mod.DEFAULT_CALIBRATIONS["pywel"]


def test_corrupt_calibration_falls_back_to_defaults(mod, data_dir):
    (data_dir / "cd_calibration_pywel.json").write_text("{nope")
    assert mod._load_calibration("pywel") == mod.DEFAULT_CALIBRATIONS["pywel"]


def test_legacy_calibration_migrates(mod, data_dir):
    (data_dir / "cd_calibration.json").write_text(json.dumps(CAL))
    assert mod._load_calibration("pywel") == CAL
    assert (data_dir / "cd_calibration_pywel.json").exists()
    assert mod._load_calibration("abyss") == mod.DEFAULT_CALIBRATIONS["abyss"]


def test_settings_missing_or_corrupt_is_empty(mod, data_dir):
    assert mod._load_settings() == {}
    (data_dir / "cd_settings.json").write_text("not json")
    assert mod._load_settings() == {}


def test_settings_round_trip(mod):
    mod._save_settings({"advanced": {"height": 900.0}, "x": [1, 2]})
    assert mod._load_settings() == {"advanced": {"height": 900.0},
                                    "x": [1, 2]}


def test_scrub_drops_offscreen_window_coords(mod, monkeypatch):
    monkeypatch.setattr(mod, "_point_on_any_monitor",
                        lambda x, y: -1000 < x < 4000 and -1000 < y < 4000)
    data = {"window": {"x": -32000, "y": -32000, "w": 800},
            "window_compact": {"x": 100, "y": 100},
            "webmap_window": {"w": 5},          # no coords: untouched
            "other": 1}
    assert mod._scrub_window_coords(data) is True
    assert data["window"] == {"w": 800}
    assert data["window_compact"] == {"x": 100, "y": 100}
    assert mod._scrub_window_coords(data) is False


def test_load_settings_heals_file_on_disk(mod, data_dir, monkeypatch):
    monkeypatch.setattr(mod, "_point_on_any_monitor", lambda x, y: False)
    (data_dir / "cd_settings.json").write_text(
        json.dumps({"window": {"x": -32000, "y": -32000}}))
    assert mod._load_settings() == {"window": {}}
    assert json.loads((data_dir / "cd_settings.json").read_text()) == {
        "window": {}}


def test_default_hotkeys_shape(mod):
    hk = mod.DEFAULT_HOTKEYS
    assert hk["teleport"]["vk"] == 0x74 and hk["save"]["vk"] == 0x75
    assert hk["abort"]["vk"] == 0x77
    if mod.__name__ == "cdt22":                  # favorites are new in 2.2
        assert [hk[f"fav_{n}"]["vk"] for n in range(1, 7)] == list(
            range(0x64, 0x6A))                   # Num4..Num9
    else:
        assert not any(k.startswith("fav_") for k in hk)
    assert all(v["enabled"] and v["mod"] == 0 for v in hk.values())
    assert mod._hotkey_display(0x74) == "F5"
    assert mod._hotkey_display(0x74, mod.VK_MOD_CTRL) == "Ctrl+F5"
    assert mod.VK_FROM_NAME["Num4"] == 0x64
