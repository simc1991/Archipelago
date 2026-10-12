-- SAI2 Archipelago debug helper (v15.0)
-- TESTING ONLY - this script writes to game memory.
--
-- Hotkeys:
--   R : simulate receiving an Archipelago item (v15 ROMs only): queues
--       "YOU'VE OBTAINED / 1000 COINS / FROM DEBUG" in the WRAM mailbox. The
--       ROM shows it with the AP logo as soon as Higgins can act. The saved
--       "received items" counter is restored afterwards so the real client
--       does not skip an item.
--   I : give every real item flag (35 flags, see ITEM_FLAGS below).
--       Lets you rush the final boss instead of collecting items.
--       DO NOT write the whole $044E-$047F range: the gaps are other
--       game flags (one of them once triggered the real ending).
--   V : ask the client to report victory. Writes $1E9F = 1; the Archipelago
--       client sees that flag and sends CLIENT_GOAL. This tests the goal
--       reporting path without corrupting the running game.
--   NumPad1 (or 1) : for ~10 s, whenever the game writes an item id to $2254
--       (the "item being displayed" slot) it is replaced by $0003, so the
--       next chest you open shows "1000 COINS" through the real game code.
--   L : dump $D3 / $10 / $2254 once.
--
-- Every change to $D3, $10 and $2254 is logged, so you can watch the real
-- chest display and the real ending sequence and compare with
-- RetroAchievements #37019.
--
-- $1E9F is in the WRAM range already used for event check flags
-- ($1E80-$1E90), away from the game's normal data.

local DOMAIN = "WRAM"
local GAME_MODE = 0x00D3
local ENDING = 0x0010
local DISPLAY_ITEM = 0x2254
local GOAL_DEBUG_FLAG = 0x1E9F

local FORCE_ITEM_ID = 0x0003      -- 1000 Coins
local FORCE_ITEM_FRAMES = 600     -- ~10 seconds
local force_item_frames = 0

-- Real item flags only (from Items.py). The gaps are other game flags.
local ITEM_FLAGS = {
    0x044E, 0x044F, 0x0450, 0x0451, 0x0452, 0x0453, 0x0455, 0x0456,
    0x0458, 0x0459, 0x045B, 0x045C, 0x045D, 0x0460, 0x0461, 0x0462,
    0x0464, 0x0466, 0x0467, 0x0468, 0x0469, 0x046A, 0x046B, 0x046C,
    0x046D, 0x046E, 0x046F, 0x0470, 0x0471, 0x0472, 0x0473, 0x0474,
    0x047D, 0x047E, 0x047F,
}

-- v15 receive mailbox (see Multiworld.py)
local MAILBOX_STATE = 0x1D00
local MAILBOX_ITEM = 0x1D02
local MAILBOX_MESSAGE = 0x1D10
local RECEIVED_COUNT = 0x03D0
local debug_receive_count = nil   -- counter value to restore

local function font_tile(ch)
    local b = ch:byte()
    if b >= 65 and b <= 90 then return 0x50 + b - 65 end
    if b >= 48 and b <= 57 then return 0xA0 + b - 48 end
    if ch == "'" then return 0x6A end
    return nil
end

