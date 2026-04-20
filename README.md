# ZTM Gdańsk — integracja Home Assistant

Integracja wyświetla odjazdy komunikacji miejskiej ZTM Gdańsk w czasie rzeczywistym
oraz monitoruje zakłócenia w ruchu. Dane pobierane z oficjalnego API Otwartych Danych
Gdańska (ckan2.multimediagdansk.pl).

Wymaga Home Assistant **2025.2** lub nowszego.

---

## Instalacja

### HACS (zalecane)

1. Dodaj repozytorium jako **custom repository** w HACS (kategoria: Integration).
2. Wyszukaj „ZTM Gdańsk" i zainstaluj.
3. Zrestartuj Home Assistant.

### Ręczna

Skopiuj katalog `custom_components/ztm_gdansk/` do katalogu
`config/custom_components/` swojej instancji HA:

```
config/
└── custom_components/
    └── ztm_gdansk/
        ├── __init__.py
        ├── api.py
        ├── binary_sensor.py
        ├── config_schema.py
        ├── const.py
        ├── coordinator.py
        ├── manifest.json
        ├── sensor.py
        └── tools/
            └── find_stops.py
```

Zrestartuj Home Assistant.

---

## Konfiguracja YAML

### Minimalna

```yaml
ztm_gdansk:
  departures:
    - stop_id: 1028
      lines:
        - "8"
        - "11"
```

### Pełna (z alertami i opcjami zaawansowanymi)

```yaml
ztm_gdansk:
  scan_interval: 60           # sekundy; min. 15, domyślnie 60
  next_departures_count: 5    # ile kolejnych odjazdów w atrybutach; 1-20, domyślnie 5
  stale_data_max_age: 600     # sekundy bez odświeżenia zanim sensor = unavailable; domyślnie 600

  departures:
    - stop_id: 1028
      stop_name: "Brama Wyżynna"   # opcjonalne — nadpisuje nazwę z API
      lines:
        - "8"
        - "11"

    - stop_id: 1495
      lines:
        - "205"
        - "N1"

  alerts:
    enabled: true                     # domyślnie true
    scan_interval: 300                # sekundy; min. 60, domyślnie 300
    filter_lines:                     # filtruj alerty do tych linii (OR z filter_stops)
      - "8"
      - "11"
    filter_stops:                     # filtruj alerty do tych przystanków
      - 1028
```

### Auto-discovery linii

Jeśli nie podasz `lines` (lub podasz pustą listę), integracja automatycznie wykryje
wszystkie linie odjeżdżające z danego przystanku przy starcie:

```yaml
ztm_gdansk:
  departures:
    - stop_id: 1028
      lines: []     # wykryj automatycznie
```

> **Uwaga:** Auto-discovery wykrywa tylko linie, które akurat kursują w momencie startu
> Home Assistant. Jeśli linia nie jeździ o danej porze (np. nocą, w weekendy),
> nie zostanie wykryta. Dla pełnego pokrycia podaj linie jawnie w `lines:`.

---

## Encje

### Sensory odjazdów (`sensor.ztm_*`)

Dla każdej kombinacji przystanek + linia powstaje sensor. Przykładowa nazwa:
`sensor.ztm_brama_wyzynna_8`.

Stan sensora: **timestamp** następnego odjazdu (ISO 8601).

| Atrybut | Typ | Opis |
|---|---|---|
| `line` | `str` | Numer linii |
| `stop_id` | `int` | ID przystanku |
| `stop_name` | `str` | Nazwa przystanku |
| `direction` | `str` | Kierunek (headsign) |
| `minutes_until` | `int` | Minuty do odjazdu |
| `delay_minutes` | `int` | Opóźnienie w minutach (ujemne = przed czasem) |
| `theoretical_time` | `str` | Planowany czas odjazdu (ISO 8601) |
| `vehicle_id` | `int` | ID pojazdu |
| `next_departures` | `list` | Lista kolejnych odjazdów (ilość wg `next_departures_count`) |
| `last_updated` | `str` | Czas ostatniego udanego odświeżenia danych |
| `data_age_seconds` | `int` | Wiek danych w sekundach |

