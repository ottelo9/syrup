"""Ver- und Entschluesselung der SYR-Connect-Nutzlast.

Das Geraet schickt seine Daten als Klartext-XML, das so verschleiert wird:

    1. XOR mit einem Ein-Byte-Schluessel, der pro Nachricht wechselt
    2. acht Bytes, die im form-urlencodeten Rumpf oder im XML-Attribut stoeren
       wuerden, werden ersetzt (siehe unten)
    3. UTF-8

Der Schluessel steht nirgends in der Nachricht. Er laesst sich aber
zurueckrechnen, weil die Nutzlast immer mit ``<d>`` (Geraet) bzw. ``<sc>``
(Cloud) beginnt.

Sonderfall 0x7F: ergibt ein Zeichen nach dem XOR das Steuerzeichen DEL, wird
statt dessen das **unveraenderte Zeichen** uebertragen. Das ist eindeutig
umkehrbar, weil 0x7F im Klartext nicht vorkommt: faellt beim Entschluesseln
0x7F an, war das gesendete Byte das Original. Bei Schluessel 0x1A trifft das
zum Beispiel jedes "e", weshalb ein naiver Decoder dort ``g<DEL>tSRN`` statt
``getSRN`` sieht.

Das Verfahren setzt voraus, dass Klartext und Schluessel unter 0x80 bleiben --
sonst koennte ein Ergebnisbyte zufaellig auf einem der Ersatzzeichen landen.
Fuer die Firmware trifft das zu (ASCII, Schluessel um 0x14 bis 0x1E).
"""

from __future__ import annotations

import re

# Byte nach dem XOR -> Ersatzzeichen, das uebertragen wird.
ESCAPES: dict[int, str] = {
    0x22: "\u00c4",  # "  -> AE
    0x25: "\u00e4",  # %  -> ae
    0x26: "\u00dc",  # &  -> UE
    0x27: "\u00f6",  # '  -> oe
    0x2B: "\u20ac",  # +  -> Euro
    0x3C: "\u00d6",  # <  -> OE
    0x3E: "\u00fc",  # >  -> ue
}
UNESCAPES: dict[str, int] = {v: k for k, v in ESCAPES.items()}

# Ergibt das XOR dieses Byte, wird das Zeichen unveraendert uebertragen.
PLAIN_BYTE = 0x7F

_PREFIXES = ("<d><", "<sc>")


class DecodeError(ValueError):
    """Die Nutzlast liess sich nicht entschluesseln."""


def _to_cipher(payload: str) -> list[int]:
    """Ersatzzeichen aufloesen, Ergebnis ist der reine Cipher-Bytestrom."""
    return [UNESCAPES.get(ch, ord(ch) & 0xFF) for ch in payload]


def _decode_cipher(cipher: list[int], key: int) -> str:
    out = []
    for byte in cipher:
        value = byte ^ key
        # 0x7F markiert ein unveraendert uebertragenes Zeichen.
        out.append(chr(byte) if value == PLAIN_BYTE else chr(value))
    return "".join(out)


def find_key(payload: str) -> int:
    """Den Schluessel einer Nachricht ueber ihren bekannten Anfang bestimmen."""
    cipher = _to_cipher(payload)
    if len(cipher) < 4:
        raise DecodeError("Nutzlast zu kurz")
    for key in range(256):
        if _decode_cipher(cipher[:4], key).startswith(_PREFIXES):
            return key
    raise DecodeError("kein passender Schluessel gefunden")


def decode(payload: str, key: int | None = None) -> str:
    """Nutzlast in Klartext-XML zurueckverwandeln."""
    cipher = _to_cipher(payload)
    if key is None:
        key = find_key(payload)
    return _decode_cipher(cipher, key)


def encode(xml: str, key: int) -> str:
    """Klartext-XML in die uebertragene Form bringen."""
    out = []
    for char in xml:
        byte = (ord(char) ^ key) & 0xFF
        if byte == PLAIN_BYTE:
            out.append(char)
        else:
            out.append(ESCAPES.get(byte) or chr(byte))
    return "".join(out)


_DAT_RE = re.compile(r'dat\s+v="([^"]*)"')
_CP_RE = re.compile(r'cp\s+v="([^"]*)"')


def extract_payload(body: str) -> tuple[str, str]:
    """``dat``- und ``cp``-Attribut aus einem Nachrichtenrumpf holen.

    Erwartet wird ``xml=<sc><cp v="..."/><dat v="..."/></sc>``; das
    ``xml=``-Praefix darf fehlen.
    """
    dat = _DAT_RE.search(body)
    if not dat:
        raise DecodeError("kein dat-Attribut im Rumpf")
    cp = _CP_RE.search(body)
    return dat.group(1), cp.group(1) if cp else ""


def build_body(inner_xml: str, key: int, cp: str) -> str:
    """Einen Antwortrumpf bauen, wie ihn die Cloud schickt."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<sc>\n"
        f'  <cp v="{cp}" />\n'
        f'  <dat v="{encode(inner_xml, key)}" />\n'
        "</sc>"
    )
