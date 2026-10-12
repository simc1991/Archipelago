"""SAI2 v15 multiworld ROM patch.

Adds an "Archipelago item" to the game:

* Receiving: the BizHawk client fills a WRAM mailbox (item + message). A hook
  in the player's per-frame update waits until the player could open a chest,
  gives the item, plays the item jingle, raises the AP logo over Higgins and
  shows "YOU'VE OBTAINED / <item> / FROM <player>".
* Sending: chests/events holding another player's item give nothing locally
  and show the AP logo with "YOU SENT / <item> / TO <player>".

Reverse-engineering notes (vanilla addresses) are in docs/index.md, section
"Multiworld (v15)".
"""
from __future__ import annotations

import pkgutil

# ---------------------------------------------------------------------------
# Memory map
# ---------------------------------------------------------------------------

# WRAM mailbox (bank $7E, unused by the game; cleared at power-on).
MAILBOX_STATE = 0x1D00      # u16: 0 idle, 1 request (client), 2 showing (ROM)
MAILBOX_ITEM = 0x1D02       # u16: WRAM flag address, common reward 0-5, or $FFFF
MAILBOX_MESSAGE = 0x1D10    # 197 bytes: message header + 3 rows of 32 tiles
# u16 count of received items already applied. Lives in the WRAM block the
# game copies to SRAM, so it follows the save file like the inventory does.
RECEIVED_COUNT = 0x03D0

# Remote chests carry SINK_BASE + k as their "item": the vanilla give routine
# writes 1 to that (unused) WRAM byte, and the index hook maps it to message k.
SINK_BASE = 0x1C10
MAX_SENT_MESSAGES = 65

# Display indices ($2254). Vanilla uses $00-$2A.
DISPLAY_RECEIVED = 0x2B     # message from the WRAM mailbox
DISPLAY_SENT_BASE = 0x40    # + k: precomputed "YOU SENT" message k

ITEM_NONE = 0xFFFF

# ---------------------------------------------------------------------------
# ROM layout (file offsets; HiROM bank $D7 = file $170000)
# ---------------------------------------------------------------------------

CODE_OFFSET = 0x17B600          # hook routines (<= 1 KB)
LOGO_OFFSET = 0x17BA00          # 1 KB sprite block
LOGO_PALETTE_OFFSET = 0x17BE00  # 32 bytes
SENT_TABLE_OFFSET = 0x17BE40    # u16 pointers (bank $D7) to each sent message
SENT_MESSAGES_OFFSET = 0x17C000  # 65 x 197 bytes
GFX_ENTRY_OFFSET = 0x00FBA0     # held-item entry, must be in bank $C0

MESSAGE_SIZE = 197

# Vanilla routines / hook sites (SNES addresses)
VANILLA_HOOKS = {
    # player per-frame update: REP #$20 / LDA $0104
    0xC20807: bytes.fromhex("C220AD0401"),
    # chest "set display index" routine
    0xC05C13: bytes.fromhex("C220B9790CC90600"),
    # held-item graphics: LDA $2254 / ASL x3 / TAX
    0xC05C39: bytes.fromhex("AD54220A0A0AAA"),
    # message draw: LDA $2254 ... JSL $C011B9 / PLB
    0xC05DEA: bytes.fromhex("AD54220AAABF0000C5AAE2208BA9C548AB22B911C0AB"),
}

DRAW_TILEMAP = 0xC011B9
CLOSE_MESSAGE = 0xC05E15
DRAW_MESSAGE = 0xC05DD8
PLAY_SOUND = 0xC02F30
ADD_MONEY = 0xC02355
COMMON_DISPLAY_TABLE = 0xC05C31
HELD_GFX_TABLE = 0xC05C80
ITEM_JINGLE = 0x54
HELD_POSE = 0x11  # 16x16 held item (cells 0-3), the generic vanilla item pose
COIN_AMOUNT_TABLES = {2: 0x5B72, 3: 0x5BA5, 4: 0x5BD8, 5: 0x5C0B}  # bank $C0


def file_to_snes(offset: int) -> int:
    return 0xC00000 + offset


def snes_to_file(address: int) -> int:
    return address - 0xC00000


# ---------------------------------------------------------------------------
# Message text
# ---------------------------------------------------------------------------

_FONT: dict[str, int] = {"'": 0x6A, "&": 0x6B, "/": 0x6C, ":": 0x6D, "-": 0x8B, "!": 0x8C, ".": 0x8D,
                         ",": 0x8E, "?": 0x8F, "_": 0x8B, "+": 0x6B}
