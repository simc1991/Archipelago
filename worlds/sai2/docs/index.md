# Super Adventure Island II — Archipelago World: Developer Documentation

This document covers the `worlds/sai2` package. It explains how the world is built,
how the ROM gets patched, and how the BizHawk client talks to the game.

- Game: *Super Adventure Island II* (SNES, USA, unheadered, HiROM, 1.5 MiB)
- Base ROM SHA‑1: `06776efd3cc3997513f90fbe2507939a1c61bb87`
- Base ROM path: `<Archipelago root>/Super Adventure Island II (USA).sfc`
- Based on: [abyssonym/sai2_rando](https://github.com/abyssonym/sai2_rando) (data tables and logic)

---

## Index

1. [File map](#1-file-map)
2. [Generation pipeline](#2-generation-pipeline)
3. [Items (`Items.py`)](#3-items-itemspy)
4. [Locations (`Locations.py`)](#4-locations-locationspy)
5. [Regions (`Regions.py`)](#5-regions-regionspy)
6. [Logic (`Rules.py`)](#6-logic-rulespy)
7. [ROM patching (`Rom.py` + `generate_output`)](#7-rom-patching)
8. [Embedded AP check table](#8-embedded-ap-check-table)
9. [BizHawk client (`client.py`)](#9-bizhawk-client-clientpy)
10. [Multiworld (v15): AP item, receive mailbox](#10-multiworld-v15)
11. [Memory map (WRAM / ROM)](#11-memory-map)
12. [Tools (`tools/`)](#12-tools)
13. [Testing](#13-testing)
14. [Known limitations / TODO](#14-known-limitations--todo)
15. [Changelog](#15-changelog)

---

## 1. File map

| File | Role |
|---|---|
| `__init__.py` | `SAI2World`: item pool, rules hook, victory event, ROM generation (`generate_output`), seed Lua detector. |
| `Items.py` | `item_table` (AP id, classification, ROM item id) and `item_pool` (68 vanilla items). |
| `Locations.py` | `location_table` (AP id, ROM address of the chest/event/technique structure). |
| `Regions.py` | Region list, location-to-region assignment, region connections. |
| `Rules.py` | Access rules. Ported from sai2_rando's `requirements.txt`. |
| `Rom.py` | Low-level ROM helpers: validation, chest/event patching, memory pools, constant tables. |
| `client.py` | `SuperAdventureIslandIIClient` (BizHawk): reads the check table, sends checks, queues received items. |
| `Multiworld.py` | v15 ROM patch: AP item hooks (65816 code), message encoder, receive mailbox constants. |
| `data/ap_logo.bin`, `data/ap_logo_palette.bin` | AP logo sprite (4bpp) + palette, built by `tools/make_ap_logo.py` from `data/icon.png`. |
| `tools/` | Standalone research and debug scripts (see [§12](#12-tools)). |
| `test/` | Unit tests (see [§13](#13-testing)). |
| `v14 - Fonctionnel mais 2 bug/` | Frozen backup of version 14. Do not edit. |
| `v14.2 - Fonctionnel/` | Frozen backup of version 14.2 (last solo-only version, with docs/tests/tools). Do not edit. |

## 2. Generation pipeline

These are the standard Archipelago steps, in the order they run:

1. **`create_regions`**: `Regions.create_regions` builds `Menu` plus 17 regions and their connections.
   `Defeat Final Boss` is an *event* location (address `None`).
2. **`create_items`**: adds `item_pool` to the multiworld, minus the 3 techniques
   (`Shove`, `Up Jab`, `Down Jab`) and the `Silver Sword` (`VANILLA_LOCKED_ITEMS`). That leaves
   **64 items**. Only the **first** copy of `Life Bottle`, `500 Coins` and `1000 Coins` is
   progression (logic only checks for one). Extra copies are useful/filler
   (`EXTRA_COPY_CLASSIFICATION`).
3. **`set_rules`**:
   - Calls `Rules.set_rules`.
   - Adds an item rule to the **14 event locations**: they may not hold this player's common
     rewards (`COMMON_REWARDS`: `Life Bottle`, `Magic`, `500/1000/2000/5000 Coins`), because event
     scripts can only award flag items.
4. **`generate_basic`**: locks the 3 techniques and the Silver Sword at their vanilla locations, and
   places the `Victory` event item on `Defeat Final Boss`. Completion condition: `has("Victory")`.
5. **`pre_fill`**: see [§2.1](#21-fill-strategy).
6. **Fill**: handled by Archipelago.
6. **`generate_output`**: patches the base ROM and writes these files to `<cwd>/output/`:
   - `AP_<seed>_P<player>_SAI2.sfc`: the patched ROM.
   - `AP_<seed>_P<player>_SAI2_CheckDetector.lua`: a read-only BizHawk script that logs checks.

### 2.1 Fill strategy

The early game is very narrow. With an empty inventory, only the Silver Sword chest is reachable.
After that, each new area adds only one to three free chests. AP's default random fill often used
those few chests for unimportant items, which caused `FillError` in 60% of solo seeds before v14.1.

The fixes:

1. **Silver Sword locked** at `Poka Isle - Silver Sword`. It was already forced there; locking it
   removes the impossible `local_early_items` rules (Silver Sword, Fire Sword).
2. **Fewer progression items**: extra copies of Life Bottle / 500 / 1000 Coins are demoted.
3. **`pre_fill` for event locations** replaces the old `PRIORITY` trick, which locked progression
   into every event slot without swaps:
   - Picks 14 random non-common items of this world, one per event location, and places them with
     `fill_restrictive`.
   - Runs a **trial fill** of this world's remaining progression into its own empty locations. This
     proves the event placement is not a dead end.
   - If either step fails, it undoes everything and retries (`EVENT_FILL_ATTEMPTS = 50`).
   - **Solo game**: the successful trial placement is kept, since every item is local anyway.
     **Multiworld**: the trial is undone and AP's main fill places the progression across all worlds.

Measured with `tools/fill_stress.py`:

| Configuration | Before v14.1 | v14.1 |
|---|---|---|
| Solo | 79/200 OK | 500/500 OK |
| 2× SAI2 multiworld (worst case) | — | 198/200 OK |

> Note: `generate_output` currently ignores its `output_directory` argument. It uses `Path.cwd()`
> for both the input ROM and the output folder.

## 3. Items (`Items.py`)

`SAI2ItemData(code, classification, rom_id)`

- AP item ids: `BASE_ID = 0x53414900` + offset.
- `rom_id` is the in-game item id. For flag items, it is also the **WRAM address of the ownership flag**.

| ROM id range | Meaning |
|---|---|
| `0x0000` | Life Bottle (health/heart container) |
| `0x0001` | Magic |
| `0x0002`–`0x0005` | 500 / 1000 / 2000 / 5000 Coins |
| `0x044E`–`0x0458` | Weapons (swords, dagger, fireballs, axe) |
| `0x0459`–`0x046A` | Tools / key items (shovel, wand, bells, ring, fan, flute) |
| `0x045B`–`0x0462` | Armors and shields |
| `0x046B`–`0x046F` | Stones (Light, Sun, Star, Aqua, Moon) |
| `0x0470`–`0x0474` | Spells (Light, Star, Sun, Aqua, Moon) |
| `0x047D`–`0x047F` | Techniques (Shove, Up Jab, Down Jab) |

`item_pool` lists the 68 vanilla rewards, with repeats for common rewards.

## 4. Locations (`Locations.py`)

`SAI2LocationData(code, rom_address)`, with `BASE_LOCATION_ID = 0x53414A00` + offset.

There are three kinds of location structure:

| Kind | Count | ROM structure at `rom_address` |
|---|---|---|
| Standard chest | 51 | `+0/+1` memory id (WRAM completion flag), `+2` marker `0x7B`, `+3/+4` item id |
| Event reward | 14 | `+0/+1` item id (WRAM flag pointer), followed by `0x7E` |
| Technique | 3 | `+0/+1` technique map code (3/4/5), signature `01 00 12 01 7E 1C` |

Total: **68 checks**, plus the `Defeat Final Boss` event.

## 5. Regions (`Regions.py`)

Regions: `Menu`, `Poka`, `Poka Isle`, `Boa`, `Boa Isle`, `Hiya`, `Hiya Isle`, `Puka`, `Puka Isle`,
`Puka Drained`, `Sala`, `Sala Isle`, `Star Zone`, `Overworld`, `Fuwa Isle`, `Final Boss`.

Main progression path:
`Menu → Poka → (Light Stone) Boa → (Sun Stone) Hiya → (Star Stone) Star Zone → (Moon Stone) Puka/Sala → (5 spells + durability) Fuwa Isle → (Power Sword, Shovel, Sky Bell, boss) Final Boss`.

Warp entrances (Boa Isle, Sala Isle, Fuwa Isle) and gate entrances (Aqua Gate, Sun Gate) are also defined.
Their rules live in `Rules.py`.

## 6. Logic (`Rules.py`)

The rules are a port of sai2_rando's `requirements.txt`. Each rule's comment shows the original
expression (for example `# lightstone_10305  poka_sword & boss`).

Helper predicates:

| Helper | Meaning |
|---|---|
| `has_sword` / `has_weapon` / `has_armor` | Owns any item of the group |
| `has_durability` | armor **and** Life Bottle |
| `can_defeat_boss` | Life Bottle **and** weapon |
| `has_poka_sword_access` | Silver Sword, **or** Shove + Shovel (Fuwa→Poka warp) |
| `sun_blocks_off` / `moon_blocks_on` | Boa Isle / Sala Isle reachable (switch pressed) |
| `star_switch` | Hiya Isle reachable + Fire Sword + Shove (deliberately conservative) |
| `aqua_switch` | Puka Drained reachable, or Sala Isle + Shove + Shovel |
| `can_up_jab` | Up Jab + sword + `1000 Coins` (the technique costs money) |
| `can_down_jab` | Down Jab + sword + (`500 Coins` or `1000 Coins`) |
| `has_ax_capability` | Axe, or `can_up_jab` |

Because some jabs need coins, `500 Coins` and `1000 Coins` are classified as **progression**.

Since the techniques are locked at their vanilla spots, each technique check additionally
requires the stone for its isle's **normal** entrance (the zone-gate shortcuts land in a
separate section that cannot reach it): Down Jab → Aqua Stone, Up Jab → Moon Stone,
Shove → Sun Stone.

## 7. ROM patching

`SAI2World.generate_output` runs these steps:

1. `load_rom`: checks the size (`0x180000`) and the SHA‑1.
2. *(v14.1)* sai2_rando's `chest_patch.txt` is **no longer applied** (see [§15](#15-changelog)).
   *(v15)* `apply_multiworld_patch` installs the AP item (see [§10](#10-multiworld-v15)).
3. `build_unused_memory_pool`: collects the memory ids of vanilla standard chests whose memory id is
   not equal to their item id. Ids ≥ `0x051F` and `0x0470` are excluded. Common rewards in chests
   draw from this pool.
4. For every location that has a ROM address:
   - **Remote item** (another player's): gets the next "sent message" index `k`
     (`YOU SENT / <item> / TO <player>`).
     - Chest: item id becomes `sink_item(k) = 0x1C10 + k`. The vanilla give routine writes `1` to
       that unused WRAM byte, so nothing is given locally. The vanilla memory id is kept, so the
       check still fires.
     - Event: `patch_event_check_flag` redirects the reward write, and the message code becomes
       `0x40 + k`.
   - **Technique**: must contain its vanilla technique. The memory id is the technique's flag.
   - **Event**:
     - `patch_event_location` writes the new item id.
     - `patch_event_memory` syncs `EventMemory`/`BossMemory`.
     - `patch_event_check_flag` redirects the script's reward write and its guards to a
       location-only flag `0x1E80 + index`.
     - `patch_event_message` sets the message code (`item_id - 0x044A`).
     - The local reward is then granted by the client, not by the script.
   - **Standard chest**: `patch_standard_location` writes the item id. The chest memory id is reset to
     the **original location memory id**, so completion tracks the physical chest.
     - `Poka Isle - Light Spell` uses `LIGHT_SPELL_CHEST_CHECK_FLAG = 0x1E90`. Its vanilla memory
       `0x0470` is also the Light Spell ownership flag.
     - The Star Spell duplicate check pointer (`0x19B58`) is kept in sync.
5. Builds the AP check table and writes it at `0x17B300` (see [§8](#8-embedded-ap-check-table)).
6. Saves the ROM and the seed-specific Lua check detector.

## 8. Embedded AP check table

Written at ROM offset `0x17B300` (CPU `$D7:B300`, unused `0xFF` space):

```
8 bytes   signature  b"SAI2AP03"   (v15; v14 ROMs use SAI2AP02 and are rejected)
2 bytes   entry count (LE) — must be 68
N × 8 bytes:
    2 bytes  WRAM memory/check id (LE)
    4 bytes  Archipelago location id (LE)
    2 bytes  local event reward ROM id, or 0xFFFF
```

The client uses the signature to recognize the ROM.

## 9. BizHawk client (`client.py`)

`SuperAdventureIslandIIClient(BizHawkClient)`, `system = "SNES"`.

- **`validate_rom`**: reads the table header from the `ROM` domain. If the signature and count match,
  it loads `check_map` (memory id → location id) and `event_rewards`.
  Sets `items_handling = 0b101`: remote items plus starting inventory. Local items are given by the ROM.
- **`game_watcher`**, every 0.125 s:
  1. **Receive items** *(v15)*: reads the mailbox state and the saved received counter. When the
     mailbox is idle and `counter < len(items_received)`, writes item `items_received[counter]`
     with its message into the mailbox (see [§10.2](#102-receiving-items)). The ROM gives the item;
     the client never writes inventory flags itself.
  2. **Send checks**: reads 1 byte per memory id in `check_map`. Any non‑zero value counts as checked.
  3. **Local event rewards**: once an event location is checked, writes `1` to the reward's WRAM flag.
  4. **Goal** *(v14.1)*: implements RetroAchievements #37019 *Save the Girl!* — see below.

### Victory detection

The client mirrors achievement #37019 `Save the Girl!` (Defeat the final boss and save Tina and
the King!):

- `$00D3 == 0x06` must be observed at least once (final boss sequence).
- `$00D3 == 0x01` resets the state (title screen).
- Once both are satisfied, `$00D3 == 0x03` with `$0010 == 0xB0` for 50 frames ends the game.

RA counts hit frames; the client polls about every 0.125 s, so it approximates 50 frames with
`ENDING_POLLS_REQUIRED = 7` polls. When the condition holds, it sends
`StatusUpdate: CLIENT_GOAL` and sets `ctx.finished_game`.

A debug hook exists for testing the reporting path without playing: writing `1` to WRAM
`$1E9F` (`tools/sai2_debug.lua`, `V` key) also triggers the goal report.

## 10. Multiworld (v15)

v15 adds an **Archipelago item** to the game, implemented in `Multiworld.py`:

- **Received** item (from any world): Higgins raises the AP logo in his hand, the item
  jingle plays, and the top box shows `YOU'VE OBTAINED` / `<item>` / `FROM <player>`.
- **Sent** item (a SAI2 chest/event holding another player's item): the same animation shows
  `YOU SENT` / `<item>` / `TO <player>`, and nothing is given locally.
- **Common rewards** received (Life Bottle, Magic, 500–5000 Coins) are applied in game, just like
  a chest would.

### 10.1 How a vanilla chest works (reverse engineering)

Objects run a bytecode VM. The interpreter is at `$C03E71`. The script pointer is
`$153C,Y`/`$157C,X`, and the opcode table is at `$C03D3E` (153 entries). Opcodes used here:

| Op | Meaning |
|---|---|
| `00` | end of script |
| `01` | yield one frame |
| `04 aaaaaa` / `05 aaaaaa` | call native routine (`04` also yields) |
| `06 aaaaaa` / `0F` / `10` | jump / jump if (not) zero |
| `28 vv nn aaaa bb` | write `vv` to `bb:aaaa` (events use it to set `$2254`) |
| `40 nn` | play sound `nn` (`JSL $C02F30`, skipped if `$1B63 ≠ 0`) |
| `7A mmmm` / `7B iiii` | set the object's memory flag `$0C39,Y` / item `$0C79,Y` |

The chest script at `$C05A10` opens like this once the player presses Up:

1. `$C05AE4` gives the item: item ≥ 6 means write `1` to WRAM `[item]`; items 0–5 go through a
   jump table (Life Bottle `$011E += 8`; Magic `$0120++`; coins add BCD digits to `$0435` via
   `JSL $C02355`). It then sets the chest flag.
2. `$C05C13` sets the display index `$2254` (`item − 0x044A`, or table `$C05C31` for items 0–5).
3. `$C05DD8` draws the message: tilemap from table `$C5:0000[$2254]` to VRAM `$1D00`, via
   `JSL $C011B9`. Format: header `20 00 03 00 00`, then 3 rows × 32 tiles (2 bytes each).
4. `$C05ACB` sets `$0104 |= 8`. The player state code (`$C22D4F`) sets `$0104 |= $8000`, loads the
   held sprite via `$C05C37` (table `$C05C80[$2254]`: gfx source, palette, held pose) and freezes
   objects. When a button is pressed, `$C22D46` clears `$8008`.
5. `40 54` plays the jingle, then `$C05E15` closes the message.

Font (tile, palette `$2C`): `A–Z` = `$50–$69`, `0–9` = `$A0–$A9`, `'` `$6A`, `&` `$6B`, `/` `$6C`,
`:` `$6D`, `-` `$8B`, `!` `$8C`, `.` `$8D`, `,` `$8E`, `?` `$8F`; space = `$90` palette `$28`.

### 10.2 Receiving items

The client and the ROM share a WRAM mailbox:

| WRAM | Meaning |
|---|---|
| `$1D00` | state: `0` idle, `1` request (client), `2` showing (ROM) |
| `$1D02` | item: WRAM flag address, common reward `0`–`5`, or `$FFFF` (show only) |
| `$1D10` | 197-byte message (`received_message`) |
| `$03D0` | received counter. It is in the WRAM block copied to SRAM, so it follows the save file. |

The hook at `$C20807` runs in the player's per-frame update, which is frozen while an item is
held. On every frame:

- **State 1**: once every chest-open condition is true, it gives the item, increments the counter,
  sets `$2254 = $2B`, draws the message, sets `$0104 |= 8` and plays sound `$54`. Then state = 2.
  The conditions are: `$D3 = 2`, `$0104 & $F20F = 0`, `$0102 & $3F7F = 0` with bit `$4000`, no
  message showing, `$1B73 = 0` and `$08D9,player = 0`.
- **State 2**: once `$0104 & $8008 = 0` (the player dismissed the item), it closes the message.
  Then state = 0.

Because the counter is saved, reloading an older save replays exactly the items that save is
missing, and items already applied are never given twice.

### 10.3 Hooks and ROM layout

| Site | Replaced | New behavior |
|---|---|---|
| `$C20807` | `REP #$20 / LDA $0104` | `JSL tick`: receive state machine |
| `$C05C13` | chest display index | `JML set_index`: items `$1C10+k` → `$2254 = $40+k` |
| `$C05C39` | held-sprite index | `JSL gfx_index`: `$2254 ≥ $2B` → AP entry at `$C0FBA0` |
| `$C05DEA` | message draw | `JSL draw_msg`: `$2B` → mailbox, `≥ $40` → sent message `k` |

| ROM offset | Content |
|---|---|
| `0x00FBA0` | AP held-sprite entry (logo gfx, palette, pose `$11` = 16×16 in the hand) |
| `0x17B600` | hook code (~550 bytes) |
| `0x17BA00` | AP logo sprite block (1 KB); `0x17BE00` palette |
| `0x17BE40` | pointers to sent messages; `0x17C000` 65 sent messages × 197 bytes |

`apply_multiworld_patch` checks that every hook site still holds the vanilla bytes, and that every
target area is free (`0xFF`).

## 11. Memory map

### WRAM

| Address | Meaning |
|---|---|
| `$0102` / `$0104` | Player state / action flags (`$0104` bit 3 = item get, bit 15 = holding item) |
| `$011A`/`$011E`, `$011C`/`$0120` | Health / max health, magic / max magic |
| `$03D0` | v15 received-items counter (saved to SRAM with the game) |
| `$0435`–`$043A` | Money, BCD digits (the last digit counts hundreds) |
| `$0C39,Y` / `$0C79,Y` | Script object memory flag / item (32 slots) |
| `$1C10`–`$1C50` | v15 sinks for remote chests (`0x1C10 + k`) |
| `$1D00`–`$1DD4` | v15 receive mailbox |
| `$225E` | Item message showing |
| `$044E`–`$047F` | Item ownership flags (`1` = owned). The address is the item's ROM id. |
| `$0490`–`$053F` | Standard chest completion flags (vanilla memory ids) |
| `$1E80`–`$1E8D` | AP event-location completion flags (`EVENT_CHECK_FLAGS`, 14 entries) |
| `$1E90` | AP Poka Isle Light Spell chest completion flag |
| `$2254` | Display index of the item being shown (`item − 0x044A`; `$2B` = AP received, `$40+k` = AP sent) |
| `$00D3` | Game mode: `1` = title, `3` = ending, `6` = final boss (RA #37019) |
| `$0010` | Ending sequence marker: `0xB0` for 50+ frames at the ending |

### ROM

| Offset | Meaning |
|---|---|
| `0x005DEA` | Item message routine (`LDA $2254 / ASL`). Hooked by v15 (`draw_msg`). |
| `0x00FBA0` | v15 AP held-sprite entry |
| `0x050000` | Pointer table to the item message tilemaps (bank `$C5`, `0xC5` bytes each) |
| `0x050306` | Tilemap text `1000 COINS` (item `$0003`) |
| `0x17B200` | sai2_rando "??? coins" routine (unused since v14.1) |
| `0x17B300` | AP check table |
| `0x17B600`–`0x17F209` | v15 hook code, AP logo, sent messages (see [§10.3](#103-hooks-and-rom-layout)) |

## 12. Tools

| Script | Purpose |
|---|---|
| `tools/analyze_rom_locations.py` | Classifies every `Locations.py` address (chest/event/technique) in a ROM. |
| `tools/generate_standard_chest_table.py` | Prints the standard chest memory table from the vanilla ROM. |
| `tools/sai2_check_monitor.lua` | BizHawk read-only monitor for the 51 vanilla chest flags. |
| `tools/sai2_debug.lua` | BizHawk debug helper for testing without a full playthrough (see [§13](#13-testing)). |
| `tools/fill_stress.py` | Generates many seeds and reports fill failures: `fill_stress.py [count] [first_seed] [players]`. |
| `tools/build_test_rom.py`, `tools/patch_seed_rom.py` | Early prototypes. `patch_seed_rom.py` uses an old API signature. |
| `tools/inspect_sai2_classes.py` | Dumps sai2_rando class sources. |
| `tools/disasm65816.py` | 65816 disassembler used to reverse engineer the item routines (see [§10.1](#101-how-a-vanilla-chest-works-reverse-engineering)). |
| `tools/make_ap_logo.py` | Rebuilds `data/ap_logo*.bin` from `data/icon.png`. |

## 13. Testing

Run the tests from the Archipelago root with the project venv:

```
.\.venv\Scripts\python.exe -m unittest discover -s worlds/sai2/test -t . -v
```

- `test/test_rom.py`: generates a seed, patches the ROM, and checks that:
  - the `1000 COINS` message is vanilla and the "??? coins" hook is not installed;
  - every local standard chest contains the item that AP placed there;
  - remote locations get a sink item / message code, and `SAI2AP03` is written.
- `test/test_client.py`: drives the client's goal detection and the receive mailbox with a fake
  BizHawk memory (queueing, busy wait, saved counter, unsupported items).
- `test/test_fill.py`: checks that 100 solo seeds all fill and are fully accessible, that events
  hold no common rewards, and that the repeatable rewards have exactly one progression copy.
- `test/test_multiworld.py`: message encoders, remote chest/event patching, and a real
  two-player SAI2 × ChecksFinder generation.
- `tools/fill_stress.py`: run at least 50 seeds after changing logic or fill rules.

To test in game without playing the whole game, use `tools/sai2_debug.lua` in BizHawk:

- `I`: give every item (the 35 real item flags only — never write the gaps in
  `$044E`–`$047F`, they are other game flags), to rush the final boss.
- `V`: write `$1E9F = 1` so the client reports the goal — tests the reporting path without
  corrupting the game.
- `NumPad1`: for ~10 s, replace `$2254` with `$0003` whenever the game displays an item — the
  next chest shows `1000 COINS` through the real code path, which verifies the "??? coins" fix.
- `R`: write a fake remote item (`2000 COINS` from `Player2`) to the mailbox — tests the v15
  receive path end to end.
- `L`: dump `$D3` / `$10` / `$2254` / mailbox state. The script also logs every change.

## 14. Known limitations / TODO

- Event locations always hold this world's own items (never remote items), because of the event
  `pre_fill`.
- Remote event check flags (`$1E80+`) are not saved to SRAM: a remote event re-triggers its check
  after reload (AP deduplicates, so it only shows the sent message again). Remote chests are fine —
  they keep the vanilla memory id, which is saved.
- `generate_output` ignores `output_directory`, and reads the base ROM from `cwd`.
- Two SAI2 slots in the same multiworld still fail about 1% of the time. Generate again with another
  seed if that happens.
- No options and no WebWorld docs yet.

### v15.1

- **SNI client** (`SAI2SNIClient(SNIClient)`): same protocol as the BizHawk client, but over SNI —
  which would add snes9x-nwa / RetroArch / **real hardware (FXPakPro/SD2SNES)** support.
  Nothing game-side blocks it; it is a client port:
  - ROM validation reads `SAI2AP03` at SNES address `$D7:B300` (file `0x17B300`) instead of the
    `ROM` domain.
  - WRAM reads/writes go through `sni.read/write(0x7E0000 + addr)` — mailbox, check flags,
    `RECEIVED_COUNT`, victory bytes all work on hardware too.
  - The mailbox/counter protocol is unchanged; the game-side hooks are emulator-agnostic.

## 15. Changelog

### v15.0
- **Multiworld items.** Chests and events holding another player's item show `YOU SENT / <item> /
  TO <player>`; items received from the network show `YOU'VE OBTAINED / <item> / FROM <player>`
  with the AP logo in Higgins's hands and the item jingle. Received Life Bottle / Magic /
  500–5000 Coins are applied in game; anything else is displayed without giving an invalid item.
- **Receive mailbox.** Client→ROM mailbox at `$1D00` (`Multiworld.py`), consumed by a hook in the
  player's frame update. A saved counter (`$03D0`) replays exactly the items an older save is
  missing and never gives an item twice.
- **AP item.** ROM hooks at `$C20807`, `$C05C13`, `$C05C39`, `$C05DEA`; new data at `0x00FBA0`
  and `0x17B600`–`0x17F209` (see [§10](#10-multiworld-v15)). Remote chests get a sink item
  (`$1C10+k`) instead of their vanilla reward. AP check table signature is now `SAI2AP03`;
  `generate_output` refuses v14 tables.
- v14.2 code is frozen in `v14.2 - Fonctionnel/`.

### v14.2
- **Fix: missing entrance requirements** (found on a real seed where the Aqua Stone was placed
  inside Sala, which the wrong logic allowed to reach with only the Moon Stone — unbeatable).
  Checked every entrance against sai2_rando's `requirements.txt` and fixed:
  - **Moon gate routes** (Star Zone↔Puka, Star Zone↔Sala, Puka↔Sala): `moongate_down` is
    `puka & moonstone`, and Puka itself needs the Aqua Stone → these routes now require
    **Moon Stone + Aqua Stone**.
  - **`Hiya to Boa`**: `sungate_down` is `boa & sunstone` → now requires **Sun + Light Stone**.
  - **`Star Zone to Hiya`**: `stargate_down` is `hiya & starstone` → now requires
    **Star + Sun + Light Stone**.
  - **Warps to Hiya/Puka** (`Boa Isle→Hiya`, `Sala Isle→Hiya`, `Sala Isle→Puka`,
    `Fuwa→Puka`): `hiya`/`puka` require `*_warp & magicwand` → added **Magic Wand**.
  - **`has_poka_sword_access`**: the `fuwa_poka_warp` alternative needs `fuwa_isle` reachable —
    added `can_reach("Fuwa Isle")` (the 8 `poka_sword` checks in Poka Isle were wrongly granted
    with just Shove + Shovel).
  - **`Sala Isle - Magic FE683`**: added **Shove** — the chest sits behind a pushable block in
    game (player-verified; missing from the original `requirements.txt`).
- **Fix: self-locking placements.** AP's reverse fill evaluates locations in a state that owns
  every unplaced item, so it could put an item behind a check that needs it (a seed placed the
  Sun Stone on `Sala Isle - Magic FE683`, which needs Shove → Sun Stone). Two guards:
  - `set_self_lock_rules` (called at the end of `generate_basic`, after locked items exist):
    for each progression item, every location unreachable without it gets an `item_rule`
    forbidding it. Only the **progression** copy is restricted (filler/useful copies of
    Life Bottle / Coins can still go anywhere).
  - The `pre_fill` trial fill additionally proves completability with a **forward sweep**
    (`sweep_for_advancements` + `has_beaten_game` + every location reachable), which also
    catches mutual locks (item A behind B's check, B behind A's check).
- **Fix: technique logic.** The zone-gate entrances lead to a separate section of each isle
  that cannot reach the technique spot. The three technique checks now also require the isle's
  normal-entrance stone: Down Jab → Aqua Stone, Up Jab → Moon Stone, Shove → Sun Stone.
- **Debug script fixes.** `tools/sai2_debug.lua` no longer crashes the game: `I` only writes
  the 35 real item flags (gaps in `$044E`–`$047F` are other game flags), `V` now reports the
  goal through a safe debug flag (`$1E9F`) instead of forcing `$D3`, and `NumPad1` only
  replaces `$2254` while the game is displaying an item.

### v14.1
- **Fix: "??? coins" message.** `apply_chest_engine_patch` (sai2_rando `chest_patch.txt`) replaced the
  `1000 COINS` tilemap with `??? COINS` and hooked `$005DEA` to add a random digit bonus.
  This came from sai2_rando's "mystery coins for empty chests" feature, which AP does not use.
  The patch is no longer applied, so the vanilla message and amount are used.
- **Fix: victory.** The client now sends `CLIENT_GOAL` when the ending condition is reached.
- **Fix: `FillError`.** Silver Sword locked, the Fire Sword early rule removed, extra repeatable
  rewards demoted, and `PRIORITY` events replaced by a verified event `pre_fill`
  (see [§2.1](#21-fill-strategy)). Solo seeds went from 40% OK to 100% OK.
- Added unit tests, `tools/fill_stress.py`, and a BizHawk debug script.

### v14
- 68 checks working in BizHawk multiworld. Two known bugs, fixed in v14.1.
