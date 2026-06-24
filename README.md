# WebsiteScorecard

CLI to scan websites from a CSV and enrich rows with check results (SSL certificate status, and more over time). Use the `resolve` command first when your CSV has institution names but no URLs.

## Prerequisites

- Python 3.10 or newer
- A CSV file with a column containing website URLs (domains or full URLs)

## Quick start

### 1. Set up a virtual environment and install

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

For development (includes pytest):

```bash
pip install -e ".[dev]"
```

Activate the virtual environment in any new terminal session before running commands:

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Test data

The repo includes a sample CSV at `data/mins_depts_test.csv` with Sri Lankan ministries and departments:

```csv
Type,Institution Name,URL
Ministry,Ministry of Defence,defence.lk
Ministry,"Ministry of Finance, Planning and Economic Development",treasury.gov.lk
Ministry,Ministry of Digital Economy,midec.gov.lk
...
```

The `URL` column contains bare domains (e.g. `defence.lk`). Full URLs such as `https://example.com/path` also work.

### 3. Run a scan

```bash
websitescorecard scan data/mins_depts_test.csv --column URL --checks ssl
```

This writes `data/mins_depts_test_scored.csv` by default (same name as input with `_scored` inserted).

Specify an output file:

```bash
websitescorecard scan data/mins_depts_test.csv -c URL -o output/mins_depts_scored.csv --checks ssl
```

### 4. Check the output

```csv
Type,Institution Name,URL,ssl_status,ssl_error
Ministry,Ministry of Defence,defence.lk,valid,
Ministry,Ministry of Digital Economy,midec.gov.lk,valid,
...
```

| `ssl_status` | Meaning |
|--------------|---------|
| `valid` | TLS succeeds, cert verifies, not expired |
| `expired` | Cert present but past expiry |
| `invalid` | Cert present but fails verification (hostname mismatch, self-signed, untrusted chain, etc.) |
| `no_certificate` | Server reached over TLS but no certificate presented |
| `unreachable` | Could not connect to evaluate SSL (bad domain, DNS failure, timeout, connection error) |
| `error` | Check raised an unexpected internal error (recorded in `ssl_error`) |

The `ssl_error` column contains the underlying error message when something went wrong. For scorecard reporting, `expired` and `invalid` can be grouped as cert problems; `unreachable` rows can be flagged separately for CSV cleanup.

## Resolve names to domains

If your CSV has institution or department **names** but no URLs, use `resolve` to look up official domains via web search before running `scan`. **Resolve is not a check** — it does not appear in `--checks` and is not registered alongside checks like `ssl`. Checks run against URLs you already have; resolve is a pre-scan step that adds URL column(s) from names.

Typical two-step workflow:

```bash
# 1. Resolve names → domains (gov.lk and .gov only, keep up to 3 per row)
websitescorecard resolve data/bodies.csv -c "Institution Name" \
  --suffixes gov.lk,lk --limit 3 -o output/bodies_with_urls.csv

# 2. Scan the first URL column
websitescorecard scan output/bodies_with_urls.csv -c URL --checks ssl
```

`resolve` searches DuckDuckGo for `"{name} {query_suffix}"` (default query suffix: `Sri Lanka`), extracts hostnames from results, optionally filters by hostname suffix, and writes an enriched CSV. All original columns are preserved.

**Output columns:**

- `--limit 1` (default) → single column `URL` (or the name you set with `--url-column`)
- `--limit 3` → `URL`, `url_2`, `url_3` (the first column is the primary one for `scan`)
- `lookup_status` — `ok`, `no_results`, or `error`
- `lookup_error` — detail when status is `error`

Cells are left empty when fewer than N suffix-matching domains are found.

**Skipping lookups:** If a row already has a value in the primary URL column, resolve leaves it unchanged (useful for manual overrides in a partially filled CSV).

**Re-running:** Each run hits the search API again; there is no cache in v1.

For a large batch (e.g. ~470 rows), use conservative settings to avoid rate limits: `--concurrency 1` (default) and `--delay 1.0` (default) imply roughly 8+ minutes minimum.

## CLI reference

### `scan`

```bash
websitescorecard scan INPUT_CSV -c COLUMN [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `INPUT_CSV` | Input CSV file path |
| `-c, --column` | Column containing website URLs (**required**) |
| `-o, --output` | Output path (default: `{input}_scored.csv`) |
| `--checks` | Comma-separated checks to run (e.g. `ssl`) (**required**) |
| `--concurrency` | Parallel workers (default: 5) |
| `--timeout` | Socket timeout per check in seconds (default: 10) |
| `--no-error-columns` | Omit `*_error` detail columns |

Examples:

```bash
# SSL check on the sample data with 10 parallel workers and 15s timeout
websitescorecard scan data/mins_depts_test.csv -c URL --checks ssl --concurrency 10 --timeout 15

# View all options
websitescorecard scan --help
```

At least one check must be specified via `--checks`. Running with an empty value prints an error.

### `resolve`

```bash
websitescorecard resolve INPUT_CSV -c COLUMN [OPTIONS]
```

| Flag | Description |
|------|-------------|
| `INPUT_CSV` | Input CSV file path |
| `-c, --column` | Column with institution/department **names** (**required**) |
| `-o, --output` | Output path (default: `{input}_resolved.csv`) |
| `--limit` | Max domains to keep per row (default: `1`) |
| `--suffixes` | Comma-separated hostname suffixes to allow (e.g. `gov.lk,gov`) |
| `--query-suffix` | Text appended to every search query (default: `Sri Lanka`) |
| `--url-column` | Column name for the first result (default: `URL`) |
| `--concurrency` | Parallel workers (default: `1`) |
| `--delay` | Seconds to wait between searches per worker (default: `1.0`) |
| `--timeout` | HTTP timeout for search requests in seconds |

Examples:

```bash
# Resolve with suffix filter and multiple URLs per row
websitescorecard resolve data/bodies.csv -c "Institution Name" \
  --suffixes gov.lk,lk --limit 3 -o output/bodies_with_urls.csv

# View all options
websitescorecard resolve --help
```

## Development

Activate the virtual environment, then run tests:

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pytest
```

## Adding a new check

Checks are separate from domain lookup (`resolve`). To add a check that runs against URLs during `scan`:

1. Create `src/websitescorecard/checks/your_check.py` implementing the `Check` protocol.
2. Register it in `src/websitescorecard/checks/__init__.py`.
3. Run it via `--checks` (comma-separated for multiple checks).

See `src/websitescorecard/checks/ssl.py` for a reference implementation.
