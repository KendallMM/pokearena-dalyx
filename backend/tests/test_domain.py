import pytest

from app.engine import ability_engine as catalog
from app.engine.ability_engine import (
    CARD_IMAGE_SPEC,
    LOCATION_IMAGE_SPEC,
    EvolutionRuleError,
    ImageInfo,
    ImageRequirementError,
    InvalidAbilityError,
    InvalidFieldError,
    ensure_evolution_is_valid,
    escape_like,
    format_card_code,
    normalize_text,
    validate_card_draft,
    validate_image_info,
    validate_image_size,
    validate_location_draft,
    validate_page_limit,
    validate_search_criteria,
)


def card(**kw):
    base = dict(
        name="Pika",
        cost=3,
        power=5,
        card_type="Fuego",
        rarity="Común",
        ability_code="HAB-000",
    )
    base.update(kw)
    return validate_card_draft(**base)


@pytest.mark.parametrize("cost", [0, 10])
def test_card_cost_boundaries_ok(cost):
    assert card(cost=cost).cost == cost


@pytest.mark.parametrize("cost", [-1, 11])
def test_card_cost_out_of_range(cost):
    with pytest.raises(InvalidFieldError) as exc:
        card(cost=cost)
    assert exc.value.field == "cost"


@pytest.mark.parametrize("power", [-20, 20])
def test_card_power_boundaries_ok(power):
    assert card(power=power).power == power


@pytest.mark.parametrize("power", [-21, 21])
def test_card_power_out_of_range(power):
    with pytest.raises(InvalidFieldError):
        card(power=power)


def test_card_name_rules():
    assert card(name="  Pika  ").name == "Pika"
    assert card(name="x" * 100)
    for bad in (None, "", "   ", "x" * 101):
        with pytest.raises(InvalidFieldError) as exc:
            card(name=bad)
        assert exc.value.field == "name"


def test_card_bool_and_none_numbers_rejected():
    for field in ("cost", "power"):
        for bad in (None, True):
            with pytest.raises(InvalidFieldError):
                card(**{field: bad})


def test_card_type_and_rarity_closed_catalogs():
    with pytest.raises(InvalidFieldError):
        card(card_type="Hielo")
    with pytest.raises(InvalidFieldError):
        card(card_type="fuego")  # exacto
    with pytest.raises(InvalidFieldError):
        card(rarity="Mítica")
    for t in catalog.CARD_TYPES:
        assert card(card_type=t)
    for r in catalog.RARITIES:
        assert card(rarity=r)


def test_ability_required():
    for bad in (None, "", "  "):
        with pytest.raises(InvalidAbilityError):
            card(ability_code=bad)
    assert card(ability_code=" hab-005 ").ability_code == "HAB-005"


def test_card_codes():
    assert format_card_code("Fuego", 1) == "PKA-FUE-001"
    assert format_card_code("Agua", 999) == "PKA-AGU-999"
    assert format_card_code("Agua", 1000) == "PKA-AGU-1000"
    prefixes = {format_card_code(t, 1).split("-")[1] for t in catalog.CARD_TYPES}
    assert prefixes == {"FUE", "AGU", "PLA", "ELE", "PSI", "LUC"}


def test_evolution_rules():
    ensure_evolution_is_valid("PKA-FUE-005", None, {})
    ensure_evolution_is_valid("PKA-FUE-005", "PKA-FUE-001", {})
    with pytest.raises(EvolutionRuleError):
        ensure_evolution_is_valid("PKA-FUE-005", "PKA-FUE-005", {})
    # 5 -> 3 y 3 ya apuntaba a 5: ciclo
    with pytest.raises(EvolutionRuleError):
        ensure_evolution_is_valid(
            "PKA-FUE-005", "PKA-FUE-003", {"PKA-FUE-003": "PKA-FUE-005"}
        )
    # ciclo ajeno que no incluye la carta nueva también termina (no se cuelga)
    with pytest.raises(EvolutionRuleError):
        ensure_evolution_is_valid("PKA-FUE-005", "A", {"A": "B", "B": "A"})
    # cadena larga sin ciclo
    ensure_evolution_is_valid("N", "A", {"A": "B", "B": "C"})


