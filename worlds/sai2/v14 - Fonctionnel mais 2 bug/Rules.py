from BaseClasses import CollectionState


SWORDS = (
    "Silver Sword",
    "Fire Sword",
    "Ice Sword",
    "Thunder Sword",
    "Crystal Sword",
    "Power Sword",
)

WEAPONS = (
    *SWORDS,
    "Dagger",
    "Fireballs",
    "Axe",
)

ARMORS = (
    "Fire Armor",
    "Ice Armor",
    "Aqua Armor",
)


def has_any(state: CollectionState, player: int, items: tuple[str, ...]) -> bool:
    """Return True when the player owns at least one item from the group."""
    return any(state.has(item, player) for item in items)


def has_sword(state: CollectionState, player: int) -> bool:
    """
    Equivalent to:
    .def sword 044e|044f|0450|0451|0452|0453
    """
    return has_any(state, player, SWORDS)


def has_weapon(state: CollectionState, player: int) -> bool:
    """
    Equivalent to:
    .def weapon sword|0455|0456|0458
    """
    return has_any(state, player, WEAPONS)


def has_armor(state: CollectionState, player: int) -> bool:
    """
    Equivalent to:
    .def armor 045b|045c|045d
    """
    return has_any(state, player, ARMORS)


def has_durability(state: CollectionState, player: int) -> bool:
    """
    Equivalent to:
    .def durability armor&lifebottle
    """
    return (
        has_armor(state, player)
        and state.has("Life Bottle", player)
    )


def can_defeat_boss(state: CollectionState, player: int) -> bool:
    """
    Equivalent to:
    .def boss lifebottle&weapon
    """
    return (
        state.has("Life Bottle", player)
        and has_weapon(state, player)
    )


def has_poka_sword_access(state, player):
    """
    Original sai2_rando logic:

        poka_sword = (poka & silversword) | fuwa_poka_warp

    When evaluating locations inside Poka, the normal route requires
    Silver Sword.

    The alternate route through Fuwa requires:
        Shove
        Shovel

    Access to Fuwa Isle itself is handled by the region graph.
    """
    return (
        state.has("Silver Sword", player)
        or (
            state.has("Shove", player)
            and state.has("Shovel", player)
        )
    )


def sun_blocks_off(state: CollectionState, player: int) -> bool:
    """
    sunswitch = boa_isle
    sunblocks_off = sunswitch
    """
    return state.can_reach("Boa Isle", "Region", player)


def moon_blocks_on(state: CollectionState, player: int) -> bool:
    """
    moonswitch = sala_isle
    moonblocks_on = moonswitch
    """
    return state.can_reach("Sala Isle", "Region", player)

def star_switch(state: CollectionState, player: int) -> bool:
    """Conservative Hiya ice-wall logic: require Fire Sword to reach the star switch.

    The previous Sala warp alternative allowed the switch without Fire Sword,
    which made Hiya checks appear in progression spheres before they were
    physically accessible in the tested route.
    """
    return (
        state.can_reach("Hiya Isle", "Region", player)
        and state.has("Fire Sword", player)
        and state.has("Shove", player)
    )


def aqua_switch(state: CollectionState, player: int) -> bool:
    """
    requirements.txt:

    aquaswitch =
        puka_drained
        | sala_puka_warp
    """

    puka_drained = state.can_reach(
        "Puka Drained",
        "Region",
        player,
    )

    # sala_puka_warp =
    # shove & sala_isle & shovel
    sala_warp = (
        state.can_reach("Sala Isle", "Region", player)
        and state.has("Shove", player)
        and state.has("Shovel", player)
    )

    return puka_drained or sala_warp

def can_up_jab(state: CollectionState, player: int) -> bool:
    return (
            state.has("Up Jab", player)
        and has_sword(state, player)
        and state.has("1000 Coins", player)
    )


def can_down_jab(state: CollectionState, player: int) -> bool:
    return (
        state.has("Down Jab", player)
        and has_sword(state, player)
        and (
            state.has("500 Coins", player)
            or state.has("1000 Coins", player)
        )
    )

