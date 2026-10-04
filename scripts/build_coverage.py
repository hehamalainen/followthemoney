"""Build a sourced entity directory without expanding the saved financial universe.

Only dist/coverage.json is written. Run after build_circulation.py so graph IDs
and documented relationship coverage reflect the latest curated graph.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AS_OF = '2026-10-03'
REVIEWED_AT = '2026-10-04'

# Product/brand aliases improve discovery; they do not become separate issuers.
FINANCIAL_ALIASES = {
    'MSFT': ['Microsoft Corporation', 'Azure', 'Microsoft Azure', 'Copilot'],
    'AMZN': ['Amazon', 'AWS', 'Amazon Web Services', 'Bedrock', 'Trainium', 'Inferentia'],
    'GOOGL': ['Alphabet', 'Google', 'Google Cloud', 'Gemini', 'DeepMind', 'Google DeepMind', 'GOOG'],
    'META': ['Meta Platforms', 'Facebook', 'Instagram', 'WhatsApp', 'Llama'],
    'AAPL': ['Apple', 'Apple Intelligence', 'Siri', 'Private Cloud Compute'],
    'NVDA': ['Nvidia', 'NVIDIA Corporation', 'CUDA', 'DGX', 'Blackwell'],
    'INTC': ['Intel', 'Intel Foundry', 'Xeon', 'Gaudi'],
    'ORCL': ['Oracle Corporation', 'Oracle Cloud', 'OCI'],
    'AMD': ['Advanced Micro Devices', 'Instinct', 'EPYC'],
    'AVGO': ['Broadcom Inc.'],
    'IBM': ['International Business Machines', 'watsonx'],
    'BABA': ['Alibaba', 'Alibaba Cloud', 'Qwen'],
    'BIDU': ['Baidu', 'ERNIE'],
    'TSM': ['TSMC', 'Taiwan Semiconductor Manufacturing', '2330.TW'],
    '005930.KS': ['Samsung', 'Samsung Electronics', 'Samsung Foundry', 'Samsung HBM'],
    '000660.KS': ['SK hynix', 'Hynix', 'SKHynix'],
    'ASML': ['ASML Holding'],
    'TEL': ['TE Connectivity', 'TE Connectivity plc'],
    '2317.TW': ['Hon Hai', 'Foxconn', 'Hon Hai Precision'],
    '2382.TW': ['Quanta', 'Quanta Computer'],
    'SU.PA': ['Schneider', 'Schneider Electric'],
    'SIE.DE': ['Siemens'],
    'ABBN.SW': ['ABB'],
    '2308.TW': ['Delta Electronics', 'Delta'],
    'CRM': ['Salesforce', 'Agentforce'],
    'NOW': ['ServiceNow'],
    'PATH': ['UiPath'],
    'CRWD': ['CrowdStrike'],
    'PLTR': ['Palantir', 'AIP'],
    'NBIS': ['Nebius', 'Nebius Group'],
    'CRWV': ['CoreWeave'],
    'SMCI': ['Supermicro', 'Super Micro', 'Super Micro Computer'],
}

CORE_METADATA = {
    'SPCX': (1, 'United States', 'Public parent spanning SpaceX, Starlink and SpaceXAI/xAI models and compute'),
    'CURSOR': (1, 'United States', 'AI coding software; Anysphere/Cursor is a SpaceX subsidiary'),
    'CBRS': (2, 'United States', 'Wafer-scale AI processors and inference compute services'),
    'TSLA': (1, 'United States', 'AI/robotics platform, related-party investor and Megapack energy-system supplier'),
    'MINIMAX': (1, 'China / Hong Kong listing', 'Foundation models, AI applications and consumer AI products'),
    'ZAI': (1, 'China / Hong Kong listing', 'GLM foundation models and enterprise/consumer AI services'),
    'MISTRAL': (1, 'France', 'European foundation models and enterprise AI deployment'),
    'SCALE': (1, 'United States', 'AI data, evaluation and model-development services'),
    'DATABRICKS': (1, 'United States', 'Enterprise data infrastructure and AI model/application platform'),
    'COHERE': (1, 'Canada', 'Enterprise foundation models and sovereign AI software'),
    'ALEPH_ALPHA': (1, 'Germany', 'Enterprise and sovereign AI systems'),
    'PERPLEXITY': (1, 'United States', 'AI search and consumer/enterprise distribution'),
    'DEEPSEEK': (1, 'China', 'Foundation-model research and open model competition'),
    'BYTEDANCE': (1, 'China / global operations', 'Consumer platforms and Seed/Doubao model development'),
    'GROQ': (2, 'United States', 'Inference processors and GroqCloud compute services'),
    'G42': (1, 'United Arab Emirates', 'AI investment, sovereign infrastructure and model/customer ecosystem'),
    'FLUIDSTACK': (2, 'Global infrastructure', 'AI cloud and data-center infrastructure partner'),
    'OPENAI': (1, 'United States', 'Foundation models, ChatGPT and AI deployment platform'),
    'ANTHROPIC': (1, 'United States', 'Claude foundation models and enterprise AI services'),
}

# Graph aggregates and legal subsidiaries must not inherit a public ticker just
# because a parent is listed. Unknown means listing status was not verified.
GRAPH_METADATA = {
    'SBG_NOTE_INVESTORS': ('group', 1, 'Multi-party financing', 'SoftBank senior-note investors', None,
                          'Aggregate debt investors; individual purchasers are not identified. This is not a separately listed company.'),
    'SOLIDIGM': ('subsidiary', 2, 'United States / SK hynix group', 'Enterprise SSD and data-center storage supplier', 'SKHYNIX',
                 'Solidigm is a subsidiary of SK hynix; it has no separate listed ticker in this registry.'),
    'CORZ': ('public', 2, 'United States listing', 'Data-center infrastructure and contracted AI hosting capacity', None, ''),
    'GLXY': ('public', 2, 'United States listing', 'Digital-asset and AI data-center infrastructure group', None, ''),
    'DB': ('public', 3, 'Germany / United States ADR listing', 'Bank financing for AI infrastructure projects', None, ''),
    'MS': ('public', 3, 'United States listing', 'Bank and institutional financing for AI infrastructure', None, ''),
    'MUFG': ('subsidiary', 3, 'Japan', 'MUFG Bank: named bank providing project debt', 'MUFG_GROUP',
             'The named lending counterparty is MUFG Bank, not the quoted holding company. MUFG is the holding-company stock symbol; bank figures must not be inferred from that quote.'),
    'LENDERS_CRWV': ('group', 2, 'Multi-party financing', 'CoreWeave financing consortium', None, 'A consortium label, not one issuer or a separate stock.'),
    'LENDERS_NBIS': ('group', 2, 'Multi-party financing', 'Nebius secured-lending consortium', None, 'A consortium label, not one issuer or a separate stock.'),
    'CRWV_VENDOR_FINANCE': ('group', 2, 'Undisclosed counterparties', 'CoreWeave OEM and software financing counterparties', None, 'Aggregate disclosed financing providers; individual issuers are not identified.'),
    'BROOKFIELD': ('group', 3, 'Global managed capital', 'Brookfield group and managed infrastructure funds', None, 'The graph aggregates group/fund activity. Do not assign BN or BAM to every contracting fund.'),
    'OAKTREE': ('group', 3, 'Global managed capital', 'Oaktree-managed project-equity capital', None, 'Managed-capital aggregate; no standalone listed security is assigned to this graph label.'),
    'BLOOM_PROJECTS': ('group', 3, 'Project portfolio', 'Brookfield–Bloom fuel-cell project portfolio', None, 'Project-financing aggregate, not a listed issuer or reported payment to Bloom.'),
    'NEBIUS_POWER_PROJECT': ('group', 3, 'United States project', 'IDF-led Nebius power project', None, 'Project-financing vehicle/aggregate, not an independently quoted company.'),
    'CHAIN_ELECTRIC': ('unknown', 3, 'United States project evidence', 'Named electrical-construction contractor', None, 'Relationships are sourced; independent listing/ownership status has not been separately verified.'),
    'HGA': ('unknown', 3, 'United States project evidence', 'Hunt, Guillot and Associates engineering/construction services', None, 'Relationships are sourced; independent listing/ownership status has not been separately verified.'),
    'RC_BORING': ('unknown', 3, 'United States project evidence', 'Named boring/construction contractor', None, 'Relationships are sourced; independent listing/ownership status has not been separately verified.'),
    'IDF': ('unknown', 3, 'United States project evidence', 'Industrial Development Funding project development and finance', None, 'Relationships are sourced; independent listing/ownership status has not been separately verified.'),
    'SBENERGY': ('unknown', 3, 'United States infrastructure', 'Data-center campus, power and infrastructure counterparty', None, 'Do not equate the project counterparty with separately listed SoftBank Group; listing/ownership status is not independently re-audited here.'),
    'MARKETECH': ('public', 3, 'Taiwan listing', 'Semiconductor-facility engineering and construction', None, ''),
}

IDENTITY_SOURCES = {
    'solidigm_parent': {'title': 'Solidigm FAQs: subsidiary of SK hynix', 'url': 'https://www.solidigm.com/support/faqs.html', 'date': None},
    'mufg_bank_parent': {'title': 'MUFG Bank company profile and shareholder', 'url': 'https://www.bk.mufg.jp/kigyou/profile.html', 'date': None},
    'mufg_holding': {'title': 'Mitsubishi UFJ Financial Group corporate overview', 'url': 'https://www.mufg.jp/english/profile/overview/index.html', 'date': None},
}


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def unique(values):
    seen = set(); result = []
    for value in values:
        if not value:
            continue
        key = value.casefold()
        if key not in seen:
            seen.add(key); result.append(value)
    return result


def financial_tier(company):
    if company['sector'] in ['Cloud & platforms', 'Software & applications']:
        return 1
    if company['sector'] in ['Chips & memory', 'Chipmaking & design', 'Networking & servers']:
        return 2
    return 3


def listing_region(ticker):
    for suffix, region in {'.KS':'South Korea listing', '.TW':'Taiwan listing', '.PA':'France listing',
                           '.DE':'Germany listing', '.SW':'Switzerland listing', '.HK':'Hong Kong listing',
                           '.T':'Japan listing', '.AS':'Netherlands listing'}.items():
        if ticker.endswith(suffix):
            return region
    return 'United States listing / global operations'


def build(root: Path = ROOT):
    financial = read(root/'dist/data.json')
    circulation = read(root/'dist/circulation.json')
    core = read(root/'scripts/research/coverage-core.json')
    downstream = read(root/'scripts/research/coverage-downstream.json')
    supplement = read(root/'scripts/research/coverage-supplement.json')
    companies = financial['companies']
    graph_nodes = circulation['nodes']
    graph_by_ticker = {n['ticker']: n for n in graph_nodes if n.get('ticker') and n['id'] != 'MUFG'}
    graph_by_id = {n['id']: n for n in graph_nodes}
    sources = {}; entities = {}; ticker_ids = {}

    def source(bucket, identifier, item):
        key = f'cover_{bucket}_{identifier}'
        normalized = {'title': item.get('title') or item.get('label') or 'Primary research source',
                      'url': item['url'], 'date': item.get('date')}
        if item.get('dateKind'): normalized['dateKind'] = item['dateKind']
        if key in sources and sources[key] != normalized:
            raise ValueError('Conflicting source id '+key)
        sources[key] = normalized
        return key

    source_maps = {}
    for bucket, raw in [('core',core['sources']),('downstream',downstream['sources']),
                        ('circulation',circulation['sources']),('identity',IDENTITY_SOURCES),('supplement',supplement['sources'])]:
        source_maps[bucket] = {sid: source(bucket,sid,item) for sid,item in raw.items()}
    graph_sources = collections.defaultdict(list)
    for edge in circulation['edges']:
        for node_id in [edge['from'],edge['to']]:
            graph_sources[node_id].extend(source_maps['circulation'][s] for s in edge['sourceIds'])

    def put(entity):
        ticker = entity['ticker']
        if ticker and ticker in ticker_ids and ticker_ids[ticker] != entity['id']:
            raise ValueError(f'Duplicate issuer {ticker}: {ticker_ids[ticker]} and {entity["id"]}')
        if ticker:
            ticker_ids[ticker] = entity['id']
        entity['aliases'] = unique([entity['name'],ticker,*entity['aliases']])
        entity['sourceIds'] = unique(entity['sourceIds'])
        entities[entity['id']] = entity

    for company in companies:
        ticker = company['ticker']; graph = graph_by_ticker.get(ticker)
        entity_id = graph['id'] if graph else ticker
        filed_by_accession = {part.get('accn'): part.get('filed') for metric in company['metrics'].values()
                              for part in metric.get('components',[]) if part.get('accn')}
        source_ids = []
        for i, item in enumerate(company['sources']):
            item = dict(item)
            accession = re.search(r'(\d{10}-\d{2}-\d{6})',item['url'])
            if accession and filed_by_accession.get(accession.group(1)):
                item['date'] = filed_by_accession[accession.group(1)]
            source_ids.append(source('financial',ticker+'_'+str(i+1),item))
        note = ('Saved financial profile is available; individual profit, cash-flow, valuation and debt fields '
                'retain their own coverage and dated source definitions.')
        if ticker == 'TEL':
            note += ' Exact US ticker TEL means TE Connectivity; Tokyo Electron uses 8035.T and shares TEL only as a name abbreviation.'
        if ticker == 'GOOGL':
            note += ' GOOG and GOOGL are share classes of Alphabet, not separate issuers in this directory.'
        put({'id':entity_id,'name':company['name'],'ticker':ticker,
             'aliases':FINANCIAL_ALIASES.get(ticker,[])+([graph['name']] if graph else []),
             'listingStatus':'public','researchStatus':'financial','financialTicker':ticker,
             'parentId':None,'tier':financial_tier(company),'role':company['role'],
             'note':note,'region':listing_region(ticker),'sourceIds':source_ids+graph_sources[entity_id]})

    for node in graph_nodes:
        entity_id = node['id']
        if entity_id in entities:
            continue
        status,tier,region,role,parent,note = GRAPH_METADATA.get(entity_id,
            ('public' if node.get('ticker') or node.get('public') else 'unknown',
             node.get('tier',2),'Not separately classified',node.get('role') or node['name'],None,
             'Financial metrics are not part of the saved financial snapshot.'))
        ticker = None if status in ['subsidiary','group','unknown'] else node.get('ticker')
        put({'id':entity_id,'name':node['name'],'ticker':ticker,'aliases':[],
             'listingStatus':status,'researchStatus':'relationships','financialTicker':None,
             'parentId':parent,'tier':tier,'role':role,'note':note,
             'region':region,'sourceIds':graph_sources[entity_id]})

    # Correct the existing bank-vs-listed-holding-company identity without changing graph IDs.
    if 'MUFG' in entities:
        entities['MUFG']['sourceIds'].append(source_maps['identity']['mufg_bank_parent'])
        put({'id':'MUFG_GROUP','name':'Mitsubishi UFJ Financial Group','ticker':'MUFG',
             'aliases':['MUFG Group','Mitsubishi UFJ'],'listingStatus':'public','researchStatus':'ecosystem',
             'financialTicker':None,'parentId':None,'tier':3,'role':'Listed financial holding company and parent of MUFG Bank',
             'note':'The circulation graph names MUFG Bank as the lender. Parent shares are listed, but no parent financial profile is added by this registry.',
             'region':'Japan / United States ADR listing','sourceIds':[source_maps['identity']['mufg_holding'],source_maps['identity']['mufg_bank_parent']]})
    if 'SOLIDIGM' in entities:
        entities['SOLIDIGM']['sourceIds'].append(source_maps['identity']['solidigm_parent'])

    for item in core['entities']:
        ticker = item.get('ticker')
        graph = graph_by_ticker.get(ticker) if ticker else graph_by_id.get(item['id'])
        entity_id = graph['id'] if graph else ticker_ids.get(ticker,item['id'])
        # The parent and its subsidiary keep explicit identity IDs, not product tickers.
        if item['id'] in ['SPCX','CURSOR']:
            entity_id = item['id']
        old = entities.get(entity_id,{})
        tier,region,role = CORE_METADATA[item['id']]
        status = 'unlisted' if item['listingStatus']=='unlisted-context' else item['listingStatus']
        source_ids = [source_maps['core'][s] for s in item['sourceIds']]
        put({'id':entity_id,'name':item['name'],'ticker':ticker,'aliases':old.get('aliases',[])+item.get('aliases',[]),
             'listingStatus':status,'researchStatus':('financial' if old.get('financialTicker') else
                 'relationships' if entity_id in graph_by_id else 'ecosystem'),
             'financialTicker':old.get('financialTicker'),'parentId':item.get('parentId'),
             'tier':tier,'role':role,'note':item['note'],'region':region,
             'sourceIds':old.get('sourceIds',[])+source_ids})

    additions = downstream['recommendedPublicAdditions']+downstream.get('nextAddition',[])
    for item in additions:
        ticker = item['ticker']; graph = graph_by_ticker.get(ticker)
        entity_id = graph['id'] if graph else ticker_ids.get(ticker,ticker)
        old = entities.get(entity_id,{})
        tier = 1 if ticker in ['0700.HK','9984.T'] else 2
        note = 'Financial research pending; no profit, cash-flow, debt, valuation or stock-return metrics are added here.'
        if item.get('notes'):
            note += ' '+item['notes']
        put({'id':entity_id,'name':item['name'],'ticker':ticker,'aliases':old.get('aliases',[])+item.get('aliases',[]),
             'listingStatus':'public','researchStatus':('financial' if old.get('financialTicker') else
                 'relationships' if entity_id in graph_by_id else 'ecosystem'),
             'financialTicker':old.get('financialTicker'),'parentId':None,'tier':tier,
             'role':item['role'],'note':note,'region':item['region'],
             'sourceIds':old.get('sourceIds',[])+[source_maps['downstream'][s] for s in item['sourceIds']]})
    for item in downstream['alreadyPresent']:
        entity = entities[ticker_ids[item['ticker']]]
        entity['aliases'] = unique(entity['aliases']+item.get('aliases',[]))

    for item in supplement['entities']:
        ticker = item.get('ticker')
        entity_id = ticker_ids.get(ticker,item['id']) if ticker else item['id']
        old = entities.get(entity_id,{})
        put({'id':entity_id,'name':item['name'],'ticker':ticker,
             'aliases':old.get('aliases',[])+item.get('aliases',[]),
             'listingStatus':'unlisted' if item['listingStatus']=='unlisted-context' else item['listingStatus'],
             'researchStatus':'financial' if old.get('financialTicker') else 'relationships' if entity_id in graph_by_id else 'ecosystem',
             'financialTicker':old.get('financialTicker'),'parentId':item.get('parentId'),
             'tier':item['tier'],'role':item['role'],'note':item.get('note',''),
             'region':item['region'],'sourceIds':old.get('sourceIds',[])+[source_maps['supplement'][sid] for sid in item['sourceIds']]})

    result = sorted(entities.values(),key=lambda entity:(entity['name'].casefold(),entity['id']))
    for entity in result:
        entity['sourceIds'] = unique(entity['sourceIds'])
        if not entity['sourceIds']:
            raise ValueError('Entity has no source evidence: '+entity['id'])
        if entity['parentId'] and entity['parentId'] not in entities:
            raise ValueError('Missing parent: '+entity['id'])
    status_counts = dict(sorted(collections.Counter(e['listingStatus'] for e in result).items()))
    research_counts = dict(sorted(collections.Counter(e['researchStatus'] for e in result).items()))
    public_gaps = [e['id'] for e in result if e['listingStatus']=='public' and not e['financialTicker']]
    audit = {
        'totalEntities':len(result),'financialCompanies':len(companies),
        'publicListedEntities':status_counts.get('public',0),'publicAwaitingFinancials':len(public_gaps),
        'circulationNodes':len(graph_nodes),'circulationRelationships':len(circulation['edges']),
        'circulationCases':len(circulation['cases']),'listingStatusCounts':status_counts,
        'researchStatusCounts':research_counts,'publicFinancialGaps':public_gaps,
        'sourceCount':len(sources),'reviewedCoreRecords':len(core['entities']),
        'reviewedDownstreamAdditions':len(additions),'reviewedSupplementAdditions':len(supplement['entities']),
        'aliasAmbiguities':[{'alias':'TEL','exactTickerId':ticker_ids['TEL'],
                            'otherEntityIds':[ticker_ids['8035.T']],
                            'note':'Exact ticker matching must rank TE Connectivity first; Tokyo Electron remains a labeled alias match.'}],
        'definitions':{
            'financial':'Links to an existing saved financial profile; not a claim that every metric is available.',
            'relationships':'Has a node in the curated circulation graph but no saved financial profile.',
            'ecosystem':'Sourced entity coverage without a saved financial profile or current graph node.',
            'unlisted':'No independently quoted stock is established by the reviewed evidence at the cutoff.',
            'unknown':'Listing/ownership status not independently established; missing financials do not imply private ownership.',
            'region':'Regional context or listing location, as labeled; not an assertion of revenue geography.',
            'sourceDates':'Dates retain their documented precision; dateKind distinguishes publication dates, reporting periods and undated issuer pages. Null means no date was established.'},
        'limits':[
            'Coverage is curated, not an exhaustive ranking of worldwide AI companies.',
            'The separate 100-company financial snapshot and its scenarios are unchanged.',
            'New public listings can lack comparable one-year and since-2023 returns; registry presence cannot qualify a hidden champion.',
            'SPCX is the quoted parent; xAI/Grok and Cursor do not add separate stock counts.',
            'Groq is separate from Grok; pending Cohere/Aleph Alpha combination does not merge entities.',
            'Subsidiaries, fund groups and projects must not be added to parent financial totals.',
            'Circulation membership describes documented relationships, not proof of tracked identical cash.'
        ]}
    return {'asOf':AS_OF,'reviewedAt':REVIEWED_AT,'entities':result,'sources':sources,'audit':audit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dist/coverage.json')
    args = parser.parse_args()
    data = build()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(data['audit'],ensure_ascii=False))


if __name__=='__main__':
    main()