@pytest.mark.parametrize(
    "size,ok",
    [(1, True), (5 * 1024 * 1024, True), (5 * 1024 * 1024 + 1, False), (0, False)],
)
def test_image_size(size, ok):
    if ok:
        validate_image_size(size)
    else:
        with pytest.raises(ImageRequirementError):
            validate_image_size(size)


def info(w, h, f="PNG"):
    return ImageInfo(f, w, h)


def requirement(spec, i):
    try:
        validate_image_info(i, spec)
    except ImageRequirementError as exc:
        return exc.details["requirement"]
    return None


def test_card_image_rules():
    assert requirement(CARD_IMAGE_SPEC, info(600, 840)) is None
    assert requirement(CARD_IMAGE_SPEC, info(1000, 1400)) is None
    assert requirement(CARD_IMAGE_SPEC, info(599, 840)) == "min_resolution"
    assert requirement(CARD_IMAGE_SPEC, info(600, 839)) == "min_resolution"
    assert requirement(CARD_IMAGE_SPEC, info(600, 841)) == "ratio"
    assert requirement(CARD_IMAGE_SPEC, info(1400, 1000)) == "ratio"
    assert requirement(CARD_IMAGE_SPEC, info(600, 840, "GIF")) == "format"
    assert requirement(CARD_IMAGE_SPEC, info(6000, 8400)) == "dimensions_too_large"


def test_location_image_rules():
    assert requirement(LOCATION_IMAGE_SPEC, info(800, 600)) is None
    assert requirement(LOCATION_IMAGE_SPEC, info(799, 600)) == "min_resolution"
    assert requirement(LOCATION_IMAGE_SPEC, info(800, 601)) == "ratio"
    assert requirement(LOCATION_IMAGE_SPEC, info(1000, 1200)) == "ratio"


def loc(**kw):
    base = dict(
        name="Bosque",
        description="Denso",
        effect_type=None,
        effect_card_type=None,
        effect_amount=None,
        effect_restricted_turns=None,
        card_limit=4,
        extra_energy_mode="fixed",
        extra_energy_amount=1,
    )
    base.update(kw)
    return validate_location_draft(**base)


def test_location_valid_effects():
    assert loc().effect is None
    bonus = loc(effect_type="type_bonus", effect_card_type="Fuego", effect_amount=-5)
    assert bonus.effect.parameters == {"card_type": "Fuego", "amount": -5}
    cost = loc(effect_type="cost_modifier", effect_amount=5)
    assert cost.effect.parameters == {"amount": 5, "card_type": None}
    cost2 = loc(effect_type="cost_modifier", effect_amount=1, effect_card_type="Agua")
    assert cost2.effect.parameters["card_type"] == "Agua"
    r = loc(effect_type="turn_restriction", effect_restricted_turns=[3, 1, 6])
    assert r.effect.parameters == {"turns": [1, 3, 6]}


