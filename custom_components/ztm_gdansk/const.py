"""Constants for the ZTM Gdańsk integration."""
from __future__ import annotations

DOMAIN = "ztm_gdansk"

# Configuration keys
CONF_SCAN_INTERVAL = "scan_interval"
CONF_NEXT_DEPARTURES_COUNT = "next_departures_count"
CONF_STALE_DATA_MAX_AGE = "stale_data_max_age"
CONF_ALERTS = "alerts"
CONF_ALERTS_ENABLED = "enabled"
CONF_ALERTS_FILTER_LINES = "filter_lines"
CONF_ALERTS_FILTER_STOPS = "filter_stops"
CONF_DEPARTURES = "departures"
CONF_STOP_ID = "stop_id"
CONF_STOP_NAME = "stop_name"
CONF_LINES = "lines"

# Defaults
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_NEXT_DEPARTURES_COUNT = 5
DEFAULT_STALE_DATA_MAX_AGE = 600
DEFAULT_ALERTS_SCAN_INTERVAL = 300

# Limits
MIN_SCAN_INTERVAL = 15
MIN_ALERTS_SCAN_INTERVAL = 60
MIN_NEXT_DEPARTURES_COUNT = 1
MAX_NEXT_DEPARTURES_COUNT = 20

# API
API_BASE = "https://ckan2.multimediagdansk.pl"
API_DEPARTURES_URL = f"{API_BASE}/departures"
API_DISPLAY_MESSAGES_URL = f"{API_BASE}/displayMessages"
API_BSK_URL = "https://files.cloudgdansk.pl/d/otwarte-dane/ztm/bsk.json"
API_ZNT_URL = "https://files.cloudgdansk.pl/d/otwarte-dane/ztm/znt.json?v=1"
_CKAN_RESOURCE_BASE = "https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172/resource"
API_STOPS_URL = f"{_CKAN_RESOURCE_BASE}/d3e96eb6-25ad-4d6c-8651-b1eb39155945/download/stopsingdansk.json"
API_DISPLAYS_URL = f"{_CKAN_RESOURCE_BASE}/ee910ad8-8ffa-4e24-8ef9-d5a335b07ccb/download/displays.json"
API_ROUTES_URL = f"{_CKAN_RESOURCE_BASE}/22313c56-5acf-41c7-a5fd-dc5dc72b3851/download/routes.json"
HTTP_TIMEOUT_SECONDS = 10

# Backoff
BACKOFF_ERROR_THRESHOLD = 3  # consecutive failures before update_interval doubles
BACKOFF_MULTIPLIER = 2
BACKOFF_MAX_DEPARTURES = 600  # seconds
BACKOFF_MAX_ALERTS = 1800  # seconds

# Polish character normalization (for entity_id slugification)
POLISH_CHAR_MAP = str.maketrans({
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
    "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
    "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
})

PLATFORMS = ["sensor", "binary_sensor"]
