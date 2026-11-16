"""TeleportEngine on fake memory: scanning, allocation, hook install and
removal, reads, and the teleport write path. Runs against v2.1.8 and v2.2."""

import struct
import time

import pytest

import fakes
from fakes import BASE, build_image, make_engine, rel32_target, abs_jmp_target


def hooked(mod, monkeypatch, **img):
    eng, pm, k = make_engine(mod, monkeypatch, build_image(**img))
    eng.scan_and_hook()
    return eng, pm, k


# ── scanning ─────────────────────────────────────────────────────────

def test_scan_finds_every_hook_and_records_signature(mod, monkeypatch):
    eng, pm, _ = hooked(mod, monkeypatch, health=True)
    assert eng.hook_a == BASE + fakes.ENTITY_AT + 3
    assert eng.hook_b == BASE + fakes.POS_AT
    assert eng.hook_c == BASE + fakes.HEALTH_AT
    assert eng.hook_d == BASE + fakes.MAP_AT + 5
    assert eng.sig_used == {"Entity": 0, "Position": 0, "Health": 0,
                            "Map dest": 0}
    assert eng.hook_len == {eng.hook_a: 8, eng.hook_b: 7, eng.hook_c: 7,
                            eng.hook_d: 8}
    assert eng.hooks_installed


def test_health_hook_is_optional(mod, monkeypatch):
    eng, pm, _ = hooked(mod, monkeypatch, health=False)
    assert eng.hook_c == 0
    assert eng.sig_used["Health"] == -1
    assert eng.hooks_installed
    # no cave C written, no patch at a health site
    cave_c = eng.block + eng.OFF_CC
    assert pm.read_bytes(cave_c, 16) == bytes(16)
    assert set(eng.orig_bytes) == {eng.hook_a, eng.hook_b, eng.hook_d}
    # set_invuln is a no-op without the hook
    eng.set_invuln(True)
    assert pm.read_bytes(eng.inv, 1) == b"\x00"


def test_set_invuln_writes_flag_when_health_hook_present(mod, monkeypatch):
    eng, pm, _ = hooked(mod, monkeypatch, health=True)
    eng.set_invuln(True)
    assert pm.read_bytes(eng.inv, 1) == b"\x01"
    eng.set_invuln(False)
    assert pm.read_bytes(eng.inv, 1) == b"\x00"


@pytest.mark.parametrize("missing", ["entity", "map"])
def test_missing_required_hook_raises_and_patches_nothing(mod, monkeypatch,
                                                         missing):
    img = build_image(entity_sig=None if missing == "entity" else 0,
                      map_sig=None if missing == "map" else 0)
    eng, pm, k = make_engine(mod, monkeypatch, img)
    with pytest.raises(RuntimeError, match="AOB not found"):
        eng.scan_and_hook()
    assert pm.read_bytes(BASE, fakes.IMAGE_SIZE) == img
    assert k.allocs == []
    assert not eng.hooks_installed


def test_fallback_signatures_used_in_order(mod, monkeypatch):
    eng, _, _ = hooked(mod, monkeypatch, entity_sig=1, map_sig=1)
    assert eng.sig_used["Entity"] == 1
    assert eng.sig_used["Map dest"] == 1
    assert eng.hook_d == BASE + fakes.MAP_AT + 4
    assert eng.hook_len[eng.hook_d] == 7


def test_oldest_map_anchor_is_last_resort(mod, monkeypatch):
    eng, _, _ = hooked(mod, monkeypatch, map_sig=2)
    assert eng.sig_used["Map dest"] == 2


def test_duplicate_position_matches_first_wins(mod, monkeypatch):
    # Pins current behaviour (real build has 5 hits). P4 plans to refuse
    # ambiguous signatures; this test will change then, on purpose.
    eng, _, _ = hooked(mod, monkeypatch, pos_count=3)
    assert eng.hook_b == BASE + fakes.POS_AT


def test_world_offset_is_most_referenced_target(mod, monkeypatch):
    eng, _, _ = hooked(mod, monkeypatch, world_refs=3)
    assert eng.world_offset_addr == fakes.WORLD_BLOCK
    assert eng.get_world_offsets() == fakes.WORLD_OFFSETS


def test_no_world_refs_leaves_offset_unset(mod, monkeypatch):
    img = bytearray(build_image(world_refs=0))
    decoy = fakes.WORLD_REFS_AT + 0x400
    img[decoy:decoy + 8] = bytes(8)   # remove the single decoy too
    eng, _, _ = hooked(mod, monkeypatch) if False else (None, None, None)
    eng, pm, _ = make_engine(mod, monkeypatch, bytes(img))
    eng.scan_and_hook()
    assert eng.world_offset_addr == 0
    assert eng.get_world_offsets() is None


# ── install / uninstall ──────────────────────────────────────────────

