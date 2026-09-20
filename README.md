# SYRUP

**SY**R **R**eversed **U**nclouded **P**rotocol – eine Home-Assistant-Integration,
die einen **SYR Safe-T+ Connect** Leckageschutz ohne Herstellercloud einbindet.

Das Gerät hat keine lokale API: Port 5333, über den die größere
*SafeTech Connect* ihre JSON-Schnittstelle anbietet, ist beim Safe-T+
geschlossen, und der Webserver auf Port 80 liefert auf jeden Pfad eine leere
Antwort. Es gibt nur einen Weg an die Daten – den, den das Gerät selbst
benutzt: den 10-Sekunden-Takt, in dem es unverschlüsselt an
`iot1.syrconnect.de` funkt.

SYRUP stellt genau diesen Endpunkt in Home Assistant bereit. Zeigt
`iot1.syrconnect.de` im lokalen Netz auf deine HA-Instanz, landen die
Meldungen hier statt in der Cloud.

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

HACS verteilt Integrationen, keine Add-ons – SYRUP ist deshalb ein
Custom Component. In HACS unter *Benutzerdefinierte Repositories* dieses
Repository als Typ **Integration** hinzufügen, installieren, Home Assistant
neu starten. Alternativ `custom_components/syrup` nach
`<config>/custom_components/syrup` kopieren.

Danach unter *Einstellungen → Geräte & Dienste → Integration hinzufügen*
nach **SYRUP** suchen und die Seriennummer der Box eintragen (steht in der
SYR-App, oder im Feld `getSRN` eines Mitschnitts).

### 2. Port 80 auf Home Assistant umbiegen

Das Gerät spricht **Port 80**, Home Assistant lauscht auf 8123. Eine der
folgenden Brücken wird gebraucht:

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
