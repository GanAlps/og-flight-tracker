# og-flight-tracker — Flight Tracker

A locally-running web app that shows real-time flights on an interactive map using the free [OpenSky Network](https://opensky-network.org/) API. Pan and zoom anywhere in the world to see live aircraft.

Note: this is an experimental repo used to built with AI, not a real production code.

## Features

- Full-screen interactive map (OpenStreetMap via Leaflet.js)
- Live flight icons positioned and oriented by heading direction
- Click any aircraft to see: callsign, country, altitude, speed, heading, and ground status
- Auto-refreshes every 60 seconds; every successful fetch resets the timer, so active panning doesn't pile on redundant polls
- Manual refresh button (10-second cooldown) and a "My location" icon to recenter on the user
- Geolocation on first load (with graceful fallback to the world view if denied)
- Location search with typeahead suggestions (Nominatim)
- Zoom-out guard: one-shot toast, auto-refresh pauses until the view is usable again
- Rate-limit aware: distinct toast for OpenSky 429s; auto-refresh pauses and resumes on the next successful manual or map-move fetch

## Prerequisites

- Python 3.8+
- Shared virtualenv at `/home/oshogupta/workspace/master-venv`

## Install

```bash
cd /home/oshogupta/workspace/og-ft
/home/oshogupta/workspace/master-venv/bin/pip install -r requirements.txt
```

## OpenSky credentials (required)

The app authenticates to OpenSky via OAuth2 client-credentials. Without valid credentials the app will not start.

1. Register a free account at [opensky-network.org](https://opensky-network.org/my-opensky/account).
2. In your account settings, create an API client and copy the `client_id` / `client_secret`.
3. Copy `.env.example` to `.env` and fill both values:

   ```
   OPENSKY_CLIENT_ID=your_client_id
   OPENSKY_CLIENT_SECRET=your_client_secret
   ```

`.env` is gitignored. In production (e.g. Vercel), set the same two variables in the project's Environment Variables settings instead of committing a file.

## Run

```bash
/home/oshogupta/workspace/master-venv/bin/python app.py
```

Then open [http://localhost:5001](http://localhost:5001) in your browser.

## OpenSky API Notes

- Requires an OpenSky account and OAuth2 client credentials (see setup section above).
- The backend fetches a bearer token on demand, caches it for its ~30-minute lifetime, and refreshes on `401`.
- Rate limit: 1 request per 10 seconds per bbox. The app enforces this with an in-memory cache and a 60-second auto-refresh interval.
- Data covers all ADS-B transponder-equipped aircraft worldwide.

## Run Tests

```bash
/home/oshogupta/workspace/master-venv/bin/pytest --cov=app tests/ -v
```

## Project Structure

```
og-flight-tracker/
├── app.py              # Flask backend — OpenSky OAuth2 + rate-limit cache + Nominatim proxy
├── static/
│   ├── map.js          # Leaflet map, markers, auto-refresh, search, geolocation
│   ├── style.css       # Dark-themed UI
│   └── icons/
│       └── plane.svg   # Airplane SVG (reference only — inlined in JS)
├── templates/
│   └── index.html      # Single-page app shell
├── tests/
│   ├── conftest.py     # Seeds dummy OpenSky creds; autouse state reset
│   └── test_app.py     # Backend tests (≥99% coverage)
├── requirements.txt
├── .env.example
└── specs/              # Requirements/design/tasks per feature increment
    ├── flight-tracker/
    ├── search-autocomplete/
    ├── opensky-auth/
    ├── ux-improvements/
    └── ux-polish/
```