def test_live_bytes_changed_since_scan_raises(mod, monkeypatch):
    img = build_image()
    hook_a = BASE + fakes.ENTITY_AT + 3
    holder = {}

    def tamper(addr, size):  # another tool patches the site mid-connect
        holder["pm"].write_bytes(hook_a, b"\xCC", 1)

    eng, pm, k = make_engine(mod, monkeypatch, img, on_alloc=tamper)
    holder["pm"] = pm
    with pytest.raises(RuntimeError, match="changed since scan"):
        eng.scan_and_hook()
    assert eng.orig_bytes == {}
    # nothing but the tamper byte differs from the original image
    now = pm.read_bytes(BASE, fakes.IMAGE_SIZE)
    diff = [i for i in range(len(img)) if now[i] != img[i]]
    assert diff == [hook_a - BASE]


def test_near_patch_is_e9_rel32_plus_nops(mod, monkeypatch):
    eng, pm, _ = hooked(mod, monkeypatch, health=True)
    assert not eng._far_mode
    caves = {eng.hook_a: eng.OFF_CA, eng.hook_b: eng.OFF_CB,
             eng.hook_c: eng.OFF_CC, eng.hook_d: eng.OFF_CD}
    for site, off in caves.items():
        rlen = eng.hook_len[site]
        patch = pm.read_bytes(site, rlen)
        assert rel32_target(patch, site) == eng.block + off
        assert patch[5:] == b"\x90" * (rlen - 5)


def test_caves_reemit_original_bytes_and_jump_back(mod, monkeypatch):
    img = build_image(health=True)
    eng, pm, _ = make_engine(mod, monkeypatch, img)
    eng.scan_and_hook()
    for site, off in ((eng.hook_a, eng.OFF_CA), (eng.hook_b, eng.OFF_CB),
                      (eng.hook_c, eng.OFF_CC), (eng.hook_d, eng.OFF_CD)):
        rlen = eng.hook_len[site]
        orig = img[site - BASE:site - BASE + rlen]
        cave = pm.read_bytes(eng.block + off, 0x80)
        assert orig in cave
        # the cave jumps back past the patched bytes (absolute jmp)
        back = b"\xFF\x25\x00\x00\x00\x00" + struct.pack("<Q", site + rlen)
        assert back in cave


def test_teleport_data_initialised(mod, monkeypatch):
    eng, pm, _ = hooked(mod, monkeypatch)
    td = pm.read_bytes(eng.td, 64)
    assert struct.unpack_from("<f", td, 0x30)[0] == mod.HEIGHT_BOOST
    assert td[:0x30] == bytes(0x30)
    assert pm.read_bytes(eng.md, 24) == bytes(24)


def test_uninstall_restores_original_bytes(mod, monkeypatch):
    img = build_image(health=True)
    eng, pm, _ = make_engine(mod, monkeypatch, img)
    eng.scan_and_hook()
    assert pm.read_bytes(BASE, fakes.IMAGE_SIZE) != img
    eng.uninstall_hooks()
    assert pm.read_bytes(BASE, fakes.IMAGE_SIZE) == img
    assert not eng.hooks_installed


def test_detach_frees_block_and_closes(mod, monkeypatch):
    eng, pm, k = hooked(mod, monkeypatch)
    block = eng.block
    eng.detach()
    assert block in k.freed
    assert pm.closed and not eng.attached


def test_half_install_is_rolled_back_by_detach(mod, monkeypatch, request):
    if mod.__name__ == "cdt218":
        request.applymarker(pytest.mark.xfail(
            strict=True, reason="v2.1.8 detach() skips uninstall when "
            "hooks_installed is False, leaving earlier patches in the game "
            "(fixed in v2.2)"))
    img = build_image()
    eng, pm, _ = make_engine(mod, monkeypatch, img)
    pm.fail_write_at.add(BASE + fakes.MAP_AT + 5)   # 3rd patch fails
    with pytest.raises(OSError):
        eng.scan_and_hook()
    assert eng.orig_bytes       # first patches went in
    eng.detach()
    assert pm.read_bytes(BASE, fakes.IMAGE_SIZE) == img


def test_far_mode_uses_trampolines(mod, monkeypatch):
    img = build_image()
    eng, pm, k = make_engine(mod, monkeypatch, img, far=True)
    eng.scan_and_hook()
    assert eng._far_mode
    assert eng.block == fakes.FAR_BLOCK
    assert len(eng._trampolines) == 3
    caves = {eng.hook_a: eng.OFF_CA, eng.hook_b: eng.OFF_CB,
             eng.hook_d: eng.OFF_CD}
    for tramp, (site, off) in zip(eng._trampolines, caves.items()):
        patch = pm.read_bytes(site, eng.hook_len[site])
        assert rel32_target(patch, site) == tramp
        assert abs_jmp_target(pm.read_bytes(tramp, 14)) == eng.block + off
    eng.detach()
    assert set(eng._trampolines) == set()
    assert set(k.freed) >= {fakes.FAR_BLOCK}
    assert pm.read_bytes(BASE, fakes.IMAGE_SIZE) == img


def test_rel32_out_of_range_raises(mod):
    eng = mod.TeleportEngine()
    assert eng._rel32(0x1000, 0x2000) == 0x2000 - 0x1005
    with pytest.raises(RuntimeError, match="too far"):
        eng._rel32(0x140000000, 0x7FF600000000)
    with pytest.raises(ValueError):
        eng._jmp_patch(0x1000, 0x2000, 4)


