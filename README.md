# ZenseHome (Home Assistant integration)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MrRasmus&repository=old_zensehome_hacs&category=integration)


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

## Version 1.1.0
- Tilføjer `button.pause_zense_5_min`, som pauser polling af Zense-bussen i 5 minutter.
- Gør `light` og `switch` mere HomeKit/Siri-venlige ved at opdatere Home Assistant-state optimistisk først og sende den langsomme Zense TCP-kommando i baggrunden.
- Bevarer debounce på dæmpning, så gentagne brightness-ændringer ikke spammer Zense-bussen.

## Branch: pause + optimistic state + reconcile + command sequence

Denne branch tilføjer en mere HomeKit/Siri-venlig kommandohåndtering:

- Home Assistant-state opdateres optimistisk med det samme.
- Den langsomme ZenseHome TCP/ASCII-kommando sendes derefter i baggrunden.
- Hvis kommandoen fejler, rulles state tilbage til forrige niveau.
- Efter en kort forsinkelse køres `Get <device-id>` for at afstemme med den faktiske ZenseHome-status.
- Hver entity har en intern `command_seq`, så gamle background tasks ikke kan overskrive nyere brugerhandlinger ved gentagne tryk.
- Det eksisterende API-lock og rate-limit i `api.py` bevares, så ZenseHome-bussen stadig kun får én kommando ad gangen.
- Dimming bevarer debounce, så hurtige brightness-ændringer samles til én ZenseHome `Fade`-kommando.
- `button.pause_zense_5_min` pauser polling i 5 minutter uden at blokere manuelle kommandoer.

