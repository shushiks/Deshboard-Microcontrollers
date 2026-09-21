# Security audit

Reviewed: telemetry ingestion, heartbeat, device editing, history reads, SQLite access, reverse geocoding and the browser dashboard.

## Fixed

- **High — unauthenticated writes:** production now requires `ESP_API_KEY`; all mutating endpoints verify `X-API-Key` with a constant-time comparison.
- **Medium — mass assignment:** telemetry can no longer alter a device's alert threshold. Device configuration remains in the dedicated PATCH endpoint.
- **Medium — malformed input:** identifiers, numeric ranges, dates, unknown JSON fields and history limits are validated. A packet containing only null sensor values is rejected.
- **Medium — write flooding:** mutating endpoints have a local per-process rate limit.
- **Low — browser hardening:** CSP, clickjacking, MIME sniffing, referrer and browser-permission headers were added; production API documentation is disabled.
- **Low — excessive response fields:** internal geocoding timestamps and redundant reading/database identifiers are no longer returned.
- **SQL injection review:** repository queries use bound SQLite parameters. The only dynamic SQL is a fixed, application-owned migration list.

## Remaining deployment considerations

- Read endpoints and the dashboard are intentionally public. Add user authentication or restrict them at a reverse proxy before exposing private telemetry to the internet.
- A single shared ESP key allows any holder to submit data for any valid `device_id`. Per-device keys or mTLS are the next step if devices are deployed in untrusted locations.
- The rate limiter is in process memory. Use a reverse-proxy/Redis limiter when running multiple application replicas.
- The current body-size check uses `Content-Length`; chunked uploads must also be limited at a reverse proxy before internet exposure.
- Development mode without `ESP_API_KEY` accepts writes without authentication. Keep it on a trusted local network only.
- Run internet deployments behind HTTPS. The API key must never travel over plain HTTP outside a trusted LAN.
- Reverse geocoding sends configured coordinates to the selected geocoding provider.
