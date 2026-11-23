"""Shared test setup.

The product files exit at import time when not run as admin, and import
pymem only in the main run. Setting _CD_WEBMAP_CHILD while loading skips
both (the same path the map subprocess uses), so the modules load as plain
libraries with no product change. LOCALAPPDATA points at a temp dir first,
so nothing at module level can touch the real %LocalAppData%\\CD_Teleport.

Each version is loaded under its own name:
  cdt22  = v2.2/cd_teleporter.py
  cdt218 = v2.1.8/cd_teleporter.py
  cdt23  = v2.3/cd_teleporter.py (P2 working copy, not yet tested in game)
"""

import importlib.util
import os
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO, "tests")
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)

_SESSION_APPDATA = tempfile.mkdtemp(prefix="cdtele-tests-")
os.environ["LOCALAPPDATA"] = _SESSION_APPDATA

VERSIONS = {
    "cdt22": os.path.join(REPO, "v2.2", "cd_teleporter.py"),
    "cdt218": os.path.join(REPO, "v2.1.8", "cd_teleporter.py"),
    "cdt23": os.path.join(REPO, "v2.3", "cd_teleporter.py"),
}


def _load(name, path):
    """Load one product file as module `name`, without admin/pymem and
    without picking up a locally bundled pywebview from its pylibs/."""
    saved_path = list(sys.path)
    had_webview = "webview" in sys.modules
    saved_webview = sys.modules.get("webview")
    sys.modules["webview"] = None          # import webview -> ImportError
    os.environ["_CD_WEBMAP_CHILD"] = "1"
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    finally:
        os.environ.pop("_CD_WEBMAP_CHILD", None)
        sys.path[:] = saved_path           # drop the pylibs/ entry
        if had_webview:
            sys.modules["webview"] = saved_webview
        else:
            sys.modules.pop("webview", None)
    return mod


MODULES = {name: _load(name, path) for name, path in VERSIONS.items()}
cdt22 = MODULES["cdt22"]
cdt218 = MODULES["cdt218"]
cdt23 = MODULES["cdt23"]


def _redirect_files(mod, monkeypatch, root):
    save_dir = str(root)
    monkeypatch.setattr(mod, "SAVE_DIR", save_dir)
    monkeypatch.setattr(mod, "SAVE_FILE",
                        os.path.join(save_dir, "cd_waypoints.json"))
    monkeypatch.setattr(mod, "SETTINGS_FILE",
                        os.path.join(save_dir, "cd_settings.json"))
    monkeypatch.setattr(mod, "CALIBRATION_FILES", {
        "pywel": os.path.join(save_dir, "cd_calibration_pywel.json"),
        "abyss": os.path.join(save_dir, "cd_calibration_abyss.json"),
    })
    monkeypatch.setattr(mod, "_LEGACY_CALIBRATION_FILE",
                        os.path.join(save_dir, "cd_calibration.json"))


def _no_network(*_a, **_k):
    raise AssertionError("tests must never touch the network")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Every test: files go to tmp_path, network is forbidden."""
    data = tmp_path / "CD_Teleport"
    data.mkdir()
    for mod in MODULES.values():
        _redirect_files(mod, monkeypatch, data)
        monkeypatch.setattr(mod, "urlopen", _no_network)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return data


@pytest.fixture
def data_dir(_isolate):
    return _isolate


@pytest.fixture(params=["cdt218", "cdt22", "cdt23"])
def mod(request):
    """Run a test against v2.1.8, v2.2 and the v2.3 working copy."""
    return MODULES[request.param]
