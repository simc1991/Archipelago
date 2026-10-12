local checks = {
    ["Poka Isle - Health 18890"] = 0x0491,
    ["Poka Isle - Dagger"] = 0x0497,
    ["Poka Isle - Health 18D8D"] = 0x0492,
    ["Poka Isle - 500 Coins"] = 0x0493,
    ["Poka Isle - Ice Sword"] = 0x0496,
    ["Poka Isle - 1000 Coins"] = 0x053E,
    ["Poka Isle - Silver Sword"] = 0x0490,
    ["Poka Isle - 2000 Coins"] = 0x0494,
    ["Poka Isle - Fireballs"] = 0x0495,
    ["Poka Isle - Light Spell"] = 0x0470,

    ["Hiya Isle - Fire Sword"] = 0x04A9,
    ["Hiya Isle - Magic FB57E"] = 0x04AA,
    ["Hiya Isle - Health FB59A"] = 0x04AB,
    ["Hiya Isle - Fire Shield"] = 0x04AC,
    ["Hiya Isle - Health FB5D2"] = 0x04AD,
    ["Hiya Isle - Health FB5EE"] = 0x04AE,
    ["Hiya Isle - Fire Armor"] = 0x04AF,
    ["Hiya Isle - 1000 Coins"] = 0x04B0,
    ["Hiya Isle - Health FB642"] = 0x053F,
    ["Hiya Isle - Star Spell"] = 0x051F,

    ["Boa Isle - Ice Shield"] = 0x053D,
    ["Boa Isle - Magic FC7CE"] = 0x04EE,
    ["Boa Isle - Magic FC7E5"] = 0x04EF,
    ["Boa Isle - 1000 Coins"] = 0x04F0,
    ["Boa Isle - Ice Armor"] = 0x04F1,
    ["Boa Isle - 2000 Coins"] = 0x04F2,
    ["Boa Isle - Magic FC841"] = 0x04F3,

    ["Puka Isle - 500 Coins"] = 0x04C6,
    ["Puka Isle - Magic FD5B2"] = 0x04C7,
    ["Puka Isle - 1000 Coins FD5C9"] = 0x04C8,
    ["Puka Isle - Magic FD5E0"] = 0x04C9,
    ["Puka Isle - Magic FD5F7"] = 0x04CA,
    ["Puka Isle - Health FD60E"] = 0x04CB,
    ["Puka Isle - 1000 Coins FD625"] = 0x04CD,
    ["Puka Isle - Magic FD63C"] = 0x04CE,
    ["Puka Isle - Aqua Armor"] = 0x04F5,
    ["Puka Isle - Thunder Sword"] = 0x04F6,
    ["Puka Isle - Aqua Spell"] = 0x051E,

    ["Sala Isle - Health FE610"] = 0x0504,
    ["Sala Isle - 2000 Coins"] = 0x0505,
    ["Sala Isle - Magic FE63E"] = 0x0506,
    ["Sala Isle - Crystal Sword"] = 0x0507,
    ["Sala Isle - Aqua Shield"] = 0x0508,
    ["Sala Isle - Magic FE683"] = 0x0509,
    ["Sala Isle - Magic FE69A"] = 0x050A,
    ["Sala Isle - Axe"] = 0x050B,

    ["Fuwa Isle - Health FEF90"] = 0x0515,
    ["Fuwa Isle - 5000 Coins"] = 0x0516,
    ["Fuwa Isle - Magic FEFBE"] = 0x0517,
    ["Fuwa Isle - Magic FEFD5"] = 0x0518,
    ["Fuwa Isle - Power Sword"] = 0x0519,
}

local previous = {}

console.clear()
console.log("SAI2 Archipelago check monitor")
console.log("Monitoring " .. tostring(51) .. " standard checks")
console.log("----------------------------------------")

for name, address in pairs(checks) do
    previous[name] = memory.read_u8(address, "WRAM")
end

while true do
    for name, address in pairs(checks) do
        local value = memory.read_u8(address, "WRAM")
        local old = previous[name]

        if old == 0 and value ~= 0 then
            console.log(
                string.format(
                    "CHECK: %s  WRAM=$%04X  %02X -> %02X",
                    name,
                    address,
                    old,
                    value
                )
            )
        end

        previous[name] = value
    end

    emu.frameadvance()
end