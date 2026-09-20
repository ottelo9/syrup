"""Auswertung der entschlüsselten SYR-Connect-Nachrichten."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Parameter, die die Cloud beim Gerät abfragt. Die Liste stammt aus einer
# mitgeschnittenen Cloud-Antwort und ist damit die des Herstellers.
KNOWN_PARAMS: tuple[str, ...] = (
    "SRN", "VER", "71", "AB", "ALA", "ALM", "AVO", "BAR", "BAT", "BLT",
    "BSA", "BSI", "BUZ", "CEL", "CNO", "DBD", "DBT", "DCM", "DMA", "DOM",
    "DPL", "DRP", "DST", "DTC", "EXI", "EXT", "FLL", "INT", "LE", "LNG",
    "NET", "NPS", "REL", "SRV", "T1", "T2", "TBS", "TC", "TMP", "TO",
    "TPA", "TYP", "UL", "UNI", "VLV", "VOL",
)

# <c n="1:getSRN" v="68SPAAEW"/> -- der Verb-Teil kann durch den
# Firmware-Fehler verstümmelt sein ("gtSRN", "etSRN", "stADM").
_CMD_RE = re.compile(r'<c\s+n="(?P<chan>\d+):(?P<verb>[a-z]{0,3})(?P<param>[A-Z0-9]+)"\s+v="(?P<value>[^"]*)"')
_INFO_RE = re.compile(r'<ci?\s+m="(?P<mac>[^"]*)"\s+f="(?P<fw>[^"]*)"\s+b="(?P<b>[^"]*)"')


@dataclass
class DeviceMessage:
    """Was ein Gerät in einer Nachricht berichtet."""

    channel: str = "1"
    values: dict[str, str] = field(default_factory=dict)
    mac: str | None = None
    firmware: str | None = None
    board: str | None = None

    @property
    def serial(self) -> str | None:
        return self.values.get("SRN")


def parse_device_message(xml: str) -> DeviceMessage:
    """Entschlüsseltes Geräte-XML in Werte zerlegen.

    Der Rumpf besteht aus mehreren Wurzelelementen (``<d>``, ``<ci>``,
    ``<cs>``) und ist damit kein gültiges XML-Dokument -- deshalb wird er
    mit regulären Ausdrücken zerlegt und nicht mit einem Parser.
    """
    msg = DeviceMessage()
    for match in _CMD_RE.finditer(xml):
        msg.channel = match.group("chan")
        verb = match.group("verb")
        if verb.startswith(("s", "c")):
            continue  # setADM/clrADM sind Quittungen, keine Messwerte
        msg.values[match.group("param")] = match.group("value")
    if info := _INFO_RE.search(xml):
        msg.mac = info.group("mac")
        msg.firmware = info.group("fw")
        msg.board = info.group("b")
    return msg


def build_cloud_response(
    channel: str = "1",
    commands: dict[str, str] | None = None,
    poll_interval: int = 10,
) -> str:
    """Die Antwort bauen, die das Gerät erwartet.

    Die Cloud schickt eine Liste leerer ``get``-Felder -- das ist die Abfrage
    für den nächsten Durchlauf. Ein Feld mit ``set`` und einem Wert ist ein
    Schaltbefehl.

    Hinweis: dass das Gerät ``set``-Befehle auf diesem Weg annimmt, ist aus
    dem Aufbau der Antwort abgeleitet und noch nicht am Gerät verifiziert.
    """
    parts = ['<sc><d><c n="%s:setADM" v="(2)f" />' % channel]
    for param in KNOWN_PARAMS:
        value = (commands or {}).get(param, "")
        verb = "set" if value else "get"
        parts.append(f'<c n="{channel}:{verb}{param}" v="{value}" />')
    parts.append(f'<c n="{channel}:clrADM" v="" />')
    parts.append(f'</d><ct rt="{poll_interval}" /></sc>')
    return "".join(parts)


def parse_int(value: str | None) -> int | None:
    """Führende Ziffern aus einem Wert wie ``2529 mbar`` holen."""
    if not value:
        return None
    if match := re.search(r"-?\d+", value):
        return int(match.group())
    return None


def parse_pressure_mbar(value: str | None) -> int | None:
    """``2529 mbar`` -> 2529."""
    return parse_int(value)


def parse_volume_liters(value: str | None) -> int | None:
    """``Vol[L]951727`` -> 951727."""
    if not value:
        return None
    return parse_int(value.split("]")[-1])


def parse_volume_ml(value: str | None) -> int | None:
    """``0mL`` -> 0."""
    return parse_int(value)


def parse_voltage(value: str | None) -> float | None:
    """``ADC:933 6,05V`` -> 6.05."""
    if not value:
        return None
    if match := re.search(r"(\d+),(\d+)\s*V", value):
        return float(f"{match.group(1)}.{match.group(2)}")
    return None
