# Das SYR-Connect-Protokoll der Control-Box

Analysiert an einem **SYR Safe-T+ Connect** (Modulnummer 2421.00.010,
Firmware 1.85, Gerätekennung `Safe-T+ V2.00e`) anhand eines
FRITZ!Box-Mitschnitts vom 20.09.2026.

## Transport

Die Box meldet sich im Standardtakt **alle 10 Sekunden** bei der
Herstellercloud -- unverschlüsselt, ohne Authentifizierung:

```http
POST /WebServices/SyrConnectDeviceWebService.asmx/GetAllCommands HTTP/1.1
Host: iot1.syrconnect.de
User-Agent: Husty Control-Box
Accept-Language: pl,en-us;q=0.7,en;q=0.3
Content-Type: application/x-www-form-urlencoded

xml=<sc><cp v="74DD" /><dat v="NUTZLAST" /></sc>
```

Aeltere oder andere Firmwarestände sprechen teils `syrconnect.consoft.de`
an. Der Taktgeber ist die Cloud: ihre Antwort endet auf `<ct rt="10" />`.

Die Antwort kommt im selben Aufbau zurück:

```xml
<?xml version="1.0" encoding="utf-8"?>
<sc>
  <cp v="94AA" />
  <dat v="NUTZLAST" />
</sc>
```

## Verschleierung der Nutzlast

Das `dat`-Attribut ist kein Chiffrat im kryptografischen Sinn, sondern eine
Verschleierung in drei Schritten:

1. Klartext-XML **XOR ein Ein-Byte-Schlüssel**. Der Schlüssel wechselt pro
   Nachricht; beobachtet wurden 0x14, 0x16, 0x18, 0x1A und 0x1E.
2. Sieben Bytes, die anschließend im form-urlencodeten Rumpf oder im
   XML-Attribut stören würden, werden durch je ein Sonderzeichen ersetzt:

   | Byte nach XOR | 0x22 `"` | 0x25 `%` | 0x26 `&` | 0x27 `'` | 0x2B `+` | 0x3C `<` | 0x3E `>` |
   |---------------|----------|----------|----------|----------|----------|----------|----------|
   | übertragen   | `Ä`      | `ä`      | `Ü`      | `ö`      | `€`      | `Ö`      | `ü`      |

3. Das Ergebnis wird als UTF-8 gesendet.

### Schlüssel zurückrechnen

Der Schlüssel steht in keiner Nachricht -- wie `cp` ihn kodiert (falls
überhaupt), ist offen. Er lässt sich aber direkt ableiten, weil die
Nutzlast immer mit `<d>` (Gerät) bzw. `<sc>` (Cloud) beginnt:

```python
key = cipher[1] ^ ord("d")
```

`cipher[0]` taugt nicht, weil `<` immer escaped wird.

### Sonderfall 0x7F

Ergibt ein Zeichen nach dem XOR das Steuerzeichen **DEL** (0x7F), wird nicht
das Ergebnis übertragen, sondern das **unveränderte Zeichen**. Das ist
eindeutig umkehrbar, weil 0x7F im Klartext nicht vorkommt: fällt beim
Entschlüsseln 0x7F an, war das gesendete Byte bereits das Original.

Je nach Schlüssel trifft das ein anderes Zeichen. Wer den Sonderfall nicht
kennt, liest an diesen Stellen DEL und hält das Zeichen für verschluckt:

| Schlüssel | betroffenes Zeichen | naiv gelesen                   |
|------------|---------------------|--------------------------------|
| 0x1E       | `a`                 | `S<DEL>fe-T+`, `Al<DEL>rms`    |
| 0x16       | `i`                 | `Engl<DEL>sh`, `<c<DEL> m=`    |
| 0x1A       | `e`                 | `g<DEL>tSRN`, `s<DEL>tADM`     |

Die Cloud macht es genauso -- offenbar dieselbe Bibliothek auf beiden Seiten.

## Inhalt der Nachrichten

### Gerät an Cloud

```xml
<d>
  <c n="1:setADM(2)f" v="FACTORY"/>
  <c n="1:getSRN" v="68SPAAEW"/>          <!-- Seriennummer -->
  <c n="1:getVER" v="Safe-T+ V2.00e"/>    <!-- Typ und Version -->
  <c n="1:getAB"  v="1"/>                 <!-- Absperrventil, 1 = offen -->
  <c n="1:getALA" v="FF"/>                <!-- Alarmcode, FF = kein Alarm -->
  <c n="1:getALM" v="Alarms: A3 A3 ..."/> <!-- Alarmverlauf -->
  <c n="1:getAVO" v="0mL"/>               <!-- laufende Entnahme -->
  <c n="1:getBAR" v="2529 mbar"/>         <!-- Wasserdruck -->
  <c n="1:getNET" v="ADC:933 6,05V"/>     <!-- Versorgungsspannung -->
  <c n="1:getVOL" v="Vol[L]951727"/>      <!-- Gesamtvolumen in Litern -->
  <c n="1:getSRV" v="19.08.19"/>          <!-- Wartungsdatum -->
  ...
</d>
<ci m="70:B3:D5:19:4C:B4" f="1.85" b="3" />
<cs v="81AC"/>
```

Nicht sicher gedeutet: `NPS` (stieg im Mitschnitt 1147 -> 1160 -> 1173),
`TPA`, `VLV`, `T1`, `T2`, `TBS`, `TC`, `TO`, `TMP`, `TYP`, `UL`, `REL`,
`get71`, das `b`-Attribut und die Prüfsumme `cs`.

### Cloud an Gerät

```xml
<sc><d>
  <c n="1:setADM" v="(2)f" />
  <c n="1:getSRN" v="" />
  <c n="1:getVER" v="" />
  ...
</d><ct rt="10" /></sc>
```

Eine Liste **leerer `get`-Felder** ist die Abfrage für den nächsten
Durchlauf. Die Cloud fragt dabei mehr Parameter ab, als das Safe-T+
beantwortet -- unter anderem `BAT`, `BLT`, `BSA`, `BSI`, `BUZ`, `CEL`,
`CNO`, `DBD`, `DBT`, `DCM`, `DMA`, `DOM`, `DPL`, `DRP`, `DST`, `DTC`,
`EXI`, `EXT`, `FLL`, `INT`, `LE`.

**Schaltbefehle** sind vermutlich Felder mit `set` und einem Wert, also etwa
`<c n="1:setAB" v="2"/>` zum Schließen des Ventils. Der
[ioBroker-Adapter](https://github.com/eifel-tech/ioBroker.syrconnect) baut
seine Antworten genau so. **Im Mitschnitt war kein Schaltbefehl enthalten,
das ist also noch nicht am Gerät verifiziert.**

## Was noch offen ist

* Wie `cp` zustande kommt und ob es den Schlüssel enthält.
* Wie `cs` berechnet wird -- das Gerät könnte Antworten mit falscher
  Prüfsumme verwerfen.
* Ob `setAB` tatsächlich schaltet, und welcher Wert für "zu" steht.
  Zum Klären: Mitschnitt laufen lassen und dabei in der SYR-App das Ventil
  schließen.
