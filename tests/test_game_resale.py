"""Game resale — platform-aware baselines + a PriceCharting price-check link."""
from mediahound.resale import estimate


def test_game_resale_adds_pricecharting_link():
    r = estimate("The Witcher 3", 2015, "PC", 9.3, media_type="game")
    assert r["price_check_label"] == "PriceCharting"
    assert "pricecharting.com" in r["price_check_url"]
    assert "Witcher" in r["price_check_url"]
    assert r["sold_listings_url"]                          # eBay sold link still present


def test_game_platform_baselines_differ():
    # Switch holds value; PC physical resale is low → Switch estimate > PC estimate
    switch = estimate("Game A", 2020, "Switch", None, media_type="game")["mid"]
    pc = estimate("Game A", 2020, "PC", None, media_type="game")["mid"]
    assert switch > pc


def test_retro_games_appreciate():
    # a 1990 retro cart is worth more than a brand-new disc of the same base
    retro = estimate("Old Cart", 1990, "Retro", None, media_type="game")["mid"]
    modern = estimate("New Disc", 2022, "PS4", None, media_type="game")["mid"]
    assert retro >= modern


def test_platform_value_implies_game_even_without_media_type():
    # a "Switch" format alone is enough to treat it as a game (price-check link appears)
    r = estimate("Zelda", 2017, "Switch", 9.7)
    assert "price_check_url" in r


def test_non_game_has_no_price_check():
    r = estimate("Some Movie", 2001, "DVD", 8.0)
    assert "price_check_url" not in r
    movie_pc = estimate("A Book", 2010, "Paperback", 7.0, media_type="book")
    assert "price_check_url" not in movie_pc


def test_pc_platform_link_omits_pc_keyword():
    # "PC" is noise in a PriceCharting query (it's console-keyed) → not appended
    r = estimate("Half-Life", 2004, "PC", 9.0, media_type="game")
    assert "PC" not in r["price_check_url"].split("q=")[1]
