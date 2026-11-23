"""Exact hook bytes. A refactor that changes one byte of a patch or cave
fails here before an exe is built. Regenerate on purpose with
UPDATE_SNAPSHOTS=1 (then review the fixture diff)."""

import json
import os

from fakes import BASE, build_image, make_engine

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "hook_snapshot.json")


def snapshot(mod, monkeypatch, far):
    eng, pm, _ = make_engine(mod, monkeypatch, build_image(health=True),
                             far=far)
    eng.scan_and_hook()
    sites = {"A": eng.hook_a, "B": eng.hook_b, "C": eng.hook_c,
             "D": eng.hook_d}
    out = {"block_offset": "far" if far else hex(eng.block - BASE),
           "patches": {}, "caves": {}}
    for name, addr in sites.items():
        out["patches"][name] = {
            "offset": hex(addr - BASE),
            "bytes": pm.read_bytes(addr, eng.hook_len[addr]).hex()}
    for name, off in (("A", eng.OFF_CA), ("B", eng.OFF_CB),
                      ("C", eng.OFF_CC), ("D", eng.OFF_CD)):
        out["caves"][name] = pm.read_bytes(eng.block + off, 0x80).hex()
    out["trampolines"] = [pm.read_bytes(t, 14).hex()
                          for t in eng._trampolines]
    out["data_init"] = pm.read_bytes(eng.block, 0x100).hex()
    return out


def current(mod, monkeypatch):
    return {"near": snapshot(mod, monkeypatch, False),
            "far": snapshot(mod, monkeypatch, True)}


def test_v22_hooks_identical_to_v218(monkeypatch):
    import conftest
    assert (current(conftest.cdt218, monkeypatch)
            == current(conftest.cdt22, monkeypatch))


def test_hook_bytes_match_snapshot(monkeypatch):
    import conftest
    now = current(conftest.cdt22, monkeypatch)
    if os.environ.get("UPDATE_SNAPSHOTS"):
        os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
        with open(FIXTURE, "w", encoding="utf-8") as f:
            json.dump(now, f, indent=1, sort_keys=True)
            f.write("\n")
    with open(FIXTURE, encoding="utf-8") as f:
        assert now == json.load(f)


def test_v23_hooks_identical_to_v22(monkeypatch):
    """The P2 working copy must not change a single hook byte."""
    import conftest
    assert (current(conftest.cdt22, monkeypatch)
            == current(conftest.cdt23, monkeypatch))
