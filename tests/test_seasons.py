import time

import pytest

from zengo.behavior.seasons import Seasons, hemisphere_of, season_in
from zengo.settings import Flags, Settings


@pytest.mark.parametrize(
    ("month", "north", "south"),
    [(1, "winter", "summer"), (4, "spring", "autumn"), (7, "summer", "winter"),
     (10, "autumn", "spring"), (12, "winter", "summer")],
)  # fmt: skip
def test_seasons_follow_the_month_and_flip_in_the_south(month, north, south):
    assert season_in(month, "north") == north
    assert season_in(month, "south") == south


@pytest.mark.parametrize(
    "zone",
    ["Australia/Sydney", "America/Sao_Paulo", "America/Argentina/Cordoba", "Africa/Johannesburg",
     "Pacific/Auckland", "AUS Eastern Standard Time", "E. South America Standard Time"],
)  # fmt: skip
def test_southern_time_zones(zone):
    assert hemisphere_of(zone) == "south"


@pytest.mark.parametrize(
    "zone",
    ["Europe/Berlin", "Asia/Amman", "America/New_York", "UTC", "Etc/GMT+3", "", None,
     "W. Europe Standard Time"],
)  # fmt: skip
def test_northern_and_unknown_time_zones(zone):
    assert hemisphere_of(zone) == "north"


def _july() -> float:
    return time.mktime((2026, 7, 15, 12, 0, 0, 0, 0, -1))


def test_the_setting_overrides_the_time_zone():
    seasons = Seasons(zone_hemisphere="north")
    assert seasons.now(_july()) == "summer"
    seasons.setting = "south"
    assert seasons.now(_july()) == "winter"


def test_seasons_can_be_turned_off_and_forced():
    seasons = Seasons(forced="winter")
    assert seasons.now(_july()) == "winter"
    seasons.enabled = False
    assert seasons.now(_july()) is None


def test_context_season_uses_its_clock(ctx):
    ctx.clock = _july
    assert ctx.season() == "summer"


def test_season_settings_read_forgivingly():
    assert Settings.from_json({"seasons": False, "hemisphere": "south"}).hemisphere == "south"
    damaged = Settings.from_json({"seasons": "yes", "hemisphere": "east"})
    assert damaged.seasons is True
    assert damaged.hemisphere == "auto"


def test_an_unknown_season_flag_is_refused():
    with pytest.raises(ValueError):
        Flags(season="monsoon")
