"""WaypointStore: persistence, community CSV parsing, submit URL."""

import pytest


class Resp:
    def __init__(self, text):
        self._b = text.encode("utf-8")

    def read(self):
        return self._b


def fake_urlopen(monkeypatch, mod, text=None, exc=None, seen=None):
    def _open(req, timeout=None):
        if seen is not None:
            seen.append(req)
        if exc:
            raise exc
        return Resp(text)
    monkeypatch.setattr(mod, "urlopen", _open)


def test_add_persists_and_reloads_unicode(mod, data_dir):
    s = mod.WaypointStore()
    s.add("Café ★ 龍", 1.5, 2.5, -3.5)
    raw = (data_dir / "cd_waypoints.json").read_text(encoding="utf-8")
    assert "龍" in raw            # ensure_ascii=False
    s2 = mod.WaypointStore()
    s2.load()
    assert s2.local == [{"name": "Café ★ 龍", "absX": 1.5,
                         "absY": 2.5, "absZ": -3.5}]


def test_delete_rename_update_swap(mod):
    s = mod.WaypointStore()
    for i in range(3):
        s.add(f"w{i}", i, i, i)
    s.rename(1, "mid")
    s.update_coords(2, 9.0, 8.0, 7.0)
    s.swap(0, 2)
    assert [w["name"] for w in s.local] == ["w2", "mid", "w0"]
    assert s.local[0]["absX"] == 9.0
    s.delete(1)
    assert [w["name"] for w in s.local] == ["w2", "w0"]
    # out-of-range indexes are ignored
    s.delete(9)
    s.rename(-1, "x")
    s.swap(0, 5)
    s.update_coords(7, 1, 1, 1)
    assert [w["name"] for w in s.local] == ["w2", "w0"]
    s2 = mod.WaypointStore()
    s2.load()
    assert s2.local == s.local


def test_load_missing_file_is_empty(mod):
    s = mod.WaypointStore()
    s.load()
    assert s.local == []


CSV = ('Timestamp,Name,X,Y,Z\n'
       '2026-01-01,"Quoted Name",100.5,20,-300\n'
       '2026-01-01,Plain Name,1,2,3\n'
       '2026-01-01,"Bad coords",abc,2,3\n'
       'garbage line\n')


def test_fetch_shared_parses_rows_and_skips_bad(mod, monkeypatch):
    seen = []
    fake_urlopen(monkeypatch, mod, CSV, seen=seen)
    s = mod.WaypointStore()
    ok, msg = s.fetch_shared()
    assert ok and "Loaded 2" in msg
    assert [w["name"] for w in s.shared] == ["Quoted Name", "Plain Name"]
    assert s.shared[0]["absX"] == 100.5 and s.shared[0]["absZ"] == -300.0
    assert "_t=" in seen[0].full_url      # cache-bust


def test_fetch_shared_header_only_is_false(mod, monkeypatch):
    fake_urlopen(monkeypatch, mod, "Timestamp,Name,X,Y,Z\n")
    ok, msg = mod.WaypointStore().fetch_shared()
    assert not ok and "No waypoints" in msg


def test_fetch_shared_network_error_is_false(mod, monkeypatch):
    fake_urlopen(monkeypatch, mod, exc=OSError("down"))
    ok, msg = mod.WaypointStore().fetch_shared()
    assert not ok and "down" in msg


def test_submit_url_is_encoded(mod, monkeypatch):
    seen = []
    fake_urlopen(monkeypatch, mod, "", seen=seen)
    assert mod.WaypointStore().submit("a b&c=d", 1.0, 2.0, 3.0)
    url = seen[0]
    assert "a+b%26c%3Dd" in url and "&c=d" not in url
    assert "1.000000" in url
    fake_urlopen(monkeypatch, mod, exc=OSError("x"))
    assert mod.WaypointStore().submit("n", 1, 2, 3) is False


# Known bugs from the plan. xfail(strict): when the bug is fixed these flip
# to XPASS and fail loudly, so the marker gets removed on purpose.

@pytest.mark.xfail(strict=True,
                   reason="plan #8 / P3: corrupt file silently replaced")
def test_corrupt_waypoint_file_is_not_overwritten(mod, data_dir):
    f = data_dir / "cd_waypoints.json"
    f.write_text('[{"name": "precious", "absX": 1', encoding="utf-8")
    s = mod.WaypointStore()
    s.load()
    s.add("new", 1, 2, 3)
    kept = [p for p in data_dir.iterdir()
            if "precious" in p.read_text(encoding="utf-8", errors="ignore")]
    assert kept          # the corrupt original must survive somewhere


@pytest.mark.xfail(strict=True,
                   reason="plan #9 / P3: community coords not validated")
@pytest.mark.parametrize("bad", ["nan", "inf", "1e30"])
def test_fetch_shared_rejects_non_finite_or_huge_coords(mod, monkeypatch,
                                                        bad):
    fake_urlopen(monkeypatch, mod,
                 f"h\nt,Evil,{bad},0,0\nt,Good,10,10,10\n")
    s = mod.WaypointStore()
    s.fetch_shared()
    assert [w["name"] for w in s.shared] == ["Good"]
