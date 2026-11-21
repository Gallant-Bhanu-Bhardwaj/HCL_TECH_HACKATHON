import os

API_BASE_URL = os.getenv("RAIL_API_BASE_URL", "http://localhost:8000").rstrip("/")
MOCK_MODE = os.getenv("RAIL_MOCK_MODE", "true").lower() in {"1", "true", "yes", "on"}
DEFAULT_PASSENGER_ID = os.getenv("RAIL_PASSENGER_ID", "PAX-1001")
REQUEST_TIMEOUT = int(os.getenv("RAIL_REQUEST_TIMEOUT", "12"))
