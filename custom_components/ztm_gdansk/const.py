"""Constants for ZTM Gdańsk integration."""

DOMAIN = "ztm_gdansk"

URL_DEPARTURES = "https://ckan2.multimediagdansk.pl/departures"
URL_STOPS = (
    "https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172"
    "/resource/d3e96eb6-25ad-4d6c-8651-b1eb39155945/download/stops.json"
)
URL_STOPS_IN_TRIP = (
    "https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172"
    "/resource/3115d29d-b763-4af5-93f6-763b835967d6/download/stopsintrip.json"
)
URL_ROUTES = (
    "https://ckan.multimediagdansk.pl/dataset/c24aa637-3619-4dc2-a171-a23eec8f2172"
    "/resource/22313c56-5acf-41c7-a5fd-dc5dc72b3851/download/routes.json"
)

DEFAULT_SCAN_INTERVAL = 60
DEFAULT_DEPARTURE_COUNT = 5
MIN_SCAN_INTERVAL = 20

CONF_STOP_ID = "stop_id"
CONF_STOP_NAME = "stop_name"
CONF_STOP_CODE = "stop_code"
CONF_LINES_FILTER = "lines_filter"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DEPARTURE_COUNT = "departure_count"