_FONT.update({chr(ord("A") + i): 0x50 + i for i in range(26)})
_FONT.update({chr(ord("0") + i): 0xA0 + i for i in range(10)})
_SPACE = bytes([0x90, 0x28])
_HEADER = bytes([0x20, 0x00, 0x03, 0x00, 0x00])


def message_row(text: str) -> bytes:
    """32 tiles, centered. Unknown characters become spaces."""
    text = " ".join(text.upper().split())[:32]
    pad = (32 - len(text)) // 2
    row = bytearray(_SPACE * pad)
    for ch in text:
        tile = _FONT.get(ch)
        row += bytes([tile, 0x2C]) if tile is not None else _SPACE
    row += _SPACE * (32 - pad - len(text))
    return bytes(row)


def encode_message(line0: str, line1: str, line2: str) -> bytes:
    data = _HEADER + message_row(line0) + message_row(line1) + message_row(line2)
    assert len(data) == MESSAGE_SIZE
    return data


def received_message(item_name: str, player_name: str) -> bytes:
    return encode_message("YOU'VE OBTAINED", item_name, f"FROM {player_name}")


def sent_message(item_name: str, player_name: str) -> bytes:
    return encode_message("YOU SENT", item_name, f"TO {player_name}")


# ---------------------------------------------------------------------------
# Tiny 65816 assembler (only what the hooks need)
# ---------------------------------------------------------------------------

class Asm:
    def __init__(self, origin: int):
        self.origin = origin
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str, str]] = []

    @property
    def pc(self) -> int:
        return self.origin + len(self.code)

    def label(self, name: str) -> None:
        self.labels[name] = self.pc

    def emit(self, *values: int) -> None:
        self.code += bytes(values)

    def u16(self, op: int, value: int) -> None:
        self.emit(op, value & 0xFF, (value >> 8) & 0xFF)

    def u24(self, op: int, value: int) -> None:
        self.emit(op, value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF)

    def branch(self, op: int, target: str) -> None:
        self.emit(op, 0)
        self.fixups.append((len(self.code) - 1, target, "rel8"))

    def ref16(self, op: int, target: str) -> None:
        self.emit(op, 0, 0)
        self.fixups.append((len(self.code) - 2, target, "abs16"))

    def far(self, op: int, target: str) -> None:
        """Conditional branch with 16-bit reach: inverted branch over a BRL."""
        self.emit(op ^ 0x20, 3)   # BEQ<->BNE, BCS<->BCC: skip the BRL
        self.emit(0x82, 0, 0)
        self.fixups.append((len(self.code) - 2, target, "rel16"))

    def brl(self, target: str) -> None:
        self.emit(0x82, 0, 0)
        self.fixups.append((len(self.code) - 2, target, "rel16"))

    def word(self, target: str) -> None:
        self.code += b"\x00\x00"
        self.fixups.append((len(self.code) - 2, target, "abs16"))

    # mnemonics -----------------------------------------------------------
    def rep(self, v): self.emit(0xC2, v)
    def sep(self, v): self.emit(0xE2, v)
    def lda_imm16(self, v): self.u16(0xA9, v)
    def lda_imm8(self, v): self.emit(0xA9, v)
    def ldx_imm16(self, v): self.u16(0xA2, v)
    def ldy_imm16(self, v): self.u16(0xA0, v)
    def lda_abs(self, a): self.u16(0xAD, a)
    def sta_abs(self, a): self.u16(0x8D, a)
    def lda_long(self, a): self.u24(0xAF, a)
    def sta_long(self, a): self.u24(0x8F, a)
    def lda_longx(self, a): self.u24(0xBF, a)
    def sta_longx(self, a): self.u24(0x9F, a)
    def lda_absy(self, a): self.u16(0xB9, a)
    def cmp_imm16(self, v): self.u16(0xC9, v)
    def and_imm16(self, v): self.u16(0x29, v)
    def ora_imm16(self, v): self.u16(0x09, v)
    def adc_imm16(self, v): self.u16(0x69, v)
    def sbc_imm16(self, v): self.u16(0xE9, v)
    def bit_imm16(self, v): self.u16(0x89, v)
    def sta_dp(self, d): self.emit(0x85, d)
    def jsl(self, a): self.u24(0x22, a)
    def jml(self, a): self.u24(0x5C, a)
    def jsr(self, label): self.ref16(0x20, label)
    def jmp_absx(self, label): self.ref16(0x7C, label)
    def beq(self, t): self.branch(0xF0, t)
    def bne(self, t): self.branch(0xD0, t)
    def bcs(self, t): self.branch(0xB0, t)
    def bcc(self, t): self.branch(0x90, t)
    def bra(self, t): self.branch(0x80, t)
    def rtl(self): self.emit(0x6B)
    def rts(self): self.emit(0x60)
    def php(self): self.emit(0x08)
    def plp(self): self.emit(0x28)
    def pha(self): self.emit(0x48)
    def phb(self): self.emit(0x8B)
    def plb(self): self.emit(0xAB)
    def phx(self): self.emit(0xDA)
    def plx(self): self.emit(0xFA)
    def phy(self): self.emit(0x5A)
    def ply(self): self.emit(0x7A)
    def tax(self): self.emit(0xAA)
    def asl(self): self.emit(0x0A)
    def xba(self): self.emit(0xEB)
    def clc(self): self.emit(0x18)
    def sec(self): self.emit(0x38)
    def inc_a(self): self.emit(0x1A)

    def assemble(self) -> bytes:
        for pos, target, kind in self.fixups:
            dest = self.labels[target]
            if kind == "rel8":
                delta = dest - (self.origin + pos + 1)
                if not -128 <= delta <= 127:
                    raise ValueError(f"branch to {target} out of range ({delta})")
                self.code[pos] = delta & 0xFF
            elif kind == "rel16":
                self.code[pos:pos + 2] = ((dest - (self.origin + pos + 2)) & 0xFFFF).to_bytes(2, "little")
            else:
                self.code[pos:pos + 2] = (dest & 0xFFFF).to_bytes(2, "little")
        return bytes(self.code)


