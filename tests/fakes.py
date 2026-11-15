"""Fake game memory, fake kernel32 and a synthetic game image.

Nothing here talks to a real process. FakePM stands in for pymem.Pymem,
FakeK32 for the module-level `k32` (VirtualAllocEx / VirtualFreeEx).
"""

import struct
import threading
import types

BASE = 0x140000000          # fake image base (typical x64 exe base)
IMAGE_SIZE = 0x20000
FAR_BLOCK = 0x7FF600000000  # where "Windows" puts a block when addr == 0
HANDLE = 0x1234

# Offsets of the hook sites inside the synthetic image
ENTITY_AT = 0x1000
POS_AT = 0x2000
HEALTH_AT = 0x3000
MAP_AT = 0x4000
WORLD_REFS_AT = 0x6000
WORLD_BLOCK = BASE + 0x9000     # most referenced world-origin block
WORLD_DECOY = BASE + 0xA000     # referenced once

ENTITY_SIGS = [
    bytes.fromhex("48 8B 07 C5 F8 11 88 B0 01 00 00"),  # #0 (1.0.0.3576)
    bytes.fromhex("48 8B 06 C5 F8 11 88 B0 01 00 00"),  # #1
]
POS_SIG = bytes.fromhex("0F 11 99 90 00 00 00")
HEALTH_SIG = bytes.fromhex("48 8B 46 08 48 89 F1")
MAP_SIGS = [
    bytes.fromhex("C4 C1 7B 10 07 C5 FB 11 02 41 8B 47 08 89 42 08 "
                  "80 7B 3C 00 75 05 4C 8D 43 10"),    # #0 hook +5 len 8
    bytes.fromhex("C5 FB 10 07 C5 FB 11 02 8B 47 08 89 42 08 "
                  "80 7B 3C 00 75 05 4C 8D 43 10"),    # #1 hook +4 len 7
    bytes.fromhex("C5 FB 10 07 C5 FB 11 02 8B 47 08 89 42 08"),  # #2
]
WORLD_OFFSETS = (1000.0, 0.0, -2000.0, 0.0)


def build_image(entity_sig=0, map_sig=0, health=False, pos_count=1,
                world_refs=3):
    """Return image bytes with the requested signature variants."""
    img = bytearray(IMAGE_SIZE)
    if entity_sig is not None:
        s = ENTITY_SIGS[entity_sig]
        img[ENTITY_AT:ENTITY_AT + len(s)] = s
    for k in range(pos_count):
        at = POS_AT + k * 0x100
        img[at:at + len(POS_SIG)] = POS_SIG
    if health:
        img[HEALTH_AT:HEALTH_AT + len(HEALTH_SIG)] = HEALTH_SIG
    if map_sig is not None:
        s = MAP_SIGS[map_sig]
        img[MAP_AT:MAP_AT + len(s)] = s

    def vsubps(at, target):
        disp = target - (BASE + at + 8)
        img[at:at + 4] = b"\xC5\xF8\x5C\x05"
        struct.pack_into("<i", img, at + 4, disp)

    for k in range(world_refs):
        vsubps(WORLD_REFS_AT + k * 0x40, WORLD_BLOCK)
    vsubps(WORLD_REFS_AT + 0x400, WORLD_DECOY)
    struct.pack_into("<ffff", img, WORLD_BLOCK - BASE, *WORLD_OFFSETS)
    struct.pack_into("<ffff", img, WORLD_DECOY - BASE, 9.0, 9.0, 9.0, 9.0)
    return bytes(img)


