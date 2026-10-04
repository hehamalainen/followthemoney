"""Normalize sourced research; preserve commitments separately from cash and revenue."""
import json
import re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
a=json.loads((root/'scripts/research/circulation-core.json').read_text());b=json.loads((root/'scripts/research/circulation-downstream.json').read_text())
coverage=json.loads((root/'scripts/research/circulation-coverage.json').read_text())
source={**a['sources'],**b['sources']};nodes={}
node_alias={'CRWV_LENDERS':'LENDERS_CRWV'}
for n in b['nodes']+a['nodes']:
 n=dict(n);n['id']=node_alias.get(n['id'],n['id']);nodes[n['id']]=n
kinds={'equity':'investment','equity_and_convertible':'investment','cash_equity':'investment','cloud':'commercial','capacity_backstop':'commercial','recognized_revenue':'commercial','lease':'commercial','lease_purchase':'commercial','contingent_purchase':'commercial','power_purchase':'commercial','financing':'finance','debt':'finance','project_finance':'finance','project_equity':'finance','tax_equity':'finance','project_debt':'finance','vendor_finance':'finance','guarantee':'guarantee','hardware':'supplier','supplier':'supplier','component_route':'supplier','noncash_equity':'noncash'}
alias={'downstream_nvda_crwv_equity':'nvda-crwv-equity','downstream_nvda_crwv_capacity':'nvda-crwv-backstop','downstream_lenders_crwv':'lenders-crwv-debt'}
edges={}
for e in a['edges']+a['supportingEdges']+b['edges']:
 e=dict(e);old=e['id'];e['id']=alias.get(old,old)
 if e['id'] in edges:
  edges[e['id']]['sourceIds']=list(dict.fromkeys(edges[e['id']]['sourceIds']+e['sourceIds']));continue
 e['from']=node_alias.get(e['from'],e['from']);e['to']=node_alias.get(e['to'],e['to']);e['originalFlowType']=e['flowType'];e['flowType']=kinds[e['flowType']];e['status']=e['status'].replace('_',' ');e['detail']=e['detail'].strip()
 if old.startswith('downstream_'):
  e['tier']=3 if any(x in old for x in ['corz','glxy','tsm_','entergy','oracle_bloom','bloom_oracle','brookfield','bloom_projects','nebius_bloom','nebius_power','power_bloom']) else 2
 if old in ['nvda-sb-guarantee','oai-sb-lease']:e['tier']=3
 # The project's financing total is not a disclosed payment to Bloom.
 if old=='downstream_nebius_power_bloom':e['amountLabel']='Equipment payment undisclosed; $1.7B whole-project financing'
 if old=='downstream_crwv_vertiv':e['tier']=3
 if old=='downstream_oracle_bloom':e['sourceIds']=list(dict.fromkeys(e['sourceIds']+['downstream_bloom_warrant']))
 edges[e['id']]=e
cases=[]
for c in a['cases']+b['cases']:
 c=dict(c);c['edgeIds']=list(dict.fromkeys(alias.get(i,i)for i in c['edgeIds']))
 if c['id'] in ['stargate-guarantee','downstream_real_economy']:c['tier']=3
 if c['id']=='stargate-guarantee':
  c['edgeIds']=[e for e in c['edgeIds'] if e not in ['oai-orcl-cloud','orcl-nvda-hardware']];c['kind']='Contingent credit-support chain'
 if c['id']=='downstream_gpu_feedback':c['kind']='Investment, capacity and vendor credit'
 if c['id']=='downstream_silicon_cascade':c['kind']='Supplier cascade; no closed loop proved'
 if c['id']=='downstream_power_equity_feedback':c['kind']='Non-cash commercial feedback'
 if c['id']=='downstream_third_party_power_finance':c['kind']='Project financing chain'
 if c['id']=='downstream_real_economy':c['kind']='Supply-chain spending into local work'
 cases.append(c)
base_edge_ids=set(edges)
base_case_ids={c['id'] for c in cases}
# Coverage research already uses the public schema and supported economic types.
# Do not alter the original relationship or case records while extending the map.
assert coverage['asOf']=='2026-10-03'
for source_id, item in coverage['sources'].items():
 assert source_id.startswith('coverage_') and source_id not in source, source_id
 source[source_id]=item
for n in coverage['nodes']:
 assert n['id'] not in nodes, n['id']
 nodes[n['id']]=dict(n)
for node_id, metadata in coverage['nodeMetadata'].items():
 assert node_id in nodes, node_id
 nodes[node_id].update(metadata)
for e in coverage['edges']:
 assert e['id'].startswith('coverage_') and e['id'] not in edges, e['id']
 edges[e['id']]=dict(e)
for c in coverage['cases']:
 assert c['id'].startswith('coverage_') and c['id'] not in base_case_ids, c['id']
 cases.append(dict(c))
method=['Tier 1: model labs and major cloud providers. Tier 2: compute operators, hardware and direct suppliers. Tier 3: manufacturing enablers, power, sites, contractors and project financing. Cases include upstream links when needed for context.','Relationships are based on named counterparties in primary sources. Some describe an established supplier route without a disclosed invoice or payment.','Paid investments, outstanding borrowing, signed commitments, frameworks, conditional guarantees and recognized revenue retain separate labels. No aggregate capital-flow total is calculated.','The same dollar is not traced through the system. Interdependence can amplify a spending shock, but is not proof of fictitious revenue.']
result={'asOf':'2026-10-03','nodes':list(nodes.values()),'edges':list(edges.values()),'cases':cases,'sources':source,'methodology':method}
supported_types={'investment','commercial','finance','guarantee','noncash','supplier'}
supported_statuses={'public','unlisted','subsidiary','group-or-fund','project','consortium','undisclosed'}
for n in nodes.values():
 assert n['tier'] in (1,2,3),n['id']
 assert n['listingStatus'] in supported_statuses,n['id']
 assert n['tickerRole'] in {'listed_issuer','listed_parent','not_listed','not_applicable'},n['id']
 assert n['listingStatus']!='public' or n.get('ticker'),n['id']
 assert n['tickerRole'] not in {'listed_issuer','listed_parent'} or n.get('ticker'),n['id']
 assert all(s in source for s in n.get('sourceIds',[])),n['id']
for e in edges.values():
 assert e['from'] in nodes and e['to'] in nodes,e['id']
 assert e['flowType'] in supported_types,e['id']
 assert e['tier'] in (1,2,3),e['id']
 assert e['status'].strip() and e['detail'].strip(),e['id']
 dates=re.findall(r'\d{4}-\d{2}(?:-\d{2})?',e['date'])
 assert dates and max(dates)<=result['asOf'],e['id']
 assert e['sourceIds'],e['id']
 assert all(s in source for s in e['sourceIds']),e['id']
assert len({c['id'] for c in cases})==len(cases)
for c in cases:
 assert c['tier'] in (1,2,3) and c['edgeIds'],c['id']
 assert all(e in edges for e in c['edgeIds']),c['id']
 assert c['limitation'].strip(),c['id']
assert base_edge_ids.issubset(edges)
assert base_case_ids.issubset({c['id'] for c in cases})
(root/'dist/circulation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(len(nodes),'counterparties',len(edges),'relationships',len(cases),'cases')
