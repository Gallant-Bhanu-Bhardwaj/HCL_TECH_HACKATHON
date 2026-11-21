# Ujjwal Rail AI Frontend

A modular Streamlit frontend for AI-powered railway travel support. It includes chat, train search, bookings, action confirmation/cancellation, refund preview and human support handover workflows.

## Run in mock mode

From the project root:

```powershell
pip install -r Frontend/requirements.txt
streamlit run Frontend/app.py
```

Mock mode is enabled by default. Passenger identity can be changed in the sidebar text field.

## Live backend mode

Set environment variables before starting Streamlit:

```powershell
$env:RAIL_MOCK_MODE="false"
$env:RAIL_API_BASE_URL="http://localhost:8000"
$env:RAIL_PASSENGER_ID="PAX-1001"
streamlit run Frontend/app.py
```

The backend must run separately.

## API contract

The implementation is centralized in `services/api_client.py`:

- `GET /health`
- `POST /chat` with `X-Passenger-Id`
- `GET /bookings/{booking_id}`
- `POST /actions/{action_id}/confirm`
- `POST /actions/{action_id}/cancel`
- `GET /trace/{trace_id}`

The chat request body is:

```json
{"session_id":"session_001","message":"Show my bookings"}
```

A complete train-list endpoint is not assumed because one was not provided in the backend contract. Live train search remains clearly unsupported until the backend exposes and documents that endpoint.

## Safety behavior

- Cancellation requires explicit passenger confirmation.
- Refund amounts are only displayed from mock or backend responses.
- No phone numbers or full passenger IDs are displayed in the UI.
- Passenger ownership is enforced by the backend through `X-Passenger-Id`.
- Backend connection and timeout errors are handled centrally.

## Structure

```text
Frontend/
  app.py
  config.py
  components/
  services/
  styles/
  utils/
  requirements.txt
  README.md
```