# ── reads ────────────────────────────────────────────────────────────

def test_player_pos_zero_is_none(mod, monkeypatch):
    eng, pm, _ = hooked(mod, monkeypatch)
    assert eng.get_player_pos() is None
    pm.write_bytes(eng.td + 0x20, struct.pack("<fff", 1.0, 2.0, 3.0), 12)
    assert eng.get_player_pos() == (1.0, 2.0, 3.0)
    # absolute = local + world offset on X and Z only
    assert eng.get_player_abs() == (1001.0, 2.0, -1997.0)


def test_reads_without_block_are_none(mod):
    eng = mod.TeleportEngine()
    assert eng.get_player_pos() is None
    assert eng.get_map_dest() is None
    assert eng.get_entity_base() == 0
    assert eng.get_world_offsets() is None


def _set_map_dest(eng, pm, xyz, flag=1, marker_set=None):
    pm.write_bytes(eng.md, struct.pack("<fffI", *xyz, flag), 16)
    if marker_set is not None:
        marker = pm.map(0x600000000, 0x100)
        pm.write_bytes(marker + 0x3C, bytes([marker_set]), 1)
        pm.write_bytes(eng.md + 0x10, struct.pack("<Q", marker), 8)


def test_map_dest_needs_flag(mod, monkeypatch):
    eng, pm, _ = hooked(mod, monkeypatch)
    _set_map_dest(eng, pm, (10.0, 20.0, 30.0), flag=0)
    assert eng.get_map_dest() is None
    _set_map_dest(eng, pm, (10.0, 20.0, 30.0), flag=1)
    assert eng.get_map_dest() == (10.0, 20.0, 30.0)


@pytest.mark.parametrize("map_sig,expect_cleared", [(0, True), (1, True),
                                                     (2, False)])
def test_cleared_marker_hides_map_dest(mod, monkeypatch, map_sig,
                                       expect_cleared):
    eng, pm, _ = hooked(mod, monkeypatch, map_sig=map_sig)
    _set_map_dest(eng, pm, (10.0, 20.0, 30.0), marker_set=1)
    assert eng.get_map_dest() == (10.0, 20.0, 30.0)
    pm.write_bytes(0x600000000 + 0x3C, b"\x00", 1)
    got = eng.get_map_dest()
    assert (got is None) == expect_cleared


# ── teleport ─────────────────────────────────────────────────────────

def test_teleport_without_entity_fails(mod, monkeypatch):
    eng, _, _ = hooked(mod, monkeypatch)
    ok, msg = eng.teleport_to_abs(1.0, 2.0, 3.0)
    assert not ok and "entity" in msg.lower()


def test_teleport_writes_local_coords_and_reports(mod, monkeypatch):
    monkeypatch.setattr(mod.TeleportEngine, "TP_HOLD_INTERVAL", 0.001)
    eng, pm, _ = hooked(mod, monkeypatch)
    entity = pm.map(0x500000000, 0x400)
    pm.write_bytes(eng.td + 0x18, struct.pack("<Q", entity), 8)

    ok, msg = eng.teleport_to_abs(1500.0, 300.0, -1500.0)
    assert ok and msg == ""
    # world offset (1000, _, -2000) is subtracted on X and Z only
    assert pm.read_float3(entity + 0x90) == (500.0, 300.0, 500.0)
    assert pm.read_float3(entity + 0x1A0) == (500.0, 300.0, 500.0)
    assert struct.unpack("<i", pm.read_bytes(eng.td + 0x10, 4))[0] == 60

    deadline = time.time() + 5
    while eng.last_tp_report is None and time.time() < deadline:
        time.sleep(0.02)
    assert eng.last_tp_report == (0.0, True, entity)


def test_teleport_hold_reports_drift(mod, monkeypatch):
    monkeypatch.setattr(mod.TeleportEngine, "TP_HOLD_INTERVAL", 0.001)
    monkeypatch.setattr(mod.TeleportEngine, "TP_HOLD_WRITES", 0)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    eng, pm, _ = hooked(mod, monkeypatch)
    entity = pm.map(0x500000000, 0x400)
    pm.write_bytes(eng.td + 0x18, struct.pack("<Q", entity), 8)
    real_write = eng._write_pos
    calls = []

    def write_then_game_reverts(e, lx, ly, lz):
        calls.append(1)
        real_write(e, lx, ly, lz)
        if len(calls) == 1:   # game snaps the player 30 units back
            pm.write_bytes(e + 0x90, struct.pack("<fff", lx + 30, ly, lz), 12)

    eng._write_pos = write_then_game_reverts
    ok, _ = eng.teleport_to_abs(1000.0, 0.0, -2000.0)
    assert ok
    deadline = time.time() + 5
    while eng.last_tp_report is None and time.time() < deadline:
        pass
    dist, same, ent = eng.last_tp_report
    assert dist == pytest.approx(30.0) and same and ent == entity
