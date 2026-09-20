"""Tests gegen echte Mitschnitte eines SYR Safe-T+ Connect.

Die Dateien in ``fixtures/`` sind die rohen HTTP-Nachrichten aus einem
FRITZ!Box-Mitschnitt. An den TCP-Segmentgrenzen fehlen dort vereinzelt Bytes,
deshalb wird nicht auf die ganze Nachricht verglichen, sondern auf Werte, die
in allen vier Mitschnitten übereinstimmen.
"""

import pathlib

import pytest

import codec
import protocol

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
REQUESTS = sorted(FIXTURES.glob("syr_*_req.bin"))
RESPONSES = sorted(FIXTURES.glob("syr_*_resp.bin"))

SERIAL = "68SPAAEW"
MAC = "70:B3:D5:19:4C:B4"


def read(path: pathlib.Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace")


@pytest.mark.parametrize("path", REQUESTS, ids=lambda p: p.stem)
def test_geraetemeldung_wird_lesbar(path: pathlib.Path) -> None:
    payload, _cp = codec.extract_payload(read(path))
    decoded = codec.decode(payload)

    assert decoded.startswith("<d><")
    assert SERIAL in decoded
    assert MAC in decoded


@pytest.mark.parametrize("path", RESPONSES, ids=lambda p: p.stem)
def test_cloudantwort_wird_lesbar(path: pathlib.Path) -> None:
    payload, _cp = codec.extract_payload(read(path))
    decoded = codec.decode(payload)

    assert decoded.startswith("<sc>")
    assert 'rt="10"' in decoded


def test_werte_aus_einer_meldung() -> None:
    # 59106 ist der Mitschnitt, dessen Druckwert nicht in eine Lücke fällt.
    payload, _cp = codec.extract_payload(read(FIXTURES / "syr_59106_req.bin"))
    message = protocol.parse_device_message(codec.decode(payload))

    assert message.serial == SERIAL
    assert message.mac == MAC
    assert message.firmware == "1.85"
    assert protocol.parse_pressure_mbar(message.values["BAR"]) == 2529
    assert protocol.parse_volume_liters(message.values["VOL"]) == 951727
    assert protocol.parse_voltage(message.values["NET"]) == 6.05
    assert message.values["AB"] == "1"


def test_unveraendert_uebertragene_zeichen() -> None:
    # Bei Schlüssel 0x1A ergibt jedes "e" nach dem XOR 0x7F und wird deshalb
    # unverändert übertragen. Ohne Sonderbehandlung stünde hier "gtSRN".
    payload, _cp = codec.extract_payload(read(FIXTURES / "syr_62601_req.bin"))
    decoded = codec.decode(payload)

    assert codec.find_key(payload) == 0x1A
    assert "getSRN" in decoded
    assert "" not in decoded


@pytest.mark.parametrize("key", [0x00, 0x14, 0x16, 0x1A, 0x1E, 0x7F])
def test_hin_und_zurueck(key: int) -> None:
    original = '<d><c n="1:getBAR" v="2529 mbar"/><c n="1:getAB" v="1"/></d>'
    assert codec.decode(codec.encode(original, key), key) == original


def test_schluessel_wird_ohne_hinweis_gefunden() -> None:
    original = '<d><c n="1:getSRN" v="68SPAAEW"/></d>'
    # Schlüssel ab 0x80 kämen mit ASCII-Klartext nie vor und könnten
    # zufällig auf einem Ersatzzeichen landen.
    for key in range(0x80):
        assert codec.find_key(codec.encode(original, key)) == key


def test_antwort_ueberlebt_die_kodierung() -> None:
    inner = protocol.build_cloud_response(commands={"AB": "2"})

    for key in (0x14, 0x16, 0x1A, 0x1E):
        assert codec.decode(codec.encode(inner, key), key) == inner


def test_schaltbefehl_landet_in_der_antwort() -> None:
    inner = protocol.build_cloud_response(commands={"AB": "2"}, poll_interval=10)

    assert '<c n="1:setAB" v="2" />' in inner
    assert '<c n="1:getBAR" v="" />' in inner
    assert inner.endswith('<ct rt="10" /></sc>')