@pytest.mark.parametrize(
    "kw,field",
    [
        (dict(effect_type="type_bonus", effect_amount=1), "effect_card_type"),
        (dict(effect_type="type_bonus", effect_card_type="Fuego"), "effect_amount"),
        (
            dict(effect_type="type_bonus", effect_card_type="Fuego", effect_amount=6),
            "effect_amount",
        ),
        (
            dict(effect_type="type_bonus", effect_card_type="Fuego", effect_amount=-6),
            "effect_amount",
        ),
        (
            dict(effect_type="type_bonus", effect_card_type="Hielo", effect_amount=1),
            "effect_card_type",
        ),
        (dict(effect_type="cost_modifier"), "effect_amount"),
        (
            dict(
                effect_type="cost_modifier",
                effect_amount=1,
                effect_restricted_turns=[1],
            ),
            "effect_restricted_turns",
        ),
        (dict(effect_type="turn_restriction"), "effect_restricted_turns"),
        (
            dict(effect_type="turn_restriction", effect_restricted_turns=[0]),
            "effect_restricted_turns",
        ),
        (
            dict(effect_type="turn_restriction", effect_restricted_turns=[7]),
            "effect_restricted_turns",
        ),
        (
            dict(effect_type="turn_restriction", effect_restricted_turns=[2, 2]),
            "effect_restricted_turns",
        ),
        (
            dict(
                effect_type="turn_restriction",
                effect_restricted_turns=[1],
                effect_amount=1,
            ),
            "effect_amount",
        ),
        (
            dict(
                effect_type="turn_restriction",
                effect_restricted_turns=[1],
                effect_card_type="Fuego",
            ),
            "effect_card_type",
        ),
        (dict(effect_type="nope"), "effect_type"),
        (dict(effect_amount=1), "effect_type"),
        (dict(effect_card_type="Fuego"), "effect_type"),
        (dict(effect_restricted_turns=[1]), "effect_type"),
        (dict(card_limit=-1), "card_limit"),
        (dict(card_limit=6), "card_limit"),
        (dict(card_limit=None), "card_limit"),
        (dict(extra_energy_mode="x"), "extra_energy_mode"),
        (dict(extra_energy_mode=None), "extra_energy_mode"),
        (dict(extra_energy_mode="fixed", extra_energy_amount=4), "extra_energy_amount"),
        (
            dict(extra_energy_mode="per_card", extra_energy_amount=3),
            "extra_energy_amount",
        ),
        (dict(extra_energy_amount=-1), "extra_energy_amount"),
        (dict(name=""), "name"),
        (dict(name="x" * 101), "name"),
        (dict(description=""), "description"),
        (dict(description="x" * 256), "description"),
    ],
)
def test_location_invalid(kw, field):
    with pytest.raises(InvalidFieldError) as exc:
        loc(**kw)
    assert exc.value.field == field


def test_location_boundaries():
    assert loc(card_limit=0, extra_energy_amount=0).card_limit == 0
    assert loc(card_limit=5).card_limit == 5
    assert loc(extra_energy_mode="fixed", extra_energy_amount=3)
    assert loc(extra_energy_mode="per_card", extra_energy_amount=2)
    assert loc(description="x" * 255)
    assert loc(
        effect_type="turn_restriction", effect_restricted_turns=[1, 2, 3, 4, 5, 6]
    )


def test_search_criteria():
    c = validate_search_criteria(name="  PIKÁchu ", cost=3, power_min=-2, power_max=4)
    assert c.name_search == "pikachu" and c.cost_min == c.cost_max == 3
    assert validate_search_criteria(code="pka-ele-001").code == "PKA-ELE-001"
    assert validate_search_criteria(name="  ", rarity="").name_search is None
    assert validate_search_criteria().to_dict()["code"] is None


@pytest.mark.parametrize(
    "kw,field",
    [
        (dict(code="XYZ"), "code"),
        (dict(code="PKA-ELE-1"), "code"),
        (dict(cost=11), "cost"),
        (dict(cost_min=-1), "cost_min"),
        (dict(cost_min=5, cost_max=2), "cost_min"),
        (dict(cost=3, cost_min=1), "cost"),
        (dict(power=21), "power"),
        (dict(power_min=3, power_max=-3), "power_min"),
        (dict(card_type="Hielo"), "type"),
        (dict(rarity="x"), "rarity"),
        (dict(ability_code="ABC"), "ability_code"),
        (dict(ability_trigger="x"), "ability_trigger"),
        (dict(ability_effect="x"), "ability_effect"),
        (dict(name="x" * 101), "name"),
    ],
)
def test_search_criteria_invalid(kw, field):
    with pytest.raises(InvalidFieldError) as exc:
        validate_search_criteria(**kw)
    assert exc.value.field == field


@pytest.mark.parametrize(
    "limit,ok",
    [(None, True), (1, True), (50, True), (0, False), (51, False), (-1, False)],
)
def test_page_limit(limit, ok):
    if ok:
        assert 1 <= validate_page_limit(limit) <= 50
    else:
        with pytest.raises(InvalidFieldError):
            validate_page_limit(limit)


def test_text_helpers():
    assert normalize_text("  Pikáchu   ÉLÉCTRICO ") == "pikachu electrico"
    assert escape_like("50%_a\\") == "50\\%\\_a\\\\"
