# ZenseHome (Home Assistant integration)

Integrerer ZenseHome PC-boks (TCP/ASCII API) direkte i Home Assistant som native `light` og `switch`.

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

Hvis en enhed ikke står i JSON, gættes type ud fra navnet (fx “stik/kontakt/ventilation” -> switch).
---

## Hvordan du ændrer “kontakt vs lys” i UI
Efter installation:
- Settings → Devices & services → ZenseHome → **Configure**
- Sæt `entity_types_json` som vist, gem
- Genindlæs integrationen (HA gør det typisk automatisk; ellers genstart)

---

## Bemærkninger om “korrekt async”
- TCP-kald er fuldt async via `asyncio.open_connection`
- Der er en `asyncio.Lock()` så der kun er **én session ad gangen** (som Zense kræver)
- Polling kører via `DataUpdateCoordinator` hvert N minutter
- Kommandoer opdaterer state lokalt med det samme og sync’er igen ved næste poll

Hvis du vil have en pænere Options-UI (dropdown pr enhed med navn i stedet for JSON), kan det laves som næste iteration.
::contentReference[oaicite:0]{index=0}