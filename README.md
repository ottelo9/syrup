# SYRUP

**SY**R **R**eversed **U**nclouded **P**rotocol – eine Home-Assistant-Integration,
die einen **SYR Safe-T+ Connect** Leckageschutz ohne Herstellercloud einbindet.

Das Gerät hat keine lokale API: Port 5333, über den die größere
*SafeTech Connect* ihre JSON-Schnittstelle anbietet, ist beim Safe-T+
geschlossen, und der Webserver auf Port 80 liefert auf jeden Pfad eine leere
Antwort. An die Daten kommt man trotzdem, auf zwei Wegen:

1. **Über das Netzwerk:** Das Gerät funkt im 10-Sekunden-Takt unverschlüsselt
   an `iot1.syrconnect.de`. SYRUP stellt genau diesen Endpunkt in Home
   Assistant bereit. Zeigt `iot1.syrconnect.de` im lokalen Netz auf deine
   HA-Instanz, landen die Meldungen hier statt in der Cloud.
2. **Über den RS-485-Servicebus:** Ein ESP32 mit Tasmota TinyC hört an der
   Servicebuchse des Geräts mit. Das braucht kein DNS und keinen Proxy – siehe
   [RS-485 mit Tasmota TinyC](#rs-485-mit-tasmota-tinyc).

Wie die Nutzlast aufgebaut und verschleiert ist, steht in
[docs/protokoll.md](docs/protokoll.md).

## Stand

Codec und Protokollauswertung sind gegen echte Mitschnitte geprüft und durch
die Testsuite abgedeckt (`pytest`, 19 Tests). Der Home-Assistant-Teil –
Config-Flow, Entitäten, HTTP-View – ist **noch nicht am lebenden Gerät
gelaufen**. Insbesondere:

* Ob das Gerät `set`-Befehle aus der Antwort annimmt, ist **nicht
  verifiziert** – das Ventil lässt sich also möglicherweise nicht schalten.
* Ob das Gerät die Prüfsumme `cs` einer Antwort prüft, ist offen.
* Der Leckageschutz selbst arbeitet autark im Gerät. Ihn beeinträchtigt
  weder die Umleitung noch ein Ausfall von Home Assistant.

## Einrichten

### 1. Integration installieren

In HACS unter *Benutzerdefinierte Repositories* die URL https://github.com/ottelo9/syrup als Typ **Integration** hinzufügen, installieren, Home Assistant
neu starten. Alternativ `custom_components/syrup` nach `<config>/custom_components/syrup` kopieren.

Danach unter *Einstellungen → Geräte & Dienste → Integration hinzufügen*
nach **SYRUP** suchen und die Seriennummer der Box eintragen (steht in der
SYR-App, oder im Feld `getSRN` eines Mitschnitts).

### 2. Port 80 auf Home Assistant umbiegen

Das SYR Gerät kommuniziert auf **Port 80**, Home Assistant auf 8123, deshalb wird eine der folgenden Brücken wird gebraucht:

* **Reverse Proxy** (empfohlen, wenn ohnehin einer läuft). In nginx:

  ```nginx
  location /WebServices/ {
      proxy_pass http://homeassistant.local:8123;
  }
  ```

* **Home Assistant direkt auf Port 80**, in `configuration.yaml`:

  ```yaml
  http:
    server_port: 80
  ```

  Damit wandert allerdings die gesamte Oberfläche auf Port 80.

* **Portweiterleitung auf dem HA-Host**, zum Beispiel
  `iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8123`.

### 3. DNS umbiegen

`iot1.syrconnect.de` muss im Heimnetz auf die Adresse aus Schritt 2 zeigen.
Die FRITZ!Box kann das selbst nicht – sie kennt keine eigenen Host-Einträge.
Also einen lokalen DNS-Server (Pi-hole, AdGuard Home, dnsmasq) mit einem
entsprechenden Eintrag betreiben und ihn unter *Heimnetz → Netzwerk →
Netzwerkeinstellungen → IPv4-Konfiguration → Lokaler DNS-Server* eintragen.

### 4. Weiterleitung entscheiden

Im Einrichtungsdialog steht `relay_url` standardmäßig auf der echten Cloud.
Damit reicht SYRUP jede Meldung weiter und gibt die Cloud-Antwort ans Gerät
zurück: **SYR-App und Cloud funktionieren normal weiter**, SYRUP liest nur
mit. Nur wenn ein Schaltbefehl ansteht, antwortet SYRUP selbst.

Feld leeren = reiner Inselbetrieb, die Cloud sieht das Gerät dann nicht mehr.

## Entitäten

| Entität | Quelle | Anmerkung |
|---------|--------|-----------|
| Wasserdruck | `getBAR` | mbar |
| Gesamtvolumen | `getVOL` | Liter, `total_increasing` |
| Laufende Entnahme | `getAVO` | mL |
| Versorgungsspannung | `getNET` | V, Diagnose |
| Alarm | `getALA` | `FF` = kein Alarm |
| Alarmcode / Alarmverlauf / Wartungsdatum | `getALA`, `getALM`, `getSRV` | Diagnose |
| Absperrventil | `getAB` / `setAB` | Schalten unverifiziert |

## Verwandte Geräte

Die Control-Box stammt nicht von SYR: der User-Agent lautet
`Husty Control-Box`, der Firmware-Update-Pfad zeigt auf `husty.pl`. Das
Protokoll dürfte deshalb auch in Geräten anderer Marken stecken. Als
baugleich beziehungsweise verwandt gelten unter anderem **Ditech**,
**CONEL**, **Sanibel**, **concept** und der **Hansgrohe Pontos Base**.
Getestet ist davon nichts – Rückmeldungen willkommen.

## RS-485 mit Tasmota TinyC

Die Alternative ohne DNS-Umleitung und ohne Proxy: Die WLAN-Control-Box fragt
die Werte im Gerät über einen internen RS-485-Bus ab, und dieser Bus liegt an
der Servicebuchse an. `tinyc/syr_rs485.tc` hört dort **passiv** mit – es sendet
nichts, die SYR-App und die Cloud laufen unverändert weiter.

**Stand:** in der JS-VM des TinyC-Compilers gegen simulierten Busverkehr
getestet, am echten Gerät noch nicht.

### Bus

* RJ10-Buchse (4P4C) an der Unterseite, RS-485 auf den **beiden mittleren
  Pins**. Die äußeren Pins sind nicht dokumentiert – erst messen, nicht blind
  anklemmen.
* 19200 Baud, 8N1, Klartext-ASCII. Anfrage `CR LF ESC "1:" getBAR CR LF`,
  Antwort nur der Wert, z. B. `2529 mbar CR`. Das `1:` ist dasselbe Präfix wie
  in der Cloud-Nutzlast – die Control-Box reicht die Cloud-Befehle auf den Bus
  durch.
* Die Control-Box fragt im 10-Sekunden-Takt nur, solange sie mit der Cloud
  verbunden ist. Ohne Cloud fragt sie nur noch alle paar Minuten den Gerätetyp ab.

### Hardware

Ein RS-485-Transceiver für 3,3 V, fest auf **nur Empfangen** verdrahtet – so
kann die Schaltung elektrisch nicht auf den Bus senden, und A/B dürfen beim
Ausprobieren der Polarität vertauscht werden. Standard-Pinbelegung, z. B.
MAX3485 (SO-8) oder THVD1410 (VSSOP-8):

| Pin | Signal | Anschluss |
|-----|--------|-----------|
| 1 | RO | freier GPIO am ESP32 |
| 2 | /RE | GND |
| 3 | DE | GND |
| 4 | DI | GND |
| 5 | GND | GND |
| 6 | A | Bus A |
| 7 | B | Bus B |
| 8 | VCC | 3,3 V, 100 nF gegen GND |

A/B über ein verdrilltes Adernpaar führen. **Keinen** 120-Ω-Abschluss setzen –
das Kabel ist nur ein Abzweig des bestehenden Busses.

### Firmware

Gebraucht wird Tasmota mit TinyC **ab Version 1.6.67** (ABI 31, wegen
`serialReadArray`). Fertige Images gibt es in meinem Repository
[tasmota-sml-images](https://github.com/ottelo9/tasmota-sml-images) – dort die
Variante **`_tc`** für den jeweiligen ESP32 nehmen, nicht `_tas`.

Das Programm braucht einen freien Hardware-UART und läuft in einem eigenen
Slot, neben einem vorhandenen SML-Programm zum Beispiel.

### Einrichten

1. `tinyc/syr_rs485.tcb` in einen freien Slot laden.
2. In der Konsole `SyrPin <gpio>` – den RX-Pin. Er wird gespeichert.
3. Zum ersten Test `SyrRaw 2`: zeigt die Rohbytes im Log, Steuerzeichen als
   `[0D]`, `[1B]`. Nur Kauderwelsch heißt: A und B tauschen. Danach `SyrRaw 0`.
4. `Syr` allein zeigt den Status; `"Uart":-1` heißt, es war kein Hardware-UART
   mehr frei.

Die Werte erscheinen als Zeilen auf der Tasmota-Hauptseite und in der
Telemetrie (Takt: `TelePeriod`):

```json
"SYR":{"Alter":3,"Druck":2.529,"Entnahme":50,"Volumen":951.727,"Ventil":1,"Alarm":"FF","Spannung":6.05}
```

Druck in bar, Entnahme in mL, Volumen in m³, Spannung in V, `Alter` = Sekunden
seit dem letzten Wert. Die Schlüssel sind absichtlich deutsch: die
Tasmota-Discovery in Home Assistant würde `Pressure` als hPa deuten.

## Werkzeuge

`tools/Decode-SyrCapture.ps1` liest einen FRITZ!Box-Mitschnitt (`.eth`,
aufzeichnen unter `http://fritz.box/html/capture.html`) und gibt die
Kommunikation im Klartext aus:

```powershell
.\tools\Decode-SyrCapture.ps1 -Path .\mitschnitt.eth
```

Das Skript versteht AVMs "modified pcap" samt PPPoE-Rahmen und braucht weder
Wireshark noch Python.

## Hinweis zu den Testdaten

`tests/fixtures/` enthält echte Mitschnitte inklusive Seriennummer und
MAC-Adresse des Geräts. Vor einer Veröffentlichung des Repositories
entweder anonymisieren oder entfernen.

## Lizenz

MIT