class FakePM:
    """Sparse process memory: a list of (start, bytearray) regions."""

    def __init__(self):
        self.regions = []
        self.process_handle = HANDLE
        self.closed = False
        self.fail_write_at = set()   # addresses whose write raises
        self.writes = []             # (addr, bytes) log
        self._lock = threading.Lock()

    def map(self, start, data_or_size):
        buf = (bytearray(data_or_size) if isinstance(data_or_size, int)
               else bytearray(data_or_size))
        self.regions.append((start, buf))
        return start

    def overlaps(self, start, size):
        return any(start < s + len(b) and s < start + size
                   for s, b in self.regions)

    def _find(self, addr, n):
        for s, b in self.regions:
            if s <= addr and addr + n <= s + len(b):
                return s, b
        raise OSError(f"unmapped read/write at {addr:#x} (+{n})")

    def read_bytes(self, addr, n):
        with self._lock:
            s, b = self._find(addr, n)
            return bytes(b[addr - s:addr - s + n])

    def write_bytes(self, addr, data, n):
        if addr in self.fail_write_at:
            raise OSError(f"write refused at {addr:#x}")
        with self._lock:
            s, b = self._find(addr, n)
            b[addr - s:addr - s + n] = bytes(data[:n])
            self.writes.append((addr, bytes(data[:n])))

    def write_int(self, addr, value):
        self.write_bytes(addr, struct.pack("<i", value), 4)

    def read_ulonglong(self, addr):
        return struct.unpack("<Q", self.read_bytes(addr, 8))[0]

    def read_float3(self, addr):
        return struct.unpack("<fff", self.read_bytes(addr, 12))

    def close_process(self):
        self.closed = True


class FakeK32:
    """VirtualAllocEx / VirtualFreeEx over a FakePM.

    near mode: any requested address that is free gets allocated there.
    far mode:  requests for a specific address fail until the main block
               has been allocated with addr == 0 (forces trampolines).
    """

    def __init__(self, pm, far=False, on_alloc=None):
        self.pm = pm
        self.far = far
        self.on_alloc = on_alloc
        self.allocs = []
        self.freed = []
        self.calls = 0

    def VirtualAllocEx(self, handle, addr, size, _type, _prot):
        self.calls += 1
        if addr == 0:
            addr = FAR_BLOCK
        elif self.far and not self.allocs:
            return 0
        if addr <= 0 or self.pm.overlaps(addr, size):
            return 0
        self.pm.map(addr, size)
        self.allocs.append((addr, size))
        if self.on_alloc:
            self.on_alloc(addr, size)
        return addr

    def VirtualFreeEx(self, handle, addr, size, _type):
        self.freed.append(addr)
        return 1


def make_engine(mod, monkeypatch, image=None, far=False, on_alloc=None):
    """A TeleportEngine wired to a FakePM holding `image` at BASE."""
    pm = FakePM()
    pm.map(BASE, image if image is not None else build_image())
    k = FakeK32(pm, far=far, on_alloc=on_alloc)
    monkeypatch.setattr(mod, "k32", k)
    eng = mod.TeleportEngine()
    eng.pm = pm
    eng.module = types.SimpleNamespace(lpBaseOfDll=BASE, SizeOfImage=IMAGE_SIZE)
    eng.attached = True
    return eng, pm, k


def rel32_target(patch, at):
    """Where an E9 rel32 jump written at `at` lands."""
    assert patch[0] == 0xE9
    return at + 5 + struct.unpack("<i", patch[1:5])[0]


def abs_jmp_target(code):
    """Target of an FF 25 00000000 <u64> absolute jump."""
    assert code[:6] == b"\xFF\x25\x00\x00\x00\x00"
    return struct.unpack("<Q", code[6:14])[0]


class FakeEngine:
    """Minimal stand-in for TeleportEngine used by the UI tests."""

    def __init__(self):
        self.attached = True
        self.hooks_installed = True
        self.hook_c = 0
        self.pos = (100.0, 50.0, 200.0)
        self.map_dest = None
        self.teleports = []
        self.fail_next = None
        self.last_tp_report = None
        self.pm = None
        self.invuln = []

    def get_player_pos(self):
        return self.pos

    def get_player_abs(self):
        return self.pos

    def get_entity_base(self):
        return 0x500000000

    def get_map_dest(self):
        return self.map_dest

    def set_invuln(self, on):
        self.invuln.append(on)

    def teleport_to_abs(self, x, y, z):
        if self.fail_next:
            err, self.fail_next = self.fail_next, None
            return False, err
        self.teleports.append((x, y, z))
        self.pos = (x, y, z)
        return True, ""

    def uninstall_hooks(self):
        pass

    def detach(self):
        self.attached = False
