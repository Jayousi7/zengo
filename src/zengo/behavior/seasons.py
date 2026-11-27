"""The time of year, from your computer's date and clock only: no internet.

Seasons go by the month, flipped for the southern hemisphere. Which hemisphere
you're in is worked out from your computer's time zone (``Australia/Sydney``,
``America/Sao_Paulo``...), or set by hand in his settings. Zones near the
equator count as northern unless they're clearly south of it; seasons hardly
show there anyway.

Pure Python: no Qt. The Qt side reads the time zone's name and hands it in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

SEASONS = ("winter", "spring", "summer", "autumn")

HEMISPHERES = ("auto", "north", "south")
"""Your setting: ``"auto"`` goes by the time zone."""

_NORTHERN_SEASON = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}  # fmt: skip

_OPPOSITE = {"winter": "summer", "summer": "winter", "spring": "autumn", "autumn": "spring"}

_SOUTHERN_PREFIXES = ("Australia/", "Antarctica/", "America/Argentina/")
"""IANA zones south of the equator, by prefix. (Offsets such as ``Etc/GMT+3``
aren't places, so they count as northern.)"""

_SOUTHERN_ZONES = frozenset(
    {
        # The Americas
        "America/Sao_Paulo", "America/Buenos_Aires", "America/Santiago",
        "America/Montevideo", "America/Asuncion", "America/La_Paz", "America/Lima",
        "America/Punta_Arenas", "America/Cordoba", "America/Mendoza",
        "America/Bahia", "America/Recife", "America/Fortaleza", "America/Maceio",
        "America/Belem", "America/Araguaina", "America/Cuiaba", "America/Campo_Grande",
        "America/Porto_Velho", "America/Rio_Branco", "America/Eirunepe",
        "America/Noronha", "America/Santarem", "America/Manaus",
        "Brazil/East", "Chile/Continental", "Chile/EasterIsland", "Pacific/Easter",
        # Africa and the Indian Ocean
        "Africa/Johannesburg", "Africa/Maputo", "Africa/Harare", "Africa/Lusaka",
        "Africa/Windhoek", "Africa/Gaborone", "Africa/Maseru", "Africa/Mbabane",
        "Africa/Blantyre", "Africa/Lubumbashi", "Africa/Luanda", "Africa/Kinshasa",
        "Africa/Dar_es_Salaam", "Africa/Kigali", "Africa/Bujumbura",
        "Indian/Antananarivo", "Indian/Mauritius", "Indian/Reunion",
        "Indian/Mayotte", "Indian/Comoro",
        # Asia and the Pacific
        "Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura", "Asia/Dili",
        "Pacific/Auckland", "Pacific/Chatham", "Pacific/Fiji", "Pacific/Tongatapu",
        "Pacific/Apia", "Pacific/Noumea", "Pacific/Port_Moresby", "Pacific/Efate",
        "Pacific/Guadalcanal", "Pacific/Norfolk", "Pacific/Tahiti", "Pacific/Rarotonga",
        "Pacific/Pago_Pago", "Pacific/Niue", "Pacific/Fakaofo", "Pacific/Funafuti",
        "Pacific/Wallis", "Pacific/Bougainville", "Pacific/Marquesas", "Pacific/Gambier",
        "Pacific/Pitcairn", "NZ", "NZ-CHAT",
    }
)  # fmt: skip

_SOUTHERN_WINDOWS_ZONES = frozenset(
    {
        "AUS Eastern Standard Time", "AUS Central Standard Time",
        "Cen. Australia Standard Time", "E. Australia Standard Time",
        "W. Australia Standard Time", "Tasmania Standard Time",
        "Aus Central W. Standard Time", "Lord Howe Standard Time",
        "New Zealand Standard Time", "Chatham Islands Standard Time",
        "Fiji Standard Time", "Tonga Standard Time", "Samoa Standard Time",
        "Norfolk Standard Time", "South Africa Standard Time", "Namibia Standard Time",
        "Mauritius Standard Time", "E. South America Standard Time",
        "Argentina Standard Time", "Pacific SA Standard Time", "Paraguay Standard Time",
        "Montevideo Standard Time", "Magallanes Standard Time", "Tocantins Standard Time",
        "Bahia Standard Time", "Central Brazilian Standard Time",
        "Easter Island Standard Time",
    }
)  # fmt: skip
"""Windows' own zone names, in case the system gives one of those instead."""


def hemisphere_of(zone: str | None) -> str:
    """``"south"`` for a time zone south of the equator, else ``"north"``."""
    if not zone:
        return "north"
    zone = zone.strip()
    if zone in _SOUTHERN_ZONES or zone in _SOUTHERN_WINDOWS_ZONES:
        return "south"
    if zone.startswith(_SOUTHERN_PREFIXES):
        return "south"
    return "north"


def season_in(month: int, hemisphere: str) -> str:
    """The season in ``month`` (1 to 12) in ``hemisphere``."""
    northern = _NORTHERN_SEASON[month]
    return _OPPOSITE[northern] if hemisphere == "south" else northern


@dataclass
class Seasons:
    """What time of year it is for him, and whether he shows it."""

    zone_hemisphere: str = "north"
    """The hemisphere the time zone says."""
    setting: str = "auto"
    """Your choice: a key of :data:`HEMISPHERES`."""
    enabled: bool = True
    """Your setting: outfits and seasonal effects on at all."""
    forced: str | None = None
    """A season given with ``--season``, to try it out whatever the date."""

    @property
    def hemisphere(self) -> str:
        return self.zone_hemisphere if self.setting == "auto" else self.setting

    def now(self, wall_clock: float) -> str | None:
        """The season at ``wall_clock`` (seconds since the epoch), or ``None`` when
        they're turned off."""
        if not self.enabled:
            return None
        if self.forced is not None:
            return self.forced
        return season_in(time.localtime(wall_clock).tm_mon, self.hemisphere)