Każdy element `next_departures`:

| Klucz | Opis |
|---|---|
| `theoretical` | Planowany czas odjazdu |
| `estimated` | Rzeczywisty (estymowany) czas odjazdu |
| `delay` | Opóźnienie w sekundach |
| `direction` | Kierunek |
| `vehicle_id` | ID pojazdu |

### Binary sensor zakłóceń (`binary_sensor.ztm_disruption`)

Stan: **ON** gdy istnieją aktywne zakłócenia, **OFF** gdy brak.

| Atrybut | Typ | Opis |
|---|---|---|
| `count` | `int` | Liczba aktywnych zakłóceń |
| `alerts` | `list` | Lista alertów (patrz niżej) |
| `last_updated` | `str` | Czas ostatniego odświeżenia |
| `data_age_seconds` | `int` | Wiek danych w sekundach |

Każdy alert w liście `alerts`:

| Klucz | Opis |
|---|---|
| `title` | Tytuł zakłócenia |
| `body` | Treść (tekst bez HTML) |
| `valid_from` | Początek obowiązywania |
| `valid_to` | Koniec obowiązywania |
| `lines` | Lista linii, których dotyczy |
| `stops` | Lista przystanków (stop_id), których dotyczy |
| `source` | Źródło: `bsk`, `display` lub `znt` |

Alerty zbierane z trzech źródeł API: komunikaty BSK (ogólne zakłócenia),
wiadomości tablic przystankowych (displayMessages) i komunikaty ZNT.
Filtrowane wg `filter_lines` / `filter_stops` (OR — wystarczy dopasowanie jednego).

---

## Jak znaleźć `stop_id`

Użyj wbudowanego narzędzia CLI:

```bash
# Szukaj po nazwie (ignoruje wielkość liter i polskie znaki)
python -m custom_components.ztm_gdansk.tools.find_stops "brama"

# Wynik:
# 1028    Brama Wyżynna
# 1029    Brama Wyżynna
# ...

# Wypisz wszystkie przystanki
python -m custom_components.ztm_gdansk.tools.find_stops --all
```

Komendę uruchamiaj z katalogu głównego repozytorium (lub z `config/` w HA, jeśli
`custom_components/ztm_gdansk/` tam się znajduje).

---

## Troubleshooting

### Nieznany `stop_id`

```
WARNING: Stop ID 9999 nie istnieje w API ZTM. Czy chodziło o: ...? — pomijam ten wpis.
```

Podany `stop_id` nie istnieje. Użyj CLI (`find_stops`) żeby znaleźć poprawne ID.

### Brak danych z API

```
WARNING: Nie udało się pobrać listy przystanków ZTM przy starcie (...) — kontynuuję bez walidacji
```

API było chwilowo niedostępne przy starcie HA. Integracja będzie działać,
ale bez walidacji ID przystanków. Dane odjazdów pojawią się przy następnym cyklu odpytywania.

### Sensor `unavailable`

Jeśli sensor przechodzi w stan `unavailable`, oznacza to że dane nie były odświeżone
przez okres dłuższy niż `stale_data_max_age` (domyślnie 600 s). Sprawdź logi pod kątem
błędów sieciowych. Integracja automatycznie stosuje backoff przy powtarzających się
błędach API (podwajanie interwału po 3 kolejnych błędach, maks. 600 s dla odjazdów,
1800 s dla alertów).

### Auto-discovery nie wykrył linii

```
WARNING: Nie udało się wykryć linii dla stop_id=... (brak danych z API w pierwszym pulli)
```

API nie zwróciło odjazdów w momencie startu (np. noc, poza kursowaniem). Podaj linie
jawnie w `lines:` lub zrestartuj HA w godzinach kursowania.

---

## Licencja

MIT
