# Model Usage Tracker

Metadata-only usage collector and dashboard for cloud and local inference. Standard-library Python; no third-party runtime dependencies.

## Run

Use Python 3.11 or newer. Create a private `state` directory containing `ingest-token` (a random secret), `server.crt`, and `server.key` (a TLS certificate and private key). Generate these locally; never commit them.

Set `USAGE_STATE` to the state directory, optionally `USAGE_BIND` (default `localhost`) and `USAGE_PORT` (default `8443`), then run `python collector.py`.

Open the HTTPS listener in your browser. `GET /health` checks availability; `GET /api/summary?days=0` returns all totals (supported windows: 0, 1, 7, 30). POST metadata batches to `/api/ingest` using a Bearer credential matching the token file. See `test_collector.py` for record examples.

Set `USAGE_MODEL_MAP` to a JSON file shaped like `models.example.json` to display alias - backend labels. No machine-specific model mapping is bundled.

`usage_agent.py` optionally reads Hermes per-model usage and forwards metadata with a durable SQLite outbox. It expects a local `agent.json` containing `url`, `token`, `ca`, `machine`, `started`, and optionally `home`, `scheduler_outbox`, or `images`. Keep it outside Git. `started` is a Unix timestamp defining the historical baseline. Collector schema allowlists fields and rejects prompt/response content.

## Dashboard sorting

Every breakdown column supports ascending and descending sorting, including real backend and last-used UTC date/time. Numeric columns use underlying counts, measurements and unrounded retail estimates, not formatted display strings. Unknown values remain last in either direction. Column buttons support keyboard navigation and expose their direction with arrows and `aria-sort`.

The selected column and direction are remembered in browser-local storage and retained across automatic refreshes, time-window changes and page reloads. If storage is unavailable, sorting still works for the current page.

## Tests

Run `python -m unittest discover -v` for the Python suite, `node --test test_sorting.cjs` for dashboard sorting tests, and `node --check dashboard.js` for JavaScript syntax validation.

## Security and limitations

The dashboard and summary are unauthenticated: keep the listener private or place it behind an authenticated reverse proxy. Ingestion requires a secret and HTTPS. Do not expose this development HTTP server directly to the Internet. Stored metadata includes configured source/model/session identifiers; protect the state directory. No runtime data, credentials, deployment scripts, host addresses, certificates, or original history are distributed.

Retail estimates are illustrative, not invoices; bundled rates must be independently reviewed and updated. Historical baselines are excluded from rolling windows. Client observations are not double-counted with local scheduler totals. Missing GPU/timing data is not fabricated.