def _draw_from(asm: Asm, bank: int) -> None:
    """X = source address in `bank`; draw the message tilemap and return."""
    asm.sep(0x20)
    asm.phb()
    asm.lda_imm8(bank)
    asm.pha()
    asm.plb()
    asm.jsl(DRAW_TILEMAP)
    asm.plb()
    asm.rtl()


def build_code(origin: int) -> tuple[bytes, dict[str, int]]:
    a = Asm(origin)
    w = lambda addr: 0x7E0000 | addr  # noqa: E731  (long WRAM address)

    # -- player per-frame tick: handle the receive mailbox ---------------
    a.label("tick")
    a.php()
    a.rep(0x30)
    a.phx()
    a.phy()
    a.lda_long(w(MAILBOX_STATE))
    a.cmp_imm16(1)
    a.beq("try_start")
    a.cmp_imm16(2)
    a.far(0xF0, "try_finish")
    a.brl("tick_done")

    a.label("try_start")
    # Same conditions a chest checks before opening (vanilla $C05A86-$C05ACA).
    a.lda_long(w(0x00D3))
    a.and_imm16(0x00FF)
    a.cmp_imm16(0x0002)
    a.far(0xD0, "tick_done")
    a.lda_long(w(0x0104))
    a.and_imm16(0xF20F)
    a.far(0xD0, "tick_done")
    a.lda_long(w(0x0102))
    a.bit_imm16(0x3F7F)
    a.far(0xD0, "tick_done")
    a.bit_imm16(0x4000)
    a.far(0xF0, "tick_done")
    a.lda_long(w(0x225E))
    a.far(0xD0, "tick_done")
    a.lda_long(w(0x1B73))
    a.far(0xD0, "tick_done")
    a.lda_long(w(0x0124))
    a.tax()
    a.lda_longx(w(0x08D9))
    a.far(0xD0, "tick_done")

    a.lda_long(w(MAILBOX_ITEM))
    a.jsr("give")
    a.rep(0x30)
    a.lda_long(w(RECEIVED_COUNT))
    a.inc_a()
    a.sta_long(w(RECEIVED_COUNT))
    a.lda_imm16(DISPLAY_RECEIVED)
    a.sta_long(w(0x2254))
    a.jsl(DRAW_MESSAGE)
    a.rep(0x30)
    a.lda_long(w(0x0104))
    a.ora_imm16(0x0008)          # same bit the chest script sets ($C05ACB)
    a.sta_long(w(0x0104))
    a.lda_long(w(0x1B63))
    a.and_imm16(0x00FF)
    a.bne("no_sound")
    a.sep(0x20)
    a.lda_imm8(ITEM_JINGLE)
    a.jsl(PLAY_SOUND)
    a.rep(0x30)
    a.label("no_sound")
    a.lda_imm16(2)
    a.sta_long(w(MAILBOX_STATE))
    a.brl("tick_done")

    a.label("try_finish")
    a.lda_long(w(0x0104))
    a.and_imm16(0x8008)          # still holding the item up
    a.far(0xD0, "tick_done")
    a.jsl(CLOSE_MESSAGE)
    a.rep(0x30)
    a.lda_imm16(0)
    a.sta_long(w(MAILBOX_STATE))

    a.label("tick_done")
    a.rep(0x30)
    a.ply()
    a.plx()
    a.plp()
    a.rep(0x20)                  # replaced vanilla code: REP #$20 / LDA $0104
    a.lda_abs(0x0104)
    a.rtl()

    # -- give(A = item) ----------------------------------------------------
    a.label("give")
    a.cmp_imm16(ITEM_NONE)
    a.beq("give_ret")
    a.cmp_imm16(0x0006)
    a.bcs("give_flag")
    a.asl()
    a.tax()
    a.jmp_absx("give_table")

    a.label("give_flag")
    a.tax()
    a.sep(0x20)
    a.lda_imm8(1)
    a.sta_longx(0x7E0000)
    a.rep(0x20)
    a.label("give_ret")
    a.rts()

    a.label("give_life")
    a.lda_long(w(0x011E))
    a.clc()
    a.adc_imm16(0x0008)
    a.sta_long(w(0x011E))
    a.sta_long(w(0x011A))
    a.rts()

    a.label("give_magic")
    a.lda_long(w(0x0120))
    a.inc_a()
    a.sta_long(w(0x0120))
    a.lda_long(w(0x011C))
    a.inc_a()
    a.sta_long(w(0x011C))
    a.rts()

    for index, table in COIN_AMOUNT_TABLES.items():
        a.label(f"give_coins{index}")
        a.lda_imm16(0x0435)
        a.sta_dp(0x0A)
        a.lda_imm16(0x007E)
        a.sta_dp(0x0C)
        a.lda_imm16(table)
        a.sta_dp(0x0E)
        a.lda_imm16(0x00C0)
        a.sta_dp(0x10)
        a.ldy_imm16(0)
        a.jsl(ADD_MONEY)
        a.rep(0x30)
        a.rts()

    a.label("give_table")
    for name in ("give_life", "give_magic", "give_coins2", "give_coins3", "give_coins4", "give_coins5"):
        a.word(name)

    # -- chest display index (replaces $C05C13) ---------------------------
    a.label("set_index")
    a.rep(0x20)
    a.lda_absy(0x0C79)
    a.cmp_imm16(SINK_BASE)
    a.bcc("idx_vanilla")
    a.cmp_imm16(SINK_BASE + MAX_SENT_MESSAGES)
    a.bcs("idx_vanilla")
    a.sec()
    a.sbc_imm16(SINK_BASE - DISPLAY_SENT_BASE)
    a.sta_abs(0x2254)
    a.rtl()
    a.label("idx_vanilla")
    a.cmp_imm16(0x0006)
    a.bcc("idx_common")
    a.sec()
    a.sbc_imm16(0x044A)
    a.sta_abs(0x2254)
    a.rtl()
    a.label("idx_common")
    a.tax()
    a.lda_longx(COMMON_DISPLAY_TABLE)
    a.and_imm16(0x00FF)
    a.sta_abs(0x2254)
    a.rtl()

    # -- held-item graphics index (called from $C05C39) -------------------
    a.label("gfx_index")
    a.lda_abs(0x2254)
    a.cmp_imm16(DISPLAY_RECEIVED)
    a.bcs("gfx_ap")
    a.asl()
    a.asl()
    a.asl()
    a.tax()
    a.rtl()
    a.label("gfx_ap")
    a.lda_imm16((file_to_snes(GFX_ENTRY_OFFSET) - HELD_GFX_TABLE) & 0xFFFF)
    a.tax()
    a.rtl()

    # -- message draw (called from $C05DEA) -------------------------------
    a.label("draw_msg")
    a.rep(0x30)
    a.lda_abs(0x2254)
    a.cmp_imm16(DISPLAY_SENT_BASE)
    a.bcs("msg_sent")
    a.cmp_imm16(DISPLAY_RECEIVED)
    a.beq("msg_received")
    a.asl()
    a.tax()
    a.lda_longx(0xC50000)
    a.tax()
    _draw_from(a, 0xC5)
    a.label("msg_received")
    a.ldx_imm16(MAILBOX_MESSAGE)
    _draw_from(a, 0x7E)
    a.label("msg_sent")
    a.sec()
    a.sbc_imm16(DISPLAY_SENT_BASE)
    a.asl()
    a.tax()
    a.lda_longx(file_to_snes(SENT_TABLE_OFFSET))
    a.tax()
    _draw_from(a, file_to_snes(SENT_MESSAGES_OFFSET) >> 16)

    code = a.assemble()
    return code, {k: v for k, v in a.labels.items()}


