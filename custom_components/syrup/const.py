"""Konstanten für die SYRUP-Integration."""

DOMAIN = "syrup"

# Genau der Pfad, den die Firmware der Control-Box anspricht.
DEVICE_ENDPOINT = "/WebServices/SyrConnectDeviceWebService.asmx/GetAllCommands"

CONF_SERIAL = "serial"
CONF_POLL_INTERVAL = "poll_interval"
CONF_RELAY_URL = "relay_url"

DEFAULT_POLL_INTERVAL = 10  # Sekunden, wird dem Gerät als <ct rt="..."/> mitgeteilt
DEFAULT_RELAY_URL = "http://iot1.syrconnect.de" + DEVICE_ENDPOINT

SIGNAL_UPDATE = f"{DOMAIN}_update"

# Ventilstellung laut getAB. Die Zuordnung stammt aus der lokalen API der
# SafeTech Connect und ist für das Safe-T+ noch nicht gegengeprüft.
AB_OPEN = "1"
AB_CLOSED = "2"
