"""TeleporterApp methods that hold the rules (height, Return stack, F6),
called on a stub `self` so no Tk window is created. v2.2 only where the
feature is new in 2.2."""

import types

import pytest

import conftest
from fakes import FakeEngine

cdt22 = conftest.cdt22


class Var:
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


def stub(adv=False, override=False, height=1200.0, **extra):
    s = types.SimpleNamespace(
        _adv_enabled_var=Var(adv), _height_override_var=Var(override),
        _adv_height=height, engine=FakeEngine(), return_stack=[],
        bottom_var=Var(""), msgs=[], **extra)
    s._themed_msgbox = lambda *a, **k: s.msgs.append(a)
    s._refresh_return_btn = lambda: None
    s._push_origin = lambda apos: cdt22.TeleporterApp._push_origin(s, apos)
    s._refresh_return_btn = lambda: None
    return s


# ── height rules ─────────────────────────────────────────────────────

@pytest.mark.parametrize("adv,override,map_y,want", [
    (False, False, 55.0, 55.0),
    (False, False, 0.0, None),       # no height data, Advanced off
    (False, True, 55.0, 55.0),       # override ignored while Advanced off
    (True, True, 55.0, 1200.0),
    (True, True, 0.0, 1200.0),
    (True, False, 0.0, 1200.0),      # only fills in when map Y is 0
    (True, False, 55.0, 55.0),
])
def test_effective_height(mod, adv, override, map_y, want):
    s = stub(adv, override)
    assert mod.TeleporterApp._get_effective_height(s, map_y) == want


# ── Return stack (2.2) ───────────────────────────────────────────────

def test_return_stack_keeps_last_five_and_pops_newest_first():
    s = stub()
    for i in range(8):
        s._push_origin((i, 0, 0))
    assert cdt22.RETURN_STACK_MAX == 5
    assert [p[0] for p in s.return_stack] == [3, 4, 5, 6, 7]
    cdt22.TeleporterApp._abort_teleport(s)
    assert s.engine.teleports == [(7, 0, 0)]
    assert len(s.return_stack) == 4
    assert "4 more" in s.bottom_var.v


def test_push_origin_ignores_missing_position():
    s = stub()
    s._push_origin(None)
    assert s.return_stack == []


def test_failed_return_repushes_and_shows_error():
    s = stub()
    s._push_origin((1, 2, 3))
    s.engine.fail_next = "no entity"
    cdt22.TeleporterApp._abort_teleport(s)
    assert s.return_stack == [(1, 2, 3)]
    assert s.bottom_var.v == "no entity"


def test_return_with_empty_stack_says_so():
    s = stub()
    cdt22.TeleporterApp._abort_teleport(s)
    assert "Nothing to return" in s.bottom_var.v
    assert s.engine.teleports == []


def test_return_button_text(monkeypatch):
    s = stub()
    btn = types.SimpleNamespace(text=None,
                                configure=lambda text: setattr(btn, "text", text))
    s._return_btn = btn
    s.return_stack = [(1, 1, 1)] * 3
    cdt22.TeleporterApp._refresh_return_btn(s)
    assert btn.text == "Return (3)"
    s.return_stack = []
    cdt22.TeleporterApp._refresh_return_btn(s)
    assert btn.text == "Return"


# ── teleport to map marker ───────────────────────────────────────────

def test_teleport_to_map_adds_boost_and_pushes_origin(mod):
    s = stub(adv=False, _trigger_invuln=lambda: None)
    s._get_effective_height = lambda y: mod.TeleporterApp._get_effective_height(s, y)
    s._push_origin = lambda apos: None
    s.engine.map_dest = (10.0, 50.0, 30.0)
    mod.TeleporterApp._teleport_to_map(s)
    assert s.engine.teleports == [(10.0, 50.0 + mod.HEIGHT_BOOST, 30.0)]


def test_teleport_to_map_without_marker_does_nothing(mod):
    s = stub()
    mod.TeleporterApp._teleport_to_map(s)
    assert s.engine.teleports == []
    assert "No map marker" in s.bottom_var.v


# ── known bug ────────────────────────────────────────────────────────

@pytest.mark.xfail(strict=True,
                   reason="plan #7 / P5: F6 does nothing while Advanced is on "
                          "(Advanced is on by default since 2.1.8)")
def test_f6_saves_with_default_settings_instead_of_popup(mod):
    s = stub(adv=True)               # Advanced default-on
    s._themed_askstring = lambda *a, **k: "spot"
    s.waypoints = types.SimpleNamespace(added=[],
                                        add=lambda *a: s.waypoints.added.append(a))
    s._refresh_local_list = lambda: None
    s.engine.map_dest = (1.0, 2.0, 3.0)
    mod.TeleporterApp._save_map_marker(s)
    assert s.msgs == [] and s.waypoints.added