# ---------------------------------------------------------------------------
# Patch application
# ---------------------------------------------------------------------------

def _data(name: str) -> bytes:
    """Read worlds/sai2/data/<name>. pkgutil also works inside an .apworld zip."""
    data = pkgutil.get_data("worlds.sai2", f"data/{name}")
    if data is None:
        raise FileNotFoundError(f"worlds/sai2/data/{name} is missing")
    return data


def _write(rom: bytearray, offset: int, data: bytes) -> None:
    rom[offset:offset + len(data)] = data


def _check_free(rom: bytes, offset: int, size: int) -> None:
    if any(b != 0xFF for b in rom[offset:offset + size]):
        raise ValueError(f"SAI2 multiworld: ROM space 0x{offset:06X}+{size} is not free.")


def apply_multiworld_patch(rom: bytearray) -> None:
    """Install the v15 hooks, AP logo and empty sent-message table."""
    for address, expected in VANILLA_HOOKS.items():
        offset = snes_to_file(address)
        if bytes(rom[offset:offset + len(expected)]) != expected:
            raise ValueError(f"SAI2 multiworld: unexpected bytes at ${address:06X}.")

    code, labels = build_code(file_to_snes(CODE_OFFSET))
    if len(code) > LOGO_OFFSET - CODE_OFFSET:
        raise ValueError("SAI2 multiworld: hook code too large.")
    for offset, size in ((CODE_OFFSET, len(code)), (LOGO_OFFSET, 0x420), (SENT_TABLE_OFFSET, 2 * MAX_SENT_MESSAGES),
                         (SENT_MESSAGES_OFFSET, MESSAGE_SIZE * MAX_SENT_MESSAGES), (GFX_ENTRY_OFFSET, 8)):
        _check_free(rom, offset, size)
    _write(rom, CODE_OFFSET, code)

    def jsl(label: str) -> bytes:
        target = labels[label]
        return bytes([0x22, target & 0xFF, (target >> 8) & 0xFF, target >> 16])

    def jml(label: str) -> bytes:
        return bytes([0x5C]) + jsl(label)[1:]

    _write(rom, snes_to_file(0xC20807), jsl("tick") + b"\xEA")
    _write(rom, snes_to_file(0xC05C13), jml("set_index"))
    _write(rom, snes_to_file(0xC05C39), jsl("gfx_index") + b"\xEA" * 3)
    _write(rom, snes_to_file(0xC05DEA), jsl("draw_msg") + b"\xEA" * 18)

    _write(rom, LOGO_OFFSET, _data("ap_logo.bin"))
    _write(rom, LOGO_PALETTE_OFFSET, _data("ap_logo_palette.bin"))
    logo = file_to_snes(LOGO_OFFSET)
    palette = file_to_snes(LOGO_PALETTE_OFFSET)
    # gfx source (3), palette source (3), held pose $0014 (32x32 over the head)
    _write(rom, GFX_ENTRY_OFFSET, logo.to_bytes(3, "little") + palette.to_bytes(3, "little")
           + HELD_POSE.to_bytes(2, "little"))

    blank = encode_message("", "", "")
    for k in range(MAX_SENT_MESSAGES):
        write_sent_message(rom, k, blank)


def write_sent_message(rom: bytearray, k: int, message: bytes) -> None:
    if not 0 <= k < MAX_SENT_MESSAGES:
        raise ValueError(f"sent message index {k} out of range")
    offset = SENT_MESSAGES_OFFSET + k * MESSAGE_SIZE
    _write(rom, offset, message)
    _write(rom, SENT_TABLE_OFFSET + 2 * k, (file_to_snes(offset) & 0xFFFF).to_bytes(2, "little"))


def sink_item(k: int) -> int:
    """ROM item id for a chest that holds another player's item."""
    return SINK_BASE + k


def sent_display_code(k: int) -> int:
    """Event message code ($2254) for an event that holds another player's item."""
    return DISPLAY_SENT_BASE + k
