# Flight Tracker — Requirements

## Overview

A locally-running web application that displays real-time flight data on an interactive map using a public open-source flight data API (OpenSky Network). The user can explore the map freely and see all flights currently in the air for any region they navigate to.

---

## User Requirements

### Core Map Experience
- A user can open the app in their browser and see a full-screen interactive map of the world.
- A user can pan and zoom the map to any location on Earth.
- A user can see all currently active flights rendered as icons on the map within the visible map area.
- A user can see flight icons update automatically as they navigate to new areas (fetch flights for the current view).

### Flight Information
- A user can click on any flight icon on the map to see a popup with details:
  - Callsign (flight identifier)
  - Country of origin
  - Altitude (meters)
  - Speed (m/s)
  - Heading/track (degrees)
  - Whether the aircraft is on the ground
- A user can see flight icons oriented in the direction the aircraft is heading.

### Data Refresh
- A user can see flights refresh automatically every 15 seconds to show updated positions.
- A user can manually trigger a refresh via a button.

### Navigation
- A user can search for a location by name (city or airport) and have the map pan to that location.

---

## Edge Cases & Constraints

- **API rate limits**: OpenSky Network anonymous API limits requests to 1 per 10 seconds and returns data within a 1-hour window. The app must respect these limits.
- **No flights in area**: If no flights are found for the current map view, the user sees a clear empty-state message (e.g., "No flights in this area").
- **API unavailable**: If the OpenSky API is unreachable, the user sees an error indicator and the last known data remains on screen.
- **Large bounding box**: If the user is zoomed out too far (whole world view), limit the request or show a prompt to zoom in to avoid returning thousands of aircraft.
- **No API key required**: The app uses the OpenSky Network REST API anonymously — no sign-up or credentials needed.
- **Local only**: The app runs as a local server (e.g., `localhost:5000`) — no deployment infrastructure needed.

---

## Out of Scope

- Flight history / playback
- Flight path prediction or routes
- Airline or airport lookup
- User accounts or saved locations
- Mobile native app (web browser only)

---

## Summary

A minimal, self-contained flight tracker web app using the free OpenSky Network API and an open-source map library. Core value is seeing real flights on a live map and being able to explore any region interactively.
