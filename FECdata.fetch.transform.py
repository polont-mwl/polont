import requests
import json
import os
from urllib.parse import urlencode

# Configuration
API_KEY = 'h3pdYZNm4O69cZIeogPkzx0keh7tBqkoPphTVntC'
FEC_ENDPOINT = 'https://api.open.fec.gov/v1/schedules/schedule_a/'
GRAPH_JSON_PATH = 'graph.json'  # Adjust this path as needed

# Base parameters for the FEC API
base_params = {
    'api_key': API_KEY,
    'contributor_state': 'CO',
    'two_year_transaction_period': 2024,
    'per_page': 100
}

# Load existing graph data or initialize new structure
if os.path.exists(GRAPH_JSON_PATH) and os.path.getsize(GRAPH_JSON_PATH) > 0:
    with open(GRAPH_JSON_PATH, 'r') as f:
        graph = json.load(f)
else:
    graph = {'nodes': [], 'edges': []}

# Use dicts for fast lookup to avoid duplicates
existing_node_ids = {node['id'] for node in graph['nodes']}
existing_edges = {(e['source'], e['target'], e['label']) for e in graph['edges']}

for is_individual in (True, False):
    page = 1
    more_pages = True

    while more_pages:
        params = base_params.copy()
        params['is_individual'] = is_individual
        params['page'] = page
        full_url = FEC_ENDPOINT + '?' + urlencode(params)
        print(f"Requesting: {full_url}")
        response = requests.get(full_url)

        try:
            data = response.json()
        except json.JSONDecodeError:
            print("Error decoding JSON response.")
            break

        results = data.get('results', [])
        print(f"Page {page}: {len(results)} results")

        for item in results:
            recipient_cmte_id = item.get('committee_id')
            recipient_cmte_name = item.get('committee', {}).get('name')
            cand_id = item.get('candidate_id')
            cand_name = item.get('candidate_name')

            if is_individual:
                donor_name = item.get('contributor_name')
                if not donor_name or not recipient_cmte_name:
                    continue
                donor_id = f"individual_{donor_name.replace(' ', '_')}"
                if donor_id not in existing_node_ids:
                    graph['nodes'].append({
                        'id': donor_id,
                        'label': donor_name,
                        'type': 'Individual',
                        'attributes': [
                            {'key': 'city', 'value': item.get('contributor_city')},
                            {'key': 'employer', 'value': item.get('contributor_employer')},
                            {'key': 'occupation', 'value': item.get('contributor_occupation')}
                        ]
                    })
                    existing_node_ids.add(donor_id)
            else:
                donor_cmte_id = item.get('contributor_committee_id')
                donor_cmte_name = item.get('contributor_name')
                if not donor_cmte_id or not recipient_cmte_id:
                    continue
                donor_id = f"committee_{donor_cmte_id}"
                if donor_id not in existing_node_ids:
                    graph['nodes'].append({
                        'id': donor_id,
                        'label': donor_cmte_name,
                        'type': 'Campaign',
                        'attributes': [
                            {'key': 'committee_id', 'value': donor_cmte_id}
                        ]
                    })
                    existing_node_ids.add(donor_id)

            if recipient_cmte_id:
                recip_id = f"committee_{recipient_cmte_id}"
                if recip_id not in existing_node_ids:
                    graph['nodes'].append({
                        'id': recip_id,
                        'label': recipient_cmte_name,
                        'type': 'Campaign',
                        'attributes': [
                            {'key': 'committee_id', 'value': recipient_cmte_id}
                        ]
                    })
                    existing_node_ids.add(recip_id)

            if cand_id:
                cand_node_id = f"candidate_{cand_id}"
                if cand_node_id not in existing_node_ids:
                    graph['nodes'].append({
                        'id': cand_node_id,
                        'label': cand_name,
                        'type': 'Campaign',
                        'attributes': [
                            {'key': 'candidate_id', 'value': cand_id}
                        ]
                    })
                    existing_node_ids.add(cand_node_id)

                if recipient_cmte_id:
                    edge_key = (recip_id, cand_node_id, 'supports_candidate')
                    if edge_key not in existing_edges:
                        graph['edges'].append({
                            'source': recip_id,
                            'target': cand_node_id,
                            'label': 'supports_candidate',
                            'type': 'Support',
                            'attributes': []
                        })
                        existing_edges.add(edge_key)

            if recipient_cmte_id and is_individual:
                edge_key = (donor_id, recip_id, 'contributed_to')
                if edge_key not in existing_edges:
                    graph['edges'].append({
                        'source': donor_id,
                        'target': recip_id,
                        'label': 'contributed_to',
                        'type': 'Contribution',
                        'attributes': [
                            {'key': 'amount', 'value': item.get('contribution_receipt_amount')},
                            {'key': 'date', 'value': item.get('contribution_receipt_date')}
                        ]
                    })
                    existing_edges.add(edge_key)

            if recipient_cmte_id and not is_individual:
                edge_key = (donor_id, recip_id, 'contributed_to')
                if edge_key not in existing_edges:
                    graph['edges'].append({
                        'source': donor_id,
                        'target': recip_id,
                        'label': 'contributed_to',
                        'type': 'Contribution',
                        'attributes': [
                            {'key': 'amount', 'value': item.get('contribution_receipt_amount')},
                            {'key': 'date', 'value': item.get('contribution_receipt_date')}
                        ]
                    })
                    existing_edges.add(edge_key)

            if cand_id:
                edge_key = (donor_id, cand_node_id, 'contributed_to_candidate')
                if edge_key not in existing_edges:
                    graph['edges'].append({
                        'source': donor_id,
                        'target': cand_node_id,
                        'label': 'contributed_to_candidate',
                        'type': 'Contribution',
                        'attributes': [
                            {'key': 'amount', 'value': item.get('contribution_receipt_amount')},
                            {'key': 'date', 'value': item.get('contribution_receipt_date')}
                        ]
                    })
                    existing_edges.add(edge_key)

        pagination = data.get('pagination', {})
        total_pages = pagination.get('pages', 1)
        page += 1
        more_pages = page <= total_pages

# Save updated graph
with open(GRAPH_JSON_PATH, 'w') as f:
    json.dump(graph, f, indent=2)

print("Graph updated with FEC data from all pages.")
