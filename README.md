# Crimson Desert Teleporter Tool

A standalone teleportation and waypoint manager for **Crimson Desert** — with an integrated interactive world map.

Prebuilt Windows binaries and source bundles are attached to each [GitHub Release](https://github.com/DameonK/Crimson-Desert-Teleporation-Tool/releases). The latest upstream release is **v2.1.7**.

> **This fork** ([PHTMGatt/Crimson-Desert-Teleporation-Tool](https://github.com/PHTMGatt/Crimson-Desert-Teleporation-Tool)) adds **v2.1.8**: fixed hooks for game build **1.0.0.3576** (Steam, Nov 2026, game 2.04.08 + "Charting the Unknown") and native height hotkeys. See [What's new in v2.1.8](#whats-new-in-v218-fork).

---

## What's new in v2.1.8 (fork)

**Fixes "Entity hook AOB not found — game version mismatch?"** on game build 1.0.0.3576 ([upstream issue #5](https://github.com/DameonK/Crimson-Desert-Teleporation-Tool/issues/5)).

- **Multi-signature hook scanner.** Every hook now has an ordered list of AOB signatures (newest game build first, older ones kept as fallbacks, `??` wildcards supported). The code caves re-emit the exact original bytes read from the hook site, so a register change between builds no longer needs new cave code. Before patching, the tool checks that the live bytes still match what it scanned.
- **Health hook is optional.** If its signature is missing, the tool still attaches and teleports; only the 10 s post-teleport invulnerability is turned off (the status bar says so).
- **Height hotkeys.** Three new rebindable hotkeys set the teleport height instantly, no trip to the Advanced tab: **Num1 = Low (500)**, **Num2 = Med (800)**, **Num3 = High (1200)**. Edit the three values under *Advanced → Height Hotkeys*. Pressing one turns Advanced mode on if it was off.
- **Height + teleport combo (optional).** Tick *Advanced → "Height hotkeys also teleport to the map marker"* and Num1/2/3 set the height and teleport in one press.
- **Advanced options on by default** (for new installs; an existing saved choice is kept).
- Build script also installs `typing_extensions` (needed by newer pywebview).

### Hook status on 1.0.0.3576 (static scan of the on-disk exe)

| Hook | Result | What changed | Confidence |
|---|---|---|---|
| Entity (`vmovups [rax+1B0],xmm1`) | **Fixed**, 1 unique hit @ `14398344B` | Pointer now loaded from `[rdi]` instead of `[rsi]`; same store, same struct offsets | Medium-high: unique store to `+1B0`, cave only uses `rax`, `xmm0` and flags are dead after the site |
| Position (`movups [rcx+90],xmm3`) | Unchanged, first of 5 hits | — | Same as every build since v1.0 |
| Map marker (`vmovsd [rdx],xmm0`) | **Fixed**, 1 unique hit @ `140F9B3E1` | Load now via `r15` (`C4 C1 7B 10 07` / `41 8B 47 08`), hook is 8 bytes. Anchored on the `cmp byte [rbx+3C],0` marker-initialised check (same anchor as upstream PR #4 and v1.0.1). The old 14-byte v2.1.7 pattern now hits 5 generic vector copies, so it is only a last-resort fallback | High |
| World offset (`vsubps xmm0,xmm0,[rip+X]`) | Unchanged, 21 of 26 hits agree | — | High |
| Health (`mov rax,[rsi+8]; mov rcx,rsi`) | **Not found** | Routine refactored; no safe replacement found statically (closest hits use `[rsi+8]` as a pointer, so patching them would corrupt memory). Invulnerability is disabled on this build instead of guessing | — |

Verified only by static analysis of the exe on disk. The live in-game test is still to do.

---

## Features

### Teleportation

- **Map Marker Teleport** — Open the in-game map, place a destination marker (red X) on any landmark, press your teleport hotkey, and you're there.
- **World Map Teleport** — Click anywhere on the integrated MapGenie map to set a destination and teleport from the map window.
- **Waypoint Teleport** — Select any saved waypoint and teleport instantly, or double-click to go.
- **Return / Abort** — Snap back to your pre-teleport position with the Return hotkey.
- **10s Invulnerability** — Automatic invulnerability window after each teleport so a bad landing won't kill you.

### Interactive World Map

- **MapGenie integration** — Full interactive map with points of interest, in its own window.
- **Live player tracking** — Your position shows in real time as an orange marker.
- **Follow player** — Toggle to keep the map centered as you move.
- **Click-to-teleport** — Click any spot on the map to set a destination, then hit Teleport. Click the destination X again to clear it.
- **Waypoint markers** — Local waypoints render as yellow dots, community waypoints as light-blue dots (toggle in Advanced).
- **Multi-realm support** — Auto-switches between Pywel and Abyss based on player height; separate calibration data per realm.
- **In-map calibration** — Built-in tool for fine-tuning the game-to-map coordinate mapping per realm.
- **Height presets** — Ground / Abyss / Custom selector right on the map toolbar.
- **Window persistence** — Position and size remembered across sessions, including multi-monitor setups.

### Waypoint Manager

- **Save Position** — Press the hotkey or click Save to bookmark your current location with a custom name.
- **Local library** — Personal waypoints saved as JSON in `%LocalAppData%\CD_Teleport`, easy to back up or share.
- **Drag-and-drop reordering**, **multi-select** (Ctrl/Shift+Click), **search/filter**, and right-click context menus.
- **Manual entry** — Add waypoints by typing exact X / Y / Z coordinates.

### Community Waypoints

- **Shared database** — Browse waypoints submitted by other players, auto-loaded on launch.
- **One-click contribute** — Submit your own waypoints to the shared database.
- **Copy to local** — Pull individual entries (or the whole list) into your personal library.

### Advanced Options

- **Custom teleport height** — Many map markers have no Y data. Advanced mode lets you set a default height so those teleports still work.
- **Ground / Abyss presets** — Quick height presets (1200 / 2400) plus manual entry for precise control.
- **Height override** — Force every map-marker teleport to use your custom height, ignoring the marker's original Y.
- **Always-start-advanced** — Persist the toggle so Advanced mode is on at launch.
- **Map marker visibility** — Toggle local and community markers on/off on the world map.

### Customizable Hotkeys

- All hotkeys rebindable in the UI — click a key badge and press the new key.
- Modifier combos supported (Ctrl / Alt / Shift + key).
- Each hotkey individually toggleable on/off.
- Persisted between sessions automatically.

---

## Default Hotkeys

```
F5    Teleport to map marker
F6    Save current position as waypoint
F8    Return to pre-teleport position (abort)
Num1  Set teleport height: Low  (500)   v2.1.8+
Num2  Set teleport height: Med  (800)   v2.1.8+
Num3  Set teleport height: High (1200)  v2.1.8+
```

Num-pad hotkeys need Num Lock on.

---

## Installation

**Easiest path:** download `CrimsonDesertTeleporter-v2.1.7.exe` from the [latest release](https://github.com/DameonK/Crimson-Desert-Teleporation-Tool/releases/latest) and double-click it (it requests Administrator automatically).

**From source:** clone the repo (or download the release zip), then double-click `v2.1.7/run_teleporter.bat`. The launcher handles everything:

- Requests Administrator privileges (required for memory access).
- Finds a usable Python install — or downloads Python 3.12 to a local folder if none is present.
- Installs `pymem` + `pywebview` into a local `pylibs/` so nothing gets added to your global site-packages.
- Launches the program.

---

## How to use

1. Launch the game and load into the world with your character.
2. Run the teleporter (exe or `.bat`). It will detect and attach to the running game automatically.
3. Wait for **Connected** — the indicator in the top-right turns green once the hooks are installed.
4. Move around in-game for a step or two so the tool can capture your player entity.
5. Teleport! Open the map, place a marker, and press **F5**. Or pick a saved waypoint and double-click it. Or open the World Map, click a spot, and hit Teleport on the map toolbar.
6. Press **F8** if you don't like where you landed.

### Using the World Map

1. Click **World Map** in the main UI to open it.
2. Your player position shows as an orange dot, updating live.
3. Click anywhere to set a destination (red X). Click the X again to clear it.
4. Toggle **Follow Player** to keep the map centered on you.
5. Pick the right **Height** preset (Ground / Abyss / Custom) for areas without elevation data.
6. The map auto-switches between Pywel and Abyss based on player height.

### Using Advanced Mode

1. Open the **Advanced** tab.
2. Check **Enable Advanced Options**.
3. Pick a height preset (Ground / Abyss) or enter a custom value.
4. Now teleports to map markers without height data use your configured height instead of being rejected.
5. Enable **Always override** if you want every map teleport to ignore the marker's Y.
6. To save accurate waypoints in Advanced mode: teleport to the location first, land on the ground, *then* click **Save Position**.

---

## Building from source

`v2.1.8/build_exe.bat` (or any version folder's copy) produces a fresh `dist/CrimsonDesertTeleporter.exe` from `cd_teleporter.py`:

1. **Locate a Python** with `tkinter` — checks, in order: a bundled `python/python.exe` next to the script, the `py` launcher, `where python` on PATH, and common install paths under `%LocalAppData%` / `%ProgramFiles%`. Windows Store stub pythons are skipped.
2. **Ensure dependencies** — if `pymem` or `pywebview` can't be imported, bootstraps `pip` (via `ensurepip` if needed) and installs `pymem`, `pywebview`, `bottle`, `proxy_tools` and `typing_extensions` into a local `pylibs/` folder.
3. **Ensure PyInstaller** — installs it into the chosen Python if missing (this is the one install outside the folder).
4. **Build** — runs PyInstaller with `--onefile --windowed --uac-admin` (the exe requests Administrator on launch, which the tool needs to read game memory), embeds `teleporter.ico`, includes `pymem`/`webview` submodules, and points at the local `pylibs/`.

Output: `dist/CrimsonDesertTeleporter.exe`. Re-running the script re-uses the cached `pylibs/` and is much faster the second time.

---

## FAQ

**Status says "Waiting for game…" but the game is running.**
Make sure the teleporter is running as Administrator. The `.bat` launcher does this automatically; if you're running `python` directly, launch your terminal as Administrator first.

**I teleported and fell through the ground / died.**
The 10-second invulnerability window protects you in most cases. If you land somewhere weird, press **F8** to return. Some map locations are on geometry that hasn't streamed in yet — try placing the marker closer or on a visible landmark.

**Map marker teleport says "no height data" or Y=0.**
Many map markers don't include elevation. Enable Advanced Options and set a height preset (Ground or Abyss) to teleport to those locations anyway.

**The World Map button doesn't work / map won't open.**
The map requires `pywebview`. The `.bat` launcher installs it automatically. If running manually, install it with `pip install pywebview`.

**The game updated and the teleporter shows "AOB not found."**
The hooked instructions in `CrimsonDesert.exe` shifted in a game update. I update when I have time. The source is open (`v*/cd_teleporter.py` — search for the `SIG_*` lists (v2.1.8+) or `AOB_*` constants (older) near the top of the `TeleportEngine` class) so anyone can fork and patch.

**The teleporter shows "Entity hook AOB not found — game version mismatch?" but the game *didn't* update.**
A few possibilities, in rough order of likelihood:

1. Multiple copies of the teleporter are running. Close them all and try again.
2. A previous run didn't release its hooks cleanly. Restart the game to clear them.
3. Another mod / trainer / cheat table is hooking the same memory locations. Disable other tools and retry.
4. The game *did* actually update.

**Can I share my waypoints with friends?**
Yes — they live as JSON in `%LocalAppData%\CD_Teleport`. Share the files directly, or use the **Contribute** button to submit them to the shared community database other users can browse.

---

## Game version compatibility

The tool relies on AOB (array-of-bytes) signatures to locate hook points inside the game executable. Every time the game updates, those signatures may shift and need re-verifying. The latest released version targets the most recent game build I've tested against; older releases are kept available in case the game-build matchup matters for you.

| Tool version | Game build |
|---|---|
| v2.1.8 (fork) | 1.0.0.3576 (Nov 2026), with fallbacks for the 2026-04 / 2026-07 builds |
| v2.1.7 | 2026-04 build (the map hook needs upstream PR #4 for the 2026-07 build) |

---

## Requirements

- Windows 10 / 11
- Administrator privileges (for game memory access)
- Python 3.10+ if running from source (the `.bat` launcher will install Python 3.12 locally if you don't have one)
- `pymem` and `pywebview` (auto-installed by the `.bat` launcher into a local `pylibs/` folder)

---

## Credits

- **DameonK** — author of the Crimson Desert Teleporter Tool (upstream: [DameonK/Crimson-Desert-Teleporation-Tool](https://github.com/DameonK/Crimson-Desert-Teleporation-Tool)).
- **Da.Zombie** — original teleport structure and code-cave research that this tool builds on.
- **LeFruitxd** — upstream PR #4: the `[rbx+3C]`-anchored map-marker signature that v2.1.8 builds on.
- **efecnc** — upstream PR #2: research on the 2026-05 entity / health breakage and the idea of letting a missing hook degrade instead of failing.
- **PHTMGatt** — v2.1.8 fork: signatures for 1.0.0.3576, multi-signature scanner, height hotkeys.
- Community waypoint database powered by Google Sheets.
- Thanks to everyone who has contributed waypoints to the shared database.

---

## License

MIT — see [`LICENSE`](LICENSE).
