# ZTM Gdańsk — Home Assistant Integration

Custom Home Assistant integration displaying real-time departures from ZTM Gdańsk (TRISTAR) stops. Includes a Lovelace dashboard card.

## Features

- Real-time departure data from any ZTM Gdańsk stop
- Configurable line filter (show only selected lines per stop)
- Configurable update interval (minimum 20 s) and departure count
- Sensor state = minutes to next departure (useful for automations)
- Custom Lovelace card with departure table, delay coloring, and live timestamps
- Polish and English UI translations

## Installation

### HACS (recommended)

1. Open HACS → Integrations → three-dot menu → Custom repositories
2. Add `https://github.com/harrrson/ZTM-Gdansk-Home-Assistant-integration` as type **Integration**
3. Search for "ZTM Gdańsk" and install
4. Restart Home Assistant

The Lovelace card JS is served automatically via HACS.

### Manual

1. Copy `custom_components/ztm_gdansk/` to your HA `config/custom_components/` directory
2. Restart Home Assistant
3. Add the Lovelace resource manually:
   - Navigate to **Settings → Dashboards → Resources** (or edit your `configuration.yaml`)
   - Add `/ztm_gdansk/ztm-gdansk-card.js` as a **JavaScript module**

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "ZTM Gdańsk"
3. Follow the three-step setup:
   - **Step 1:** Select a stop from the dropdown (search by name or code)
   - **Step 2:** Optionally filter lines (leave empty to show all lines)
   - **Step 3:** Set update interval and number of departures to display

You can change the line filter and options later via **Configure** on the integration card.

## Lovelace Card

Add the card to your dashboard via the visual editor or manually:

```yaml
type: custom:ztm-gdansk-card
entity: sensor.ztm_gdansk_dworzec_glowny_07
title: "Dworzec Główny 07"  # optional
```

### Card display

| Linia | Kierunek | Odjazd | Opóźnienie |
|-------|----------|--------|------------|
| 130 | Dworzec Główny | 20:53 | -2 min |
| 106 | Jasień | 21:00 | — |
| 112 | Osowa | 21:07 | +1 min |

- **Odjazd** — estimated departure time (HH:MM)
- **Opóźnienie** — green (on time / early), red (delayed), gray dash (scheduled only)
- Footer shows last update timestamp

## Sensor

Entity: `sensor.ztm_gdansk_{stop_name_slug}_{stop_code}`

| Property | Value |
|----------|-------|
| State | Minutes to next departure (int) |
| `stop_name` | Stop display name |
| `stop_id` | ZTM stop ID |
| `stop_code` | Stop code |
| `filtered_lines` | Active line filter (empty = all) |
| `departures` | List of departure dicts (up to configured count) |

## Data source

Open data from the **TRISTAR** ITS platform provided by the City of Gdańsk.  
License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)  
Source: [ckan.multimediagdansk.pl](https://ckan.multimediagdansk.pl)

## License

MIT — see [LICENSE](LICENSE)
