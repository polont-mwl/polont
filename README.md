# polont

This repository contains a small tool for fetching campaign finance data from the FEC API and building a simple graph structure.

## Requirements
- Python 3
- `requests` library (`pip install requests`)
- Internet access to reach the FEC API

Set the environment variable `FEC_API_KEY` with your API key. If it is not set, the script falls back to a demo key which may be rate limited.

## Running the fetcher
Execute the data fetcher using:

```bash
python3 FECdata.fetch.transform.py
```

The script reads `graph.json` (creating it if missing) and updates it with nodes and edges from candidates, committees and contributions.

API calls are retried automatically when rate limited. The tool waits up to three
times for 60 seconds each and then performs one final retry after waiting an
hour before giving up.
