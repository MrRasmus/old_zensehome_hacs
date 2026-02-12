# ZenseHome (Home Assistant integration)

Integrerer ZenseHome PC-boks (TCP/ASCII API) direkte i Home Assistant som native `light` og `switch`.

## Ansvarsfraskrivelse
Denne kode leveres "som den er", uden nogen form for garanti. Du bruger den på eget ansvar.
Jeg tager ikke ansvar for skader, datatab, driftstop eller andre direkte/indirekte konsekvenser,
der kan opstå ved brug af koden eller integrationen.

## Installation via HACS (Custom repository)
1. HACS → Integrations → menu (⋮) → Custom repositories
2. Tilføj dette repo som type **Integration**
3. Installer “ZenseHome_Old”
4. Genstart Home Assistant
5. Settings → Devices & services → Add integration → ZenseHome

## Konfiguration
Indtast:
- IP (host)
- Login-kode
- Port (default 10001)

## Indstillinger (Options)
- Polling (minutter): fx 10 (opdaterer status ved vægtryk)
- Entity-typer (JSON): map enheder til light/switch

Eksempel:
```json

{
  "83190": "switch",
  "17861": "switch",
  "57541": "light"
}
```
Hvis en enhed ikke står i JSON, gættes type ud fra navnet (fx “stik/kontakt/ventilation” -> switch).

---
## Hvordan du ændrer “kontakt vs lys” i UI
Efter installation:
- Settings → Devices & services → ZenseHome → **Configure**
- Sæt `entity_types_json` som vist, gem
- Genindlæs integrationen (HA gør det typisk automatisk; ellers genstart)
---