def has_ax_capability(state: CollectionState, player: int) -> bool:
    return (
        state.has("Axe", player)
        or can_up_jab(state, player)
    )

def set_rules(world) -> None:
    """
    Apply Super Adventure Island II access rules.

    This is the first logic layer:
    - Starting access
    - Poka Isle
    - Boa
    - Boa Isle
    """

    multiworld = world.multiworld
    player = world.player

    # Ensure Fire Sword is placed in an early reachable location rather than
    # behind the ice-wall checks it unlocks.
    multiworld.local_early_items[player]["Fire Sword"] = 1

    # ---------------------------------------------------------
    # Menu -> Poka
    #
    # requirements.txt:
    # .def poka *
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Start Game", player
    ).access_rule = lambda state: True

    # ---------------------------------------------------------
    # Poka -> Poka Isle
    #
    # requirements.txt:
    # .def poka_isle *
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Enter Poka Isle", player
    ).access_rule = lambda state: True

    # ---------------------------------------------------------
    # Poka -> Boa
    #
    # requirements.txt:
    # .def boa lightgate_down|hiya&sungate_down
    #
    # From the starting side, Light Gate is the initial route.
    # Light gate down:
    # .def lightgate_down lightstone
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Poka to Boa", player
    ).access_rule = lambda state: state.has(
        "Light Stone",
        player,
    )

    # =========================================================
    # BOSS / EVENT LOCATIONS
    # =========================================================

    # lightstone_10305
    # poka_sword & boss
    multiworld.get_location(
        "Poka - Light Stone", player
    ).access_rule = lambda state: (
        has_poka_sword_access(state, player)
        and can_defeat_boss(state, player)
    )

    # starstone_116ec
    # starswitch & shove & boss
    multiworld.get_location(
        "Hiya - Star Stone", player
    ).access_rule = lambda state: (
        star_switch(state, player)
        and state.has("Shove", player)
        and can_defeat_boss(state, player)
    )

    # elvenflute_14159
    # sala_isle & shove & shovel & downjab & ax & boss
    multiworld.get_location(
        "Sala - Elven Flute", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and state.has("Shovel", player)
        and can_down_jab(state, player)
        and has_ax_capability(state, player)
        and can_defeat_boss(state, player)
    )

    # skybell_14c5c
    # fuwa_isle & powersword & shovel & boss
    multiworld.get_location(
        "Fuwa - Sky Bell", player
    ).access_rule = lambda state: (
        state.has("Power Sword", player)
        and state.has("Shovel", player)
        and can_defeat_boss(state, player)
    )

    # aquastone_16d70
    # boa_isle & shove & icesword & boss
    multiworld.get_location(
        "Puka - Aqua Stone", player
    ).access_rule = lambda state: (
        state.can_reach("Boa Isle", "Region", player)
        and state.has("Shove", player)
        and state.has("Ice Sword", player)
        and can_defeat_boss(state, player)
    )
 
    # moonstone_17a91
    # puka_isle & shove & shovel & aquaswitch & boss
    multiworld.get_location(
        "Puka Isle - Moon Stone", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and state.has("Shovel", player)
        and aqua_switch(state, player)
        and can_defeat_boss(state, player)
    )

    # sunstone_1a961
    # boa & lifebottle | boa & weapon
    #
    # Because this location is already in the Boa region,
    # Boa reachability is handled by Archipelago.
    multiworld.get_location(
        "Boa - Sun Stone", player
    ).access_rule = lambda state: (
        state.has("Life Bottle", player)
        or has_weapon(state, player)
    )

    # ---------------------------------------------------------
    # Boa -> Boa Isle
    #
    # requirements.txt:
    # .def boa_isle boa&sunring&durability
    #
    # Reaching this entrance already means Boa is reachable,
    # so the remaining requirements are:
    #   Sun Ring
    #   + durability
    #
    # durability = armor & Life Bottle
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Enter Boa Isle", player
    ).access_rule = lambda state: (
        state.has("Sun Ring", player)
        and has_durability(state, player)
    )   
    
    # ---------------------------------------------------------
    # Boa -> Hiya
    #
    # requirements.txt:
    # .def hiya boa&sungate_down | ...
    # .def sungate_down boa&sunstone
    #
    # Since Boa is already reachable when using this entrance,
    # only Sun Stone remains to be checked.
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Boa to Hiya", player
    ).access_rule = lambda state: state.has(
        "Sun Stone",
        player,
    )

    # ---------------------------------------------------------
    # Hiya -> Star Zone
    #
    # requirements.txt:
    # .def star_zone hiya&stargate_down | ...
    # .def stargate_down hiya&starstone
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Hiya to Star Zone", player
    ).access_rule = lambda state: state.has(
        "Star Stone",
        player,
    )

    # ---------------------------------------------------------
    # Star Zone -> Hiya
    #
    # requirements.txt:
    # .def hiya ... | star_zone&stargate_down
    #
    # Once Star Zone is reachable, Star Stone opens this route.
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Star Zone to Hiya", player
    ).access_rule = lambda state: state.has(
        "Star Stone",
        player,
    )
    
    # ---------------------------------------------------------
    # Moon Gate routes
    #
    # requirements.txt:
    #
    # .def puka
    #     ... | star_zone&moongate_down
    #         | sala&moongate_down
    #
    # .def sala
    #     puka&moongate_down
    #     | star_zone&moongate_down
    #
    # .def star_zone
    #     ... | puka&moongate_down
    #         | sala&moongate_down
    #
    # Moon Stone controls these routes.
    # ---------------------------------------------------------

    multiworld.get_entrance(
        "Star Zone to Puka", player
    ).access_rule = lambda state: state.has(
        "Moon Stone", player
    )

    multiworld.get_entrance(
        "Star Zone to Sala", player
    ).access_rule = lambda state: state.has(
        "Moon Stone", player
    )

    multiworld.get_entrance(
        "Puka to Sala", player
    ).access_rule = lambda state: state.has(
        "Moon Stone", player
    )

    multiworld.get_entrance(
        "Puka to Star Zone", player
    ).access_rule = lambda state: state.has(
        "Moon Stone", player
    )

    multiworld.get_entrance(
        "Sala to Puka", player
    ).access_rule = lambda state: state.has(
        "Moon Stone", player
    )

    multiworld.get_entrance(
        "Sala to Star Zone", player
    ).access_rule = lambda state: state.has(
        "Moon Stone", player
    )
    
    # ---------------------------------------------------------
    # Boa -> Hiya warp
    #
    # .def boa_hiya_warp shove&boa_isle&shovel
    #
    # Being at Boa Isle already satisfies boa_isle.
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Boa Isle Warp to Hiya", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and state.has("Shovel", player)
    )

    # ---------------------------------------------------------
    # Boa -> Poka warp
    #
    # .def boa_poka_warp shove&boa_isle
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Boa Isle Warp to Poka", player
    ).access_rule = lambda state: state.has(
        "Shove", player
    )

    # ---------------------------------------------------------
    # Sala -> Hiya warp
    #
    # .def sala_hiya_warp shove&sala_isle&shovel
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Sala Isle Warp to Hiya", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and state.has("Shovel", player)
    )

    # ---------------------------------------------------------
    # Sala -> Puka warp
    #
    # .def sala_puka_warp shove&sala_isle&shovel
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Sala Isle Warp to Puka", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and state.has("Shovel", player)
    )
    # ---------------------------------------------------------
    # Hiya Isle
    #
    # requirements.txt:
    #
    # .def hiya_isle
    #   hiya&icebell&shove
    #   | boa_hiya_warp&firesword&shovel
    #   | hiya_warp&magicwand&shove
    #   | sala_hiya_warp&firesword
    #
    # IMPORTANT:
    # This entrance represents the normal Hiya route only.
    # Alternate warp routes will be represented separately.
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Enter Hiya Isle", player
    ).access_rule = lambda state: (
        state.has("Ice Bell", player)
        and state.has("Shove", player)
    )


    # ---------------------------------------------------------
    # Puka Isle
    #
    # .def puka_isle
    #   puka&powerfan&shovel&durability
    #   | puka_warp&magicwand&shovel&durability
    #
    # This is the normal Puka route.
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Enter Puka Isle", player
    ).access_rule = lambda state: (
        state.has("Power Fan", player)
        and state.has("Shovel", player)
        and has_durability(state, player)
    )


    # ---------------------------------------------------------
    # Puka Drained
    #
    # .def puka_drained puka_isle&shovel&shove
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Drain Puka", player
    ).access_rule = lambda state: (
        state.has("Shovel", player)
        and state.has("Shove", player)
    )


    # ---------------------------------------------------------
    # Sala Isle
    #
    # .def sala_isle sala&durability
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Enter Sala Isle", player
    ).access_rule = lambda state: has_durability(
        state, player
    )


    # ---------------------------------------------------------
    # Fuwa Isle
    #
    # .def fuwa_isle
    #   lightspell
    #   & starspell
    #   & sunspell
    #   & aquaspell
    #   & moonspell
    #   & durability
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Sala to Fuwa Isle", player
    ).access_rule = lambda state: (
        state.has("Light Spell", player)
        and state.has("Star Spell", player)
        and state.has("Sun Spell", player)
        and state.has("Aqua Spell", player)
        and state.has("Moon Spell", player)
        and has_durability(state, player)
    )

    # ---------------------------------------------------------
    # Alternate access to Hiya Isle through Boa warp
    #
    # boa_hiya_warp = shove & boa_isle & shovel
    #
    # hiya_isle alternatives using this warp:
    #   boa_hiya_warp & firesword & shovel
    #   hiya_warp & magicwand & shove
    #
    # Since the entrance starts in Boa Isle, boa_isle is
    # already satisfied.
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Boa Warp to Hiya Isle", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and state.has("Shovel", player)
        and (
            state.has("Fire Sword", player)
            or state.has("Magic Wand", player)
        )
    )

    # ---------------------------------------------------------
    # Alternate access to Hiya Isle through Sala warp
    #
    # sala_hiya_warp = shove & sala_isle & shovel
    #
    # hiya_isle:
    #   sala_hiya_warp & firesword
    #   OR
    #   hiya_warp & magicwand & shove
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Sala Warp to Hiya Isle", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and state.has("Shovel", player)
        and (
            state.has("Fire Sword", player)
            or state.has("Magic Wand", player)
        )
    )

    # ---------------------------------------------------------
    # Alternate access to Puka Isle through Sala warp
    #
    # sala_puka_warp = shove & sala_isle & shovel
    #
    # puka_isle =
    #   puka_warp
    #   & magicwand
    #   & shovel
    #   & durability
    #
    # Sala Isle already guarantees durability to reach it.
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Sala Warp to Puka Isle", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and state.has("Shovel", player)
        and state.has("Magic Wand", player)
        and has_durability(state, player)
    )    
    
    # ---------------------------------------------------------
    # Fuwa -> Poka warp
    #
    # .def fuwa_poka_warp shove&fuwa_isle&shovel
    #
    # Fuwa Isle is already satisfied by reaching this entrance.
    # ---------------------------------------------------------
    multiworld.get_entrance(
        "Fuwa Warp to Poka", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and state.has("Shovel", player)
    )

    # ---------------------------------------------------------
    # Fuwa -> Puka warp
    #
    # .def fuwa_puka_warp
    #   shove&fuwa_isle&powersword&downjab
    # ---------------------------------------------------------
    # fuwa_puka_warp
    # shove & fuwa_isle & powersword & downjab
    multiworld.get_entrance(
        "Fuwa Warp to Puka", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and state.has("Power Sword", player)
        and can_down_jab(state, player)
    )
    # =========================================================
    # POKA ISLE LOCATIONS
    # =========================================================

    # health_18890
    # poka & silversword
    multiworld.get_location(
        "Poka Isle - Health 18890", player
    ).access_rule = lambda state: state.has(
        "Silver Sword", player
    )

    # dagger_18b47
    # poka_sword
    multiworld.get_location(
        "Poka Isle - Dagger", player
    ).access_rule = lambda state: has_poka_sword_access(
        state, player
    )

    # health_18d8d
    # poka & shovel
    multiworld.get_location(
        "Poka Isle - Health 18D8D", player
    ).access_rule = lambda state: state.has(
        "Shovel", player
    )

    # 500c_18dd0
    # poka_sword & shove
    multiworld.get_location(
        "Poka Isle - 500 Coins", player
    ).access_rule = lambda state: (
        has_poka_sword_access(state, player)
        and state.has("Shove", player)
    )

    # icesword_18e22
    # poka_sword & sunblocks_off
    multiworld.get_location(
        "Poka Isle - Ice Sword", player
    ).access_rule = lambda state: (
        has_poka_sword_access(state, player)
        and sun_blocks_off(state, player)
    )

    # 1000c_18e3e
    # poka_sword & elvenflute
    multiworld.get_location(
        "Poka Isle - 1000 Coins", player
    ).access_rule = lambda state: (
        has_poka_sword_access(state, player)
        and state.has("Elven Flute", player)
    )

    # silversword_18e78
    # poka & lightblocks_on
    #
    # Poka itself activates the light switch.
    multiworld.get_location(
        "Poka Isle - Silver Sword", player
    ).access_rule = lambda state: True

    # 2000c_1907e
    # poka_sword & moonblocks_on
    multiworld.get_location(
        "Poka Isle - 2000 Coins", player
    ).access_rule = lambda state: (
        has_poka_sword_access(state, player)
        and moon_blocks_on(state, player)
    )

    # fireballs_1909a
    # poka_sword & downjab
    #
    # "downjab" in the original randomizer is not just the Down Jab item.
    # The player must have:
    #   - Down Jab
    #   - any Sword
    #   - either 500 Coins or 1000 Coins
    multiworld.get_location(
        "Poka Isle - Fireballs", player
    ).access_rule = lambda state: (
        has_poka_sword_access(state, player)
        and can_down_jab(state, player)
    )

    # lightspell_1911a
    # poka_sword & elvenflute
    multiworld.get_location(
        "Poka Isle - Light Spell", player
    ).access_rule = lambda state: (
        has_poka_sword_access(state, player)
        and state.has("Elven Flute", player)
    )       
    
    # =========================================================
    # OVERWORLD / EVENT LOCATIONS
    # =========================================================

    # sunring_39179
    # star_zone
    #
    # Region reachability already handles the requirement.
    multiworld.get_location(
        "Overworld - Sun Ring", player
    ).access_rule = lambda state: True

    # icebell_39348
    # hiya & shove
    #
    # This location currently lives in the Overworld region,
    # therefore we must explicitly verify Hiya reachability.
    multiworld.get_location(
        "Overworld - Ice Bell", player
    ).access_rule = lambda state: (
        state.can_reach("Hiya", "Region", player)
        and state.has("Shove", player)
    )

    # magicwand_394d7
    # star_zone
    multiworld.get_location(
        "Overworld - Magic Wand", player
    ).access_rule = lambda state: True

    # shovel_39db9
    # puka
    #
    # Location currently belongs to Overworld, so explicitly
    # require Puka reachability.
    multiworld.get_location(
        "Overworld - Shovel", player
    ).access_rule = lambda state: state.can_reach(
        "Puka",
        "Region",
        player,
    )
    
     # =========================================================
    # TECHNIQUE LOCATIONS
    # =========================================================

    # downjab_2b9ef
    # puka
    multiworld.get_location(
        "Puka - Down Jab", player
    ).access_rule = lambda state: True

    # powerfan_1a9d9
    # puka & boss
    multiworld.get_location(
        "Puka - Power Fan", player
    ).access_rule = lambda state: can_defeat_boss(state, player)
    

    # upjab_2ba05
    # sala
    multiworld.get_location(
        "Sala - Up Jab", player
    ).access_rule = lambda state: True

    # shove_2ba1b
    # hiya
    multiworld.get_location(
        "Hiya - Shove", player
    ).access_rule = lambda state: True   
    
        # =========================================================
    # HIYA ISLE LOCATIONS
    # =========================================================

    # firesword_fb562
    # hiya_isle
    multiworld.get_location(
        "Hiya Isle - Fire Sword", player
    ).access_rule = lambda state: True

    # magic_fb57e
    # hiya_isle & shovel | boa_hiya_warp & firesword
    multiworld.get_location(
        "Hiya Isle - Magic FB57E", player
    ).access_rule = lambda state: (
        state.has("Shovel", player)
        or (
            state.can_reach("Boa Isle", "Region", player)
            and state.has("Shove", player)
            and state.has("Shovel", player)
            and state.has("Fire Sword", player)
        )
    )

    # health_fb59a
    # hiya_isle & sunblocks_off
    multiworld.get_location(
        "Hiya Isle - Health FB59A", player
    ).access_rule = lambda state: sun_blocks_off(
        state, player
    )

    # fireshield_fb5b6
    # starswitch & starblocks_off
    #
    # starblocks_off = starswitch
    multiworld.get_location(
        "Hiya Isle - Fire Shield", player
    ).access_rule = lambda state: star_switch(
        state, player
    )

    # health_fb5d2
    # starswitch & upjab
    multiworld.get_location(
        "Hiya Isle - Health FB5D2", player
    ).access_rule = lambda state: (
        star_switch(state, player)
        and can_up_jab(state, player)
    )

    # health_fb5ee
    # shove & starblocks_off
    multiworld.get_location(
        "Hiya Isle - Health FB5EE", player
    ).access_rule = lambda state: (
        state.has("Shove", player)
        and star_switch(state, player)
    )

    # firearmor_fb60a
    # starswitch
    multiworld.get_location(
        "Hiya Isle - Fire Armor", player
    ).access_rule = lambda state: star_switch(
        state, player
    )

    # 1000c_fb626
    # starswitch & starblocks_on
    #
    # starblocks_on = *
    multiworld.get_location(
        "Hiya Isle - 1000 Coins", player
    ).access_rule = lambda state: star_switch(
        state, player
    )

    # health_fb642
    # starswitch & elvenflute
    multiworld.get_location(
        "Hiya Isle - Health FB642", player
    ).access_rule = lambda state: (
        star_switch(state, player)
        and state.has("Elven Flute", player)
    )

    # starspell_fb659
    # starswitch & elvenflute
    multiworld.get_location(
        "Hiya Isle - Star Spell", player
    ).access_rule = lambda state: (
        star_switch(state, player)
        and state.has("Elven Flute", player)
    )
   
    # =========================================================
    # BOA ISLE LOCATIONS
    # =========================================================

    # iceshield_fc7b7
    # boa_isle
    multiworld.get_location(
        "Boa Isle - Ice Shield", player
    ).access_rule = lambda state: True

    # magic_fc7ce
    # boa_isle & sunblocks_on
    # sunblocks_on = *
    multiworld.get_location(
        "Boa Isle - Magic FC7CE", player
    ).access_rule = lambda state: True

    # magic_fc7e5
    # boa_isle & elvenflute & sunblocks_off
    multiworld.get_location(
        "Boa Isle - Magic FC7E5", player
    ).access_rule = lambda state: (
        state.has("Elven Flute", player)
        and sun_blocks_off(state, player)
    )

    # 1000c_fc7fc
    # boa_isle & shovel
    multiworld.get_location(
        "Boa Isle - 1000 Coins", player
    ).access_rule = lambda state: state.has(
        "Shovel", player
    )

    # icearmor_fc813
    # boa_isle
    multiworld.get_location(
        "Boa Isle - Ice Armor", player
    ).access_rule = lambda state: True

    # 2000c_fc82a
    # boa_isle & upjab
    multiworld.get_location(
        "Boa Isle - 2000 Coins", player
    ).access_rule = lambda state: can_up_jab(
        state, player
    )

    # magic_fc841
    # boa_isle & downjab
    multiworld.get_location(
        "Boa Isle - Magic FC841", player
    ).access_rule = lambda state: can_down_jab(
        state, player
    )

    # sunspell_fc894
    # boa_isle & elvenflute
    multiworld.get_location(
        "Boa Isle - Sun Spell", player
    ).access_rule = lambda state: state.has(
        "Elven Flute", player
    )   
    
        # =========================================================
    # PUKA ISLE LOCATIONS
    # =========================================================

    # 500c_fd59b
    # puka_isle & shovel & lightblocks_on
    # lightblocks_on = lightswitch = poka
    # Poka est la région de départ, donc seule Shovel est nécessaire ici.
    multiworld.get_location(
        "Puka Isle - 500 Coins", player
    ).access_rule = lambda state: state.has(
        "Shovel", player
    )

    # magic_fd5b2
    # puka_isle & downjab
    multiworld.get_location(
        "Puka Isle - Magic FD5B2", player
    ).access_rule = lambda state: can_down_jab(
        state, player
    )

    # 1000c_fd5c9
    # puka_isle & starblocks_on
    # starblocks_on = *
    multiworld.get_location(
        "Puka Isle - 1000 Coins FD5C9", player
    ).access_rule = lambda state: True

    # magic_fd5e0
    # puka_isle & upjab
    multiworld.get_location(
        "Puka Isle - Magic FD5E0", player
    ).access_rule = lambda state: can_up_jab(
        state, player
    )

    # magic_fd5f7
    # puka_drained
    multiworld.get_location(
        "Puka Isle - Magic FD5F7", player
    ).access_rule = lambda state: state.can_reach(
        "Puka Drained",
        "Region",
        player,
    )

    # health_fd60e
    # puka_drained & shovel & aquablocks_off
    # aquablocks_off = aquaswitch
    multiworld.get_location(
        "Puka Isle - Health FD60E", player
    ).access_rule = lambda state: (
        state.can_reach("Puka Drained", "Region", player)
        and state.has("Shovel", player)
        and aqua_switch(state, player)
    )

    # 1000c_fd625
    # puka_isle & elvenflute
    multiworld.get_location(
        "Puka Isle - 1000 Coins FD625", player
    ).access_rule = lambda state: state.has(
        "Elven Flute", player
    )

    # magic_fd63c
    # puka_isle & elvenflute
    multiworld.get_location(
        "Puka Isle - Magic FD63C", player
    ).access_rule = lambda state: state.has(
        "Elven Flute", player
    )

    # aquaarmor_fd653
    # puka_isle
    multiworld.get_location(
        "Puka Isle - Aqua Armor", player
    ).access_rule = lambda state: True

    # thundersword_fd66a
    # puka_isle
    multiworld.get_location(
        "Puka Isle - Thunder Sword", player
    ).access_rule = lambda state: True

    # aquaspell_fd681
    # puka_isle & elvenflute
    multiworld.get_location(
        "Puka Isle - Aqua Spell", player
    ).access_rule = lambda state: state.has(
        "Elven Flute", player
    )
    
        # =========================================================
    # SALA ISLE LOCATIONS
    # =========================================================

    # health_fe610
    # sala_isle & shovel
    multiworld.get_location(
        "Sala Isle - Health FE610", player
    ).access_rule = lambda state: state.has(
        "Shovel", player
    )

    # 2000c_fe627
    # sala_isle & shovel & shove & upjab
    multiworld.get_location(
        "Sala Isle - 2000 Coins", player
    ).access_rule = lambda state: (
        state.has("Shovel", player)
        and state.has("Shove", player)
        and can_up_jab(state, player)
    )

    # magic_fe63e
    # sala_isle & starblocks_on
    # starblocks_on = *
    multiworld.get_location(
        "Sala Isle - Magic FE63E", player
    ).access_rule = lambda state: True

    # crystalsword_fe655
    # sala_isle & shovel & downjab
    multiworld.get_location(
        "Sala Isle - Crystal Sword", player
    ).access_rule = lambda state: (
        state.has("Shovel", player)
        and can_down_jab(state, player)
    )

    # aquashield_fe66c
    # sala_isle & shovel &
    # lightblocks_on & sunblocks_on & starblocks_on &
    # aquablocks_on & moonblocks_on
    #
    # light/sun/star/aqua blocks ON impose no additional
    # item requirement here.
    # moonblocks_on = moonswitch = sala_isle.
    multiworld.get_location(
        "Sala Isle - Aqua Shield", player
    ).access_rule = lambda state: state.has(
        "Shovel", player
    )

    # magic_fe683
    # sala_isle & shovel & downjab & elvenflute
    multiworld.get_location(
        "Sala Isle - Magic FE683", player
    ).access_rule = lambda state: (
        state.has("Shovel", player)
        and can_down_jab(state, player)
        and state.has("Elven Flute", player)
    )

    # magic_fe69a
    # sala_isle & moonblocks_on
    # moonblocks_on = moonswitch = sala_isle
    multiworld.get_location(
        "Sala Isle - Magic FE69A", player
    ).access_rule = lambda state: True

    # ax_fe6b1
    # sala_isle & shovel & shove
    multiworld.get_location(
        "Sala Isle - Axe", player
    ).access_rule = lambda state: (
        state.has("Shovel", player)
        and state.has("Shove", player)
    )

    # moonspell_fe704
    # sala_isle & shovel & elvenflute
    multiworld.get_location(
        "Sala Isle - Moon Spell", player
    ).access_rule = lambda state: (
        state.has("Shovel", player)
        and state.has("Elven Flute", player)
    )
    # =========================================================
    # FUWA ISLE LOCATIONS
    # =========================================================

    # health_fef90
    # fuwa_isle & downjab & upjab & powersword
    multiworld.get_location(
        "Fuwa Isle - Health FEF90", player
    ).access_rule = lambda state: (
        can_down_jab(state, player)
        and can_up_jab(state, player)
        and state.has("Power Sword", player)
    )

    # 5000c_fefa7
    # fuwa_isle & moonblocks_on & starblocks_on
    #
    # starblocks_on = *
    # moonblocks_on = moonswitch = sala_isle
    multiworld.get_location(
        "Fuwa Isle - 5000 Coins", player
    ).access_rule = lambda state: state.can_reach(
        "Sala Isle",
        "Region",
        player,
    )

    # magic_fefbe
    # fuwa_isle & powersword & lightblocks_on
    #
    # lightblocks_on = lightswitch = poka
    multiworld.get_location(
        "Fuwa Isle - Magic FEFBE", player
    ).access_rule = lambda state: state.has(
        "Power Sword", player
    )

    # magic_fefd5
    # fuwa_isle & shovel
    multiworld.get_location(
        "Fuwa Isle - Magic FEFD5", player
    ).access_rule = lambda state: state.has(
        "Shovel", player
    )

    # powersword_fefec
    # fuwa_isle & shovel
    multiworld.get_location(
        "Fuwa Isle - Power Sword", player
    ).access_rule = lambda state: state.has(
        "Shovel", player
    )    
    
    # =========================================================
    # FINAL BOSS
    # =========================================================

    multiworld.get_entrance(
        "Enter Final Boss", player
    ).access_rule = lambda state: (
        state.has("Power Sword", player)
        and state.has("Shovel", player)
        and state.has("Sky Bell", player)
        and can_defeat_boss(state, player)
    )
    multiworld.get_location(
        "Defeat Final Boss", player
    ).access_rule = lambda state: True
    
    # Allows access to Puka through the Aqua Gate.
    # This route becomes available once the player has obtained
    # the Aqua Stone, matching the original randomizer logic:
    # aquagate_down = aquastone
    multiworld.get_entrance(
        "Aqua Gate to Puka", player
    ).access_rule = lambda state: state.has(
        "Aqua Stone", player
)
    # Allows the player to return from Hiya to Boa through the Sun Gate.
    # The route becomes available once the player has obtained
    # the Sun Stone, matching the original randomizer logic:
    # sungate_down = boa & sunstone
    multiworld.get_entrance(
        "Hiya to Boa", player
    ).access_rule = lambda state: state.has(
        "Sun Stone", player
    )
