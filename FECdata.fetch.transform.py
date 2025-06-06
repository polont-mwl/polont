import requests
import json
import os
from urllib.parse import urlencode

# Configuration
DEFAULT_API_KEY = 'h3pdYZNm4O69cZIeogPkzx0keh7tBqkoPphTVntC'
API_KEY = os.getenv('FEC_API_KEY', DEFAULT_API_KEY)

CONTRIBUTION_ENDPOINT = 'https://api.open.fec.gov/v1/schedules/schedule_a'
CANDIDATE_ENDPOINT = 'https://api.open.fec.gov/v1/candidates'
COMMITTEE_ENDPOINT = 'https://api.open.fec.gov/v1/committees'

GRAPH_JSON_PATH = 'graph.json'  # Adjust this path as needed

# Try loading an existing graph from disk
try:
    with open(GRAPH_JSON_PATH, 'r') as f:
        graph = json.load(f)  # stored nodes and edges
except (json.JSONDecodeError, OSError):
    # Start with an empty graph if file is missing or invalid
    graph = {'nodes': [], 'edges': []}

# Use dicts for fast lookup to avoid duplicates
existing_node_ids = {node['id'] for node in graph['nodes']}
existing_edges = {(e['source'], e['target'], e['label']) for e in graph['edges']}


def fetch_candidates():
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
            resp = requests.get(url)
            try:
                data = resp.json()
            except json.JSONDecodeError:
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


def fetch_committees():
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
            resp = requests.get(url)
            try:
                data = resp.json()
            except json.JSONDecodeError:
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
                    if cand in existing_node_ids:
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


def fetch_contributions():
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
                'contributor_employer': 'jeffco',
            }
            url = CONTRIBUTION_ENDPOINT + '?' + urlencode(params)
            resp = requests.get(url)
            try:
                data = resp.json()
            except json.JSONDecodeError:
                break
            for item in data.get('results', []):
                contrib_id = item.get('contributor_id')
                name = item.get('contributor_name')
                employer = item.get('contributor_employer')
                if not contrib_id or not employer or not employer.lower().startswith('jeffco'):
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
                    if tgt in existing_node_ids:
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


fetch_candidates()
fetch_committees()
fetch_contributions()

# Save updated graph
with open(GRAPH_JSON_PATH, 'w') as f:
    json.dump(graph, f, indent=2)

print("Graph updated with FEC data from all sources.")
