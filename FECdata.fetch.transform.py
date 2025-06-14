import requests
import json
import os
import hashlib
import time  # Used for retry delays
from urllib.parse import urlencode

# Debug flag toggled through environment variable
DEBUG = os.getenv('DEBUG', '1') == '1'


def debug(msg: str) -> None:
    """Print debug messages when DEBUG mode is on."""
    if DEBUG:
        print(f"[DEBUG] {msg}")

# Configuration values for the FEC API
DEFAULT_API_KEY = 'h3pdYZNm4O69cZIeogPkzx0keh7tBqkoPphTVntC'
API_KEY = os.getenv('FEC_API_KEY', DEFAULT_API_KEY)

CONTRIBUTION_ENDPOINT = 'https://api.open.fec.gov/v1/schedules/schedule_a'
CANDIDATE_ENDPOINT = 'https://api.open.fec.gov/v1/candidates'
COMMITTEE_ENDPOINT = 'https://api.open.fec.gov/v1/committees'

# Short and long retry delays when hitting API rate limits
RETRY_WAIT_SHORT = 60        # wait 60 seconds on first few retries
RETRY_WAIT_LONG = 60 * 60    # wait 60 minutes on the final retry
MAX_SHORT_RETRIES = 3        # number of short retries

# Graph file stored relative to this script
GRAPH_JSON_PATH = os.path.join(os.path.dirname(__file__), 'FECgraph.json')
# Separate file to confirm writes succeed
DEBUG_JSON_PATH = os.path.join(os.path.dirname(__file__), 'graph_debug.json')

# Attempt to load an existing graph file
try:
    # Only load when the file exists and has content
    if os.path.exists(GRAPH_JSON_PATH) and os.path.getsize(GRAPH_JSON_PATH) > 0:
        with open(GRAPH_JSON_PATH, 'r') as f:
            graph = json.load(f)
            debug(f"Loaded graph with {len(graph.get('nodes', []))} nodes")
    else:
        raise OSError
except (json.JSONDecodeError, OSError):
    # Start with an empty graph if the file can't be read
    graph = {'nodes': [], 'edges': []}
    debug("Starting with a new empty graph")

# Track nodes and edges so we don't insert duplicates
existing_node_ids = {n['id'] for n in graph['nodes']}
existing_edges = {(e['source'], e['target'], e['label']) for e in graph['edges']}


def log_error(url, resp):
    """Print a short error message when an API request fails."""
    print(f"Error {resp.status_code} fetching {url}")


def get_with_retry(url: str) -> requests.Response:
    """Request a URL and handle FEC API rate limiting."""
    resp = requests.get(url)
    retries = 0
    while resp.status_code == 429:
        # Decide how long to wait based on how many retries we've done
        if retries < MAX_SHORT_RETRIES:
            delay = RETRY_WAIT_SHORT
        elif retries == MAX_SHORT_RETRIES:
            delay = RETRY_WAIT_LONG
        else:
            break
        debug(f"Rate limited, waiting {delay} seconds before retry {retries + 1}")
        time.sleep(delay)
        resp = requests.get(url)
        retries += 1
    return resp


def fetch_candidates():
    """Fetch candidate nodes from the FEC API."""
    print("Fetching candidate data...")
    for year in (2020, 2024):
        page = 1
        more = True
        while more:
            params = {
                'api_key': API_KEY,
                'election_year': year,
                'per_page': 100,
                'page': page,
            }
            url = CANDIDATE_ENDPOINT + '?' + urlencode(params)
            debug(f"Requesting candidate page {page} for {year}")
            resp = get_with_retry(url)
            if resp.status_code != 200:
                log_error(url, resp)
                break
            try:
                data = resp.json()
                debug(f"Received {len(data.get('results', []))} candidate records")
            except json.JSONDecodeError:
                print(f"Invalid JSON from {url}")
                break
            for item in data.get('results', []):
                cid = item.get('candidate_id')
                name = item.get('name')
                if not cid or not name:
                    continue
                cycles = item.get('election_years', item.get('cycles', [])) or []
                if cid not in existing_node_ids:
                    graph['nodes'].append({
                        'id': cid,
                        'label': name,
                        'type': 'Campaign',
                        'attributes': [
                            {'key': 'candidate_id', 'value': cid},
                            {'key': 'cycles', 'value': cycles},
                        ],
                    })
                    existing_node_ids.add(cid)
            pages = data.get('pagination', {}).get('pages', 1)
            page += 1
            more = page <= pages
            # Show progress for candidate requests
            print(f"  Candidates {year}: completed page {page - 1}/{pages}")


