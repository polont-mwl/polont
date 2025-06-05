import requests
import json
import os

# Configuration
GRAPH_JSON_PATH = 'graph.json'  # Adjust this path as needed

# Load existing graph data or initialize new structure
if os.path.exists(GRAPH_JSON_PATH) and os.path.getsize(GRAPH_JSON_PATH) > 0:
    with open(GRAPH_JSON_PATH, 'r') as f:
        graph = json.load(f)
else:
    graph = {'nodes': [], 'edges': []}

# Use dicts for fast lookup to avoid duplicates
existing_node_ids = {node['id'] for node in graph['nodes']}
existing_edges = {(e['source'], e['target'], e['label']) for e in graph['edges']}

# Direct request using known working Postman URL
url = "https://api.open.fec.gov/v1/schedules/schedule_a/?api_key=h3pdYZNm4O69cZIeogPkzx0keh7tBqkoPphTVntC&contributor_state=CO&two_year_transaction_period=2024&per_page=20"
print(f"Requesting: {url}")
response = requests.get(url)
data = response.json()

results = data.get('results', [])
print(f"Results: {len(results)}")

for item in results:
    donor_id = f"individual_{item['contributor_name'].replace(' ', '_')}"
    cmte_id = f"committee_{item['committee']['name'].replace(' ', '_')}"

    # Donor node
    if donor_id not in existing_node_ids:
        graph['nodes'].append({
            'id': donor_id,
            'label': item['contributor_name'],
            'type': 'Individual',
            'attributes': [
                {'key': 'city', 'value': item.get('contributor_city')},
                {'key': 'employer', 'value': item.get('contributor_employer')},
                {'key': 'occupation', 'value': item.get('contributor_occupation')}
            ]
        })
        existing_node_ids.add(donor_id)

    # Committee node
    if cmte_id not in existing_node_ids:
        graph['nodes'].append({
            'id': cmte_id,
            'label': item['committee']['name'],
            'type': 'Campaign',
            'attributes': [
                {'key': 'committee_id', 'value': item.get('committee_id')}
            ]
        })
        existing_node_ids.add(cmte_id)

    # Edge (donor -> committee)
    edge_key = (donor_id, cmte_id, 'contributed_to')
    if edge_key not in existing_edges:
        graph['edges'].append({
            'source': donor_id,
            'target': cmte_id,
            'label': 'contributed_to',
            'type': 'Contribution',
            'attributes': [
                {'key': 'amount', 'value': item.get('contribution_receipt_amount')},
                {'key': 'date', 'value': item.get('contribution_receipt_date')}
            ]
        })
        existing_edges.add(edge_key)

# Save updated graph
with open(GRAPH_JSON_PATH, 'w') as f:
    json.dump(graph, f, indent=2)

print("Graph updated with FEC data from direct request.")