local function message_row(text)
    local row = {}
    local pad = math.floor((32 - #text) / 2)
    for col = 0, 31 do
        local ch = text:sub(col - pad + 1, col - pad + 1)
        local tile = (col >= pad and ch ~= "") and font_tile(ch) or nil
        row[#row + 1] = tile or 0x90
        row[#row + 1] = tile and 0x2C or 0x28
    end
    return row
end

local function queue_debug_item()
    if memory.read_u16_le(MAILBOX_STATE, DOMAIN) ~= 0 then
        console.log("[DBG] mailbox busy, try again")
        return
    end
    local bytes = {0x20, 0x00, 0x03, 0x00, 0x00}
    for _, line in ipairs({"YOU'VE OBTAINED", "1000 COINS", "FROM DEBUG"}) do
        for _, b in ipairs(message_row(line)) do bytes[#bytes + 1] = b end
    end
    for i, b in ipairs(bytes) do memory.write_u8(MAILBOX_MESSAGE + i - 1, b, DOMAIN) end
    debug_receive_count = memory.read_u16_le(RECEIVED_COUNT, DOMAIN)
    memory.write_u16_le(MAILBOX_ITEM, 0x0003, DOMAIN)
    memory.write_u16_le(MAILBOX_STATE, 1, DOMAIN)
    console.log("[DBG] AP item queued: shows as soon as Higgins can act")
end

local prev_mode = memory.read_u8(GAME_MODE, DOMAIN)
local prev_ending = memory.read_u8(ENDING, DOMAIN)
local prev_display = memory.read_u16_le(DISPLAY_ITEM, DOMAIN)
local prev_keys = input.get()

console.clear()
console.log("=================================================")
console.log(" SAI2 AP debug helper")
console.log(" I = all items   V = report victory (via $1E9F)")
console.log(" NumPad1 = next chest shows 1000 Coins")
console.log(" L = dump $D3 / $10 / $2254   R = receive an AP item")
console.log(string.format(" Now: $%04X=%02X  $%04X=%02X  $%04X=%04X",
    GAME_MODE, prev_mode, ENDING, prev_ending, DISPLAY_ITEM, prev_display))
console.log("=================================================")

local function pressed(key)
    return prev_keys[key] ~= true and input.get()[key] == true
end

local function pressed_any(keys)
    local current = input.get()
    for _, key in ipairs(keys) do
        if prev_keys[key] ~= true and current[key] == true then
            return true
        end
    end
    return false
end

while true do
    -- Hotkeys
    if pressed("I") then
        for _, address in ipairs(ITEM_FLAGS) do
            memory.write_u8(address, 1, DOMAIN)
        end
        console.log(string.format("[DBG] %d item flags set", #ITEM_FLAGS))
    end

    if pressed("V") then
        memory.write_u8(GOAL_DEBUG_FLAG, 1, DOMAIN)
        console.log("[DBG] goal flag $1E9F set: the client should now")
        console.log("[DBG] report victory (check its log + the server)")
    end

    if pressed("R") then
        queue_debug_item()
    end
    if debug_receive_count and memory.read_u16_le(MAILBOX_STATE, DOMAIN) == 0
            and memory.read_u16_le(RECEIVED_COUNT, DOMAIN) ~= debug_receive_count then
        memory.write_u16_le(RECEIVED_COUNT, debug_receive_count, DOMAIN)
        debug_receive_count = nil
        console.log("[DBG] AP item shown; received counter restored")
    end

    if pressed("L") then
        console.log(string.format("[DBG] $%04X=%02X  $%04X=%02X  $%04X=%04X",
            GAME_MODE, memory.read_u8(GAME_MODE, DOMAIN),
            ENDING, memory.read_u8(ENDING, DOMAIN),
            DISPLAY_ITEM, memory.read_u16_le(DISPLAY_ITEM, DOMAIN)))
    end

    if pressed_any({"NumberPad1", "NumPad1", "D1"}) then
        force_item_frames = FORCE_ITEM_FRAMES
        console.log("[DBG] 1000 Coins override armed for ~10 s.")
        console.log("[DBG] Open a chest: $2254 will be forced to $0003.")
    end

    -- Replace the displayed item ONLY while the game is showing one.
    -- ($2254 is 0 outside chest/item sequences, so this never touches
    -- normal gameplay and cannot freeze the game.)
    if force_item_frames > 0 then
        local value = memory.read_u16_le(DISPLAY_ITEM, DOMAIN)
        if value ~= 0 and value ~= FORCE_ITEM_ID then
            memory.write_u16_le(DISPLAY_ITEM, FORCE_ITEM_ID, DOMAIN)
            console.log(string.format(
                "[DBG] $2254: $%04X -> $%04X (1000 Coins)",
                value, FORCE_ITEM_ID))
        end
        force_item_frames = force_item_frames - 1
        if force_item_frames == 0 then
            console.log("[DBG] 1000 Coins override expired")
        end
    end

    -- Watch the interesting bytes
    local mode = memory.read_u8(GAME_MODE, DOMAIN)
    local ending = memory.read_u8(ENDING, DOMAIN)
    local display = memory.read_u16_le(DISPLAY_ITEM, DOMAIN)

    if mode ~= prev_mode or ending ~= prev_ending then
        console.log(string.format("[DBG] $%04X: %02X -> %02X   $%04X: %02X -> %02X",
            GAME_MODE, prev_mode, mode, ENDING, prev_ending, ending))
    end
    if display ~= prev_display then
        console.log(string.format("[DBG] $%04X: %04X -> %04X",
            DISPLAY_ITEM, prev_display, display))
    end
    prev_mode = mode
    prev_ending = ending
    prev_display = display

    prev_keys = input.get()
    emu.frameadvance()
end
