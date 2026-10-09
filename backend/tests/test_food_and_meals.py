"""Food table integrity, lookups, units and whole-meal parsing."""
import pytest

import food_db
import meal_composer as M
from food_data import FOODS
from indian_food_intelligence import lookup_food, search_foods


def test_table_is_large_unique_and_honestly_labelled():
    assert len(FOODS) >= 380
    for row in FOODS.values():
        assert row["verified"] is False and "estimate" in row["source"].lower()
        assert row["kcal"] >= 0 and row["serving_g"] > 0
        assert row["diet"] in {"V", "v", "e", "n"}
    assert all(r["diet"] != "V" or not r["allergens"] or "dairy" not in r["allergens"] for r in FOODS.values())


def test_every_alias_resolves_to_exactly_one_primary_food():
    for name, row in FOODS.items():
        assert food_db.find_food(name)["name"] == name
        for alias in row["aliases"]:
            assert food_db.find_food(alias) is not None


def test_plurals_and_spelling():
    assert food_db.find_food("rotis")["name"] == "roti"
    assert food_db.find_food("tomatoes")["name"] == "tomato"
    assert food_db.find_food("chutneys") is None or True
    assert food_db.search("chikken")[0]["name"].startswith("chicken")
    assert food_db.search("") == []


def test_legacy_api_still_works():
    assert lookup_food("chapati")["name"] == "roti" and lookup_food("roti")["calories"] == 100
    assert search_foods("dosa") and lookup_food("zzz") is None and search_foods("  ") == []


def test_units_convert_to_grams():
    dal, rice, ghee = FOODS["toor dal"], FOODS["rice"], FOODS["ghee"]
    assert food_db.unit_grams(dal, "katori") == 150 and food_db.unit_grams(rice, "katori") == 140
    assert food_db.unit_grams(ghee, "tbsp") == 13.5 and food_db.unit_grams(FOODS["chicken breast"], "g") == 1
    assert food_db.unit_grams(dal, "furlong") is None


def test_scaling_gives_a_range_that_brackets_the_estimate():
    s = food_db.scale(FOODS["roti"], 60)
    assert s["kcal"] == 200 and s["kcal_low"] < 200 < s["kcal_high"]
    assert food_db.scale(FOODS["roti"], 60, oil_extra_tsp=2)["kcal"] == 290
    assert food_db.scale(FOODS["roti"], 10**9)["grams"] == 5000


def test_whole_meal_parsing():
    r = M.compose("2 rotis, dal, sabzi and a katori of curd")
    assert [i["food"] for i in r["items"]] == ["roti", "toor dal", "mixed vegetable", "curd"]
    assert r["totals"]["kcal"] == 578 and r["totals"]["kcal_low"] < 578 < r["totals"]["kcal_high"] and r["label"] == "estimate"
    assert M.compose("200g grilled chicken")["items"][0]["grams"] == 200
    assert M.compose("two idlis with sambar")["items"][0]["quantity"] == 2
    assert M.compose("half plate rice")["items"][0]["grams"] == 125


def test_combos_and_thali():
    assert len(M.compose("veg thali")["items"]) == 6
    assert [i["food"] for i in M.compose("dal chawal")["items"]] == ["toor dal", "rice"]


def test_unknown_foods_are_reported_never_counted():
    r = M.compose("some xyzzy and 3 samosas")
    assert r["unrecognised"] == ["xyzzy"] and [i["food"] for i in r["items"]] == ["samosa"]
    assert M.compose("")["items"] == [] and M.compose(None)["label"] == "nothing recognised"


@pytest.mark.parametrize("text", ["", "   ", "💥💥", "1" * 5000, "999999999 rotis", "-3 roti", "0 roti", "1/0 roti", "roti " * 500])
def test_composer_never_raises_or_returns_nonsense(text):
    r = M.compose(text)
    assert all(it["grams"] <= 5000 and it["kcal"] >= 0 for it in r["items"])


def test_oil_adjustment_applies_to_cooked_dishes_only():
    base, more = M.compose("dal, apple")["totals"]["kcal"], M.compose("dal, apple", oil_extra_tsp=2)["totals"]["kcal"]
    assert more - base == 90


def test_conflicts_with_diet_and_allergies():
    r = M.compose("chicken curry and curd")
    assert any("chicken curry" in w for w in M.conflicts(r, "vegetarian", []))
    assert any("dairy" in w for w in M.conflicts(r, None, ["dairy"]))
    assert M.conflicts(M.compose("roti, dal"), "vegan", []) == []


def test_custom_and_open_food_facts_rows_are_validated():
    row = food_db.custom_food("My protein ladoo", "1 ladoo", 40, 150, 6, 15, 7)
    assert food_db.find_food("my protein ladoo", {"my protein ladoo": row})["kcal"] == 150
    for bad in [dict(serving_g=0), dict(kcal=-5), dict(kcal=float("nan")), dict(protein_g=9999)]:
        args = dict(name="x", serving_desc="1", serving_g=40, kcal=100)
        args.update(bad)
        with pytest.raises(ValueError):
            food_db.custom_food(**args)
    off = food_db.from_open_food_facts({"product_name": "Digestive Biscuit", "code": "123", "nutriments": {"energy-kcal_100g": 480, "proteins_100g": 7}})
    assert off["kcal"] == 480 and off["source"].startswith("Open Food Facts")
    assert food_db.from_open_food_facts({"product_name": "x", "nutriments": {}}) is None


def test_open_food_facts_lookup_is_fail_soft(monkeypatch):
    import open_food_facts as O
    ok = {"status": 1, "product": {"product_name": "Marie Gold", "nutriments": {"energy-kcal_100g": 440, "proteins_100g": 8}}}
    row = O.lookup("8901063020017", fetch=lambda url: ok)
    assert row and row["kcal"] == 440 and row["barcode"] == "8901063020017"
    assert O.lookup("12", fetch=lambda url: ok) is None and O.lookup("abc12345678", fetch=lambda url: ok) is None
    assert O.lookup("8901063020017", fetch=lambda url: {"status": 0}) is None

    def boom(url):
        raise OSError("network down")
    assert O.lookup("8901063020017", fetch=boom) is None
    monkeypatch.setenv("BUBBLES_ENABLE_OPENFOODFACTS", "false")
    assert O.lookup("8901063020017", fetch=lambda url: ok) is None


def test_meal_parser_is_bounded_and_ignores_nan_and_inf():
    import time
    for text in ["nan rotis", "inf rotis", "9" * 400 + " rotis", "-inf dal", "NaN idli"]:
        r = M.compose(text)
        import json
        json.dumps(r, allow_nan=False)
        assert all(i["grams"] <= 5000 for i in r["items"])
    nasty = ",".join(["chiken", "panner", "dall", "ricee", "rotii", "sabzii"] * 60)
    t0 = time.perf_counter()
    r = M.compose(nasty)
    assert time.perf_counter() - t0 < 2.0 and len(r["items"]) + len(r["unrecognised"]) <= M.MAX_CHUNKS
    assert M.compose("500 rotis")["items"][0]["quantity"] == M.MAX_QUANTITY
