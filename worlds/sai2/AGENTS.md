# worlds/sai2 — Super Adventure Island II Archipelago world

See `docs/index.md` for full developer documentation.

## Environment

- Work from the Archipelago repo root (`../../..`).
- Use the project venv: `.\.venv\Scripts\python.exe` (the system Python 3.14 lacks dependencies).
- Base ROM `Super Adventure Island II (USA).sfc` must sit in the repo root to run ROM generation
  or the ROM tests (tests skip themselves when it is missing).

## Tests

```
.\.venv\Scripts\python.exe -m unittest discover -s worlds/sai2/test -t . -v
```

`test/test_rom.py` performs real fills and ROM generation in a temp directory; it can print
verbose `[SAI2]` output. `test/test_client.py` is offline (fake BizHawk memory).

Fill reliability (should report 0 failures solo):

```
.\.venv\Scripts\python.exe worlds\sai2\tools\fill_stress.py 500        # solo
.\.venv\Scripts\python.exe worlds\sai2\tools\fill_stress.py 200 1 2    # 2x SAI2 multiworld
```

Note: `generate_output` writes ROMs to `<cwd>/output/` regardless of `--outputpath`.

## Testing in game without a full playthrough

Load `tools/sai2_debug.lua` in BizHawk:

- `I` — give every item (the 35 real flags only; the gaps in `$044E`–`$047F` are other game
  flags and must NOT be written — doing so once crashed the game and triggered the real ending).
- `V` — write `$1E9F = 1`: the client reports the goal (tests the reporting path safely).
- `L` — dump `$D3` / `$10` / `$2254`.
- `NumPad1` — for ~10 s, replace `$2254` with `$0003` whenever the game displays an item:
  the next chest shows/awards 1000 Coins through the real game code (tests the "??? coins" fix).
- `R` — write a fake remote item to the mailbox (tests the v15 receive path in game).
- Do NOT force `$D3` or `$2254` continuously — it crashes the game.
- Do NOT write broad WRAM ranges; only the 35 item flags and the mailbox addresses are safe.

It also logs every change to `$D3` and `$10`.

## Key facts

- 68 checks: 51 standard chests (marker `$7B`), 14 event locations, 3 techniques (locked vanilla),
  plus the `Defeat Final Boss` event location.
- Check table `SAI2AP03` embedded at ROM `0x17B300` (v15; `SAI2AP02` = v14 ROMs, rejected).
- Event completion flags: `$1E80`–`$1E8D`; Poka Light Spell chest: `$1E90`; goal debug flag: `$1E9F`.
- Techniques are locked vanilla AND require the isle's normal-entrance stone (Down Jab→Aqua,
  Up Jab→Moon, Shove→Sun): zone-gate entrances are separate sections that can't reach them.
- Gate rules were re-verified against sai2_rando `tables/requirements.txt` in v14.2: moon gates
  need Moon+Aqua Stone (`moongate_down = puka&moonstone`), `Hiya to Boa` needs Sun+Light,
  `Star Zone to Hiya` needs Star+Sun+Light, and warps to Hiya/Puka need Magic Wand. Do not
  loosen these — a too-strict rule only costs variety, a too-loose one ships unbeatable seeds.
- Self-lock safety: `set_self_lock_rules` runs in `generate_basic` AFTER locked items are
  placed (order matters — earlier, locked items are invisible to the sweeps). The `pre_fill`
  trial also does a forward-sweep completability proof, catching mutual locks.
- Known player-verified extras not in the original requirements: `Sala Isle - Magic FE683`
  needs Shove.
- Since v14.1 the sai2_rando `chest_patch.txt` ("??? coins") is NOT applied — vanilla item `$0003`
  already displays and awards 1000 Coins correctly.
- Fill: Silver Sword locked vanilla; only 1st copy of Life Bottle/500/1000 Coins is progression;
  event locations filled in `pre_fill` with a verified trial fill (kept in solo). Don't
  reintroduce `local_early_items` or `PRIORITY` on events — they caused the FillErrors.
- `Item.__eq__` compares by name: remove items from `itempool` by identity, not `list.remove`.
- Victory = RA #37019: `$D3 = 6` seen, then `$D3 = 3` with `$10 = $B0` (50 frames ≈ 7 polls).

## Multiworld (v15)

- `Multiworld.py` adds the AP item: hooks at `$C20807` (receive tick), `$C05C13` (chest display
  index), `$C05C39` (held sprite), `$C05DEA` (message draw); data at `0x00FBA0` and
  `0x17B600`–`0x17F209`. `apply_multiworld_patch` verifies vanilla bytes at hook sites and that
  target areas are free — keep those checks strict.
- Receive mailbox: `$1D00` state (0 idle / 1 request / 2 showing), `$1D02` item (`$FFFF` = show
  only), `$1D10` 197-byte message, `$03D0` saved received counter. The client only writes the
  mailbox; the ROM gives items, so common rewards (Life Bottle/Magic/Coins) get applied for real.
- Remote chests get sink item `$1C10 + k` (message `YOU SENT / <item> / TO <player>`), remote
  events get message code `$40 + k` via `patch_event_check_flag`. Never write a cross-game item
  id to SAI2 item memory.
- `v14.2 - Fonctionnel/` is a frozen backup — never edit it.
