# BuildingLink for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Validate](https://github.com/evandcoleman/ha-buildinglink/actions/workflows/validate.yml/badge.svg)](https://github.com/evandcoleman/ha-buildinglink/actions/workflows/validate.yml)

A Home Assistant custom integration for [BuildingLink](https://www.buildinglink.com/) — the resident portal used by many apartment buildings and condos.

## Features

- **📦 Packages** — Track pending package deliveries with carrier and tracking info
- **🔧 Maintenance Requests** — Monitor open maintenance requests
- **📢 Announcements** — See active building announcements
- **📅 Calendar Events** — Upcoming building events
- **🏊 Amenity Reservations** — Your upcoming amenity reservations

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/evandcoleman/ha-buildinglink` as an **Integration**
4. Search for "BuildingLink" and install
5. Restart Home Assistant

### Manual

Copy the `custom_components/buildinglink` folder to your Home Assistant `config/custom_components/` directory.

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **BuildingLink**
3. Enter your refresh token

### Getting a Refresh Token

You'll need to capture the refresh token from the BuildingLink iOS app:

1. Install a network proxy tool (e.g., [Proxyman](https://proxyman.io/))
2. Configure your iPhone to use the proxy
3. Open the BuildingLink app and log in
4. Look for a request to `auth.buildinglink.com/connect/token`
5. Copy the `refresh_token` from the response

## Sensors

| Sensor | Description |
|---|---|
| `sensor.buildinglink_packages` | Count of pending packages (with carrier/tracking in attributes) |
| `sensor.buildinglink_maintenance_requests` | Count of open maintenance requests |
| `sensor.buildinglink_announcements` | Count of active announcements (with content in attributes) |
| `sensor.buildinglink_calendar_events` | Count of upcoming calendar events |
| `sensor.buildinglink_amenity_reservations` | Count of upcoming amenity reservations |

Data refreshes every 5 minutes. The refresh token is automatically rotated.

## License

MIT