def fetch_committees():
    """Fetch committee nodes and edges to candidates."""
    print("Fetching committee data...")
    for cycle in (2020, 2024):
        page = 1
        more = True
        while more:
            params = {
                'api_key': API_KEY,
                'cycle': cycle,
                'per_page': 100,
                'page': page,
            }
            url = COMMITTEE_ENDPOINT + '?' + urlencode(params)
            debug(f"Requesting committee page {page} for {cycle}")
            resp = get_with_retry(url)
            if resp.status_code != 200:
                log_error(url, resp)
                break
            try:
                data = resp.json()
                debug(f"Received {len(data.get('results', []))} committee records")
            except json.JSONDecodeError:
                print(f"Invalid JSON from {url}")
                break
            for item in data.get('results', []):
                cmte_id = item.get('committee_id')
                name = item.get('name')
                if not cmte_id:
                    continue
                if cmte_id not in existing_node_ids:
                    graph['nodes'].append({
                        'id': cmte_id,
                        'label': name,
                        'type': 'Campaign',
                        'attributes': [
                            {'key': 'committee_id', 'value': cmte_id},
                            {'key': 'cycles', 'value': item.get('cycles')},
                        ],
                    })
                    existing_node_ids.add(cmte_id)
                candidate_ids = item.get('candidate_ids') or []
                cid = item.get('candidate_id')
                if cid:
                    candidate_ids.append(cid)
                for cand in candidate_ids:
                    if cand not in existing_node_ids:
                        # Skip edges to candidates not already in the graph
                        continue
                    edge_key = (cmte_id, cand, 'supports')
                    if edge_key not in existing_edges:
                        graph['edges'].append({
                            'source': cmte_id,
                            'target': cand,
                            'label': 'supports',
                        })
                        existing_edges.add(edge_key)
            pages = data.get('pagination', {}).get('pages', 1)
            page += 1
            more = page <= pages
            # Show progress for committee requests
            print(f"  Committees {cycle}: completed page {page - 1}/{pages}")


def make_contrib_id(item):
    """Return contributor_id or a synthetic hash when missing."""
    contrib_id = item.get('contributor_id')
    if contrib_id:
        return contrib_id
    concat = (
        (item.get('contributor_name') or '') +
        (item.get('contributor_street_1') or '') +
        (item.get('contributor_zip') or '')
    )
    return hashlib.sha1(concat.encode('utf-8')).hexdigest()


def fetch_contributions():
    """Fetch individual contributions and create edges."""
    print("Fetching contribution data...")
    for period in (2020, 2024):
        page = 1
        more = True
        while more:
            params = {
                'api_key': API_KEY,
                'two_year_transaction_period': period,
                'per_page': 100,
                'page': page,
                'contributor_state': 'CO',
            }
            url = CONTRIBUTION_ENDPOINT + '?' + urlencode(params)
            debug(f"Requesting contribution page {page} for {period}")
            resp = get_with_retry(url)
            if resp.status_code != 200:
                log_error(url, resp)
                break
            try:
                data = resp.json()
                debug(f"Received {len(data.get('results', []))} contribution records")
            except json.JSONDecodeError:
                print(f"Invalid JSON from {url}")
                break
            for item in data.get('results', []):
                contrib_id = make_contrib_id(item)
                name = item.get('contributor_name')
                employer = item.get('contributor_employer')
                if not employer or not employer.lower().startswith('jeffco'):
                    continue
                if contrib_id not in existing_node_ids:
                    graph['nodes'].append({
                        'id': contrib_id,
                        'label': name,
                        'type': 'Individual',
                        'attributes': [
                            {'key': 'address', 'value': item.get('contributor_city')},
                            {'key': 'employer', 'value': employer},
                        ],
                    })
                    existing_node_ids.add(contrib_id)
                targets = []
                cmte = item.get('committee_id')
                cand = item.get('candidate_id')
                if cmte:
                    targets.append(cmte)
                if cand:
                    targets.append(cand)
                for tgt in targets:
                    if tgt not in existing_node_ids:
                        # Skip edges if target is unknown
                        continue
                    edge_key = (contrib_id, tgt, 'contributed_to')
                    if edge_key not in existing_edges:
                        graph['edges'].append({
                            'source': contrib_id,
                            'target': tgt,
                            'label': 'contributed_to',
                            'type': 'Contribution',
                            'attributes': [
                                {'key': 'amount', 'value': item.get('contribution_receipt_amount')},
                                {'key': 'date', 'value': item.get('contribution_receipt_date')},
                            ],
                        })
                        existing_edges.add(edge_key)
            pages = data.get('pagination', {}).get('pages', 1)
            page += 1
            more = page <= pages
            # Show progress for contribution requests
            print(f"  Contributions {period}: completed page {page - 1}/{pages}")


fetch_candidates()
fetch_committees()
fetch_contributions()

# Persist the augmented graph back to disk and debug file
with open(GRAPH_JSON_PATH, 'w') as f:
    json.dump(graph, f, indent=2)
    debug("Graph written to disk")
with open(DEBUG_JSON_PATH, 'w') as f:
    json.dump(graph, f, indent=2)
    debug("Debug graph written")

print("Graph updated with FEC data from all sources.")
