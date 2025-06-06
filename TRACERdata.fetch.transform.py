import csv
import json
import os
import hashlib
import requests

# Enable debug logging when the DEBUG env var is set
DEBUG = os.getenv('DEBUG', '1') == '1'

TRACER_BASE_URL = 'https://tracer.sos.colorado.gov/PublicSite/Download.aspx'
# CSV export endpoints for each entity type
CANDIDATE_URL = f'{TRACER_BASE_URL}?type=candidates'
COMMITTEE_URL = f'{TRACER_BASE_URL}?type=committees'
CONTRIBUTION_URL = f'{TRACER_BASE_URL}?type=contributions'

GRAPH_JSON_PATH = 'graph.json'


def debug(msg: str) -> None:
    """Print debug messages when DEBUG is enabled."""
    if DEBUG:
        print(f"[DEBUG] {msg}")


# Load existing graph or create a new one
try:
    with open(GRAPH_JSON_PATH, 'r') as f:
        graph = json.load(f)
        debug(f"Loaded graph with {len(graph.get('nodes', []))} nodes")
except (json.JSONDecodeError, OSError):
    graph = {'nodes': [], 'edges': []}
    debug('Starting new graph')

# Keep track of nodes and edges already stored in the graph
existing_node_ids = {n['id'] for n in graph['nodes']}
existing_edges = {(e['source'], e['target'], e['label']) for e in graph['edges']}


def download_file(url: str, dest: str) -> None:
    """Download a remote file to the local filesystem."""
    # Simple wrapper over requests.get for CSV downloads
    debug(f"Downloading {url} -> {dest}")
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"Error {resp.status_code} fetching {url}")
        return
    with open(dest, 'wb') as f:
        f.write(resp.content)


def make_contrib_id(name: str, addr: str) -> str:
    """Create a stable contributor ID using name and address."""
    # Hash ensures the ID is consistent across runs
    concat = (name or '') + (addr or '')
    return hashlib.sha1(concat.encode('utf-8')).hexdigest()


def process_candidates(path: str) -> None:
    """Read candidate data and add nodes."""
    # Each row describes a campaign filing
    debug(f"Processing candidates from {path}")
    with open(path, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            cid = row.get('FilerId') or row.get('candidate_id')
            name = row.get('FilerName') or row.get('candidate_name')
            if not cid or not name:
                continue
            if cid not in existing_node_ids:
                graph['nodes'].append({
                    'id': cid,
                    'label': name,
                    'type': 'Campaign',
                    'attributes': [
                        {'key': 'source', 'value': 'TRACER'}
                    ]
                })
                existing_node_ids.add(cid)


def process_committees(path: str) -> None:
    """Read committee data and add nodes."""
    # Committees represent campaign organizations
    debug(f"Processing committees from {path}")
    with open(path, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            cmte_id = row.get('CommitteeId') or row.get('committee_id')
            name = row.get('CommitteeName') or row.get('committee_name')
            if not cmte_id or not name:
                continue
            if cmte_id not in existing_node_ids:
                graph['nodes'].append({
                    'id': cmte_id,
                    'label': name,
                    'type': 'Campaign',
                    'attributes': [
                        {'key': 'source', 'value': 'TRACER'}
                    ]
                })
                existing_node_ids.add(cmte_id)


def process_contributions(path: str) -> None:
    """Read individual contributions and create edges."""
    # Link contributor nodes to the committees they support
    debug(f"Processing contributions from {path}")
    with open(path, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            name = row.get('ContributorName') or row.get('contributor_name')
            addr = row.get('ContributorAddress') or row.get('contributor_address')
            amount = row.get('Amount') or row.get('contribution_amount')
            date = row.get('Date') or row.get('contribution_date')
            cmte = row.get('CommitteeId') or row.get('committee_id')
            if not name or not cmte:
                continue
            contrib_id = make_contrib_id(name, addr)
            if contrib_id not in existing_node_ids:
                graph['nodes'].append({
                    'id': contrib_id,
                    'label': name,
                    'type': 'Individual',
                    'attributes': [
                        {'key': 'address', 'value': addr},
                        {'key': 'source', 'value': 'TRACER'}
                    ]
                })
                existing_node_ids.add(contrib_id)
            if cmte not in existing_node_ids:
                continue
            edge_key = (contrib_id, cmte, 'contributed_to')
            if edge_key not in existing_edges:
                graph['edges'].append({
                    'source': contrib_id,
                    'target': cmte,
                    'label': 'contributed_to',
                    'type': 'Contribution',
                    'attributes': [
                        {'key': 'amount', 'value': amount},
                        {'key': 'date', 'value': date}
                    ]
                })
                existing_edges.add(edge_key)


# Download files to local paths
# Data files are saved in a temporary directory
os.makedirs('tracer_data', exist_ok=True)
CANDIDATE_FILE = 'tracer_data/candidates.csv'
COMMITTEE_FILE = 'tracer_data/committees.csv'
CONTRIBUTION_FILE = 'tracer_data/contributions.csv'

download_file(CANDIDATE_URL, CANDIDATE_FILE)
download_file(COMMITTEE_URL, COMMITTEE_FILE)
download_file(CONTRIBUTION_URL, CONTRIBUTION_FILE)

# Process downloaded data
process_candidates(CANDIDATE_FILE)
process_committees(COMMITTEE_FILE)
process_contributions(CONTRIBUTION_FILE)

# Save updated graph
with open(GRAPH_JSON_PATH, 'w') as f:
    json.dump(graph, f, indent=2)
    debug('Graph updated with TRACER data')

print('Graph updated with TRACER data from all sources.')
