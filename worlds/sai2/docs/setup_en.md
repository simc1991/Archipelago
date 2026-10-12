# Super Adventure Island II — Setup & Multiworld Guide

How to install the `sai2.apworld`, generate a multiworld seed, host it on
archipelago.gg, and connect with BizHawk or SNI.

## Requirements

| File / software | Where to get it |
|---|---|
| `sai2.apworld` | GitHub Releases on this repository (or build it yourself with the "Build APWorlds" launcher component) |
| `Super Adventure Island II (USA).sfc` | Your own unheadered USA ROM dump (HiROM, 1.5 MiB). **Not** included — the generator patches it locally |
| An Archipelago install | `archipelago.gg` → releases (0.6.x) |
| For BizHawk play | BizHawk (BSNES core) + Archipelago's `connector_bizhawk_generic.lua` |
| For SNI play (v15.1) | SNI + its `Connector.lua` (BizHawk/snes9x-nwa/RetroArch) or an FXPakPro/SD2SNES |

## Who needs what

- **Whoever generates the seed**: the `.apworld` **and** the base ROM.
- **The SAI2 player(s)**: the `.apworld` (it carries `client.py`) + the patched `.sfc`
  produced by generation.
- **Players of other games**: nothing SAI2-related — a standard Archipelago install.

## 1. Install the world

Launcher → **Install APWorld** → select `sai2.apworld`.

Alternatively, copy `sai2.apworld` into the `custom_worlds/` folder of the
Archipelago installation. The world registers as *Super Adventure Island II*.

## 2. Prepare the player YAML files

Put one YAML per player in the `Players/` folder next to the Archipelago
generate tool (same folder for source and release installs).

`Simon.yaml`:

```yaml
description: SAI2 player
name: Simon
game: Super Adventure Island II
Super Adventure Island II: {}
```

`Friend.yaml` (example: Super Metroid):

```yaml
description: SM player
name: Friend
game: Super Metroid
Super Metroid: {}
```

SAI2 currently has no options; an empty `{}` block is correct.
`{}` is also valid for the other game if its defaults are fine.

## 3. Place the base ROM

The generator patches your own ROM at generation time. Put
`Super Adventure Island II (USA).sfc` in the directory you run generation
from (the Archipelago folder for a release install, the repo root for source).

## 4. Generate

Run **Archipelago Generate** (`ArchipelagoGenerate.exe`, or `Generate.py`
from source).

Results in `output/`:

- `AP_<seed>.zip` — the multiworld archive (contains the patch files of the
  *other* games, e.g. `.apsm`, and the server template)
- `AP_<seed>_P1_SAI2.sfc` — the patched SAI2 ROM for the SAI2 player(s)

## 5. Host on archipelago.gg

1. Go to `https://archipelago.gg/uploads`
2. Upload `AP_<seed>.zip`
3. The page creates a room and shows an address like `archipelago.gg:38281`

Alternative: host it yourself with `MultiServer.py` on the generated zip.

## 6. Connect and play

### SAI2 player — BizHawk

1. Open `AP_<seed>_P1_SAI2.sfc` in BizHawk (BSNES core)
2. Tools → Lua Console → `data/lua/connector_bizhawk_generic.lua`
3. Run **BizHawk Client**, `/connect archipelago.gg:38281`, enter the slot name

### SAI2 player — SNI (v15.1)

1. Start SNI, load the ROM in your device (BizHawk with **SNI's**
   `Connector.lua`, snes9x-nwa, RetroArch, or SD2SNES/FXPakPro)
2. Run **SNI Client**, `/snes`, then `/connect archipelago.gg:38281`

### Other players

They use their own patch file and client — e.g. Super Metroid:
`.apsm` + SNI + SNI Client.

## Troubleshooting

- **"ROM does not match" / client stays silent**: the ROM loaded must be the
  one produced by generation, which embeds the `SAI2AP03` check table.
  Vanilla and v14.x ROMs are rejected.
- **Generate fails to find the ROM**: the base `.sfc` must be in the working
  directory of the generate tool, exactly named
  `Super Adventure Island II (USA).sfc`.
- **No items arrive in game**: the SAI2 client must be connected *and*
  attached to the game. Watch the `[SAI2]` lines in the client log:
  `ITEM QUEUED`, `CHECK SENT`, `VICTORY`.
- **New generation?** Re-patch and redistribute the `.sfc`; each seed's ROM
  is unique.
