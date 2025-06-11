# polont

This repository contains a small tool for fetching campaign finance data from the FEC API and the Colorado TRACER system.  The data is transformed into a simple graph structure stored in `graph.json`.

## Requirements
- Python 3
- `requests` library (`pip install requests`)
- Internet access to reach the FEC API

Set the environment variable `FEC_API_KEY` with your API key. If it is not set, the script falls back to a demo key which may be rate limited.

## Running the fetchers
Execute the FEC data fetcher using:

```bash
python3 FECdata.fetch.transform.py
```

The script reads `graph.json` (creating it if missing) and updates it with nodes and edges from candidates, committees and contributions.

To ingest Colorado TRACER data run:

```bash
python3 TRACERdata.fetch.transform.py
```

This script downloads the public TRACER contribution CSV, parses it and appends
the data to the same `graph.json` file. The default URL fetches the latest cycle,
but you can set the `YEAR` environment variable to download a different election
year back to 2020. The download is zipped and the script extracts the CSV automatically.
The CSV is encoded with Windows-1252, which the script reads automatically.

API calls are retried automatically when rate limited. The tool waits up to three
times for 60 seconds each and then performs one final retry after waiting an
hour before giving up.

If you see SSL certificate errors when fetching TRACER data,
set the environment variable `VERIFY_SSL=0` to skip the check.
