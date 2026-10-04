'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
let opened = null;
const context = vm.createContext({window: {}, openCompany: ticker => {opened = ticker;}});
Object.defineProperty(context, 'document', {get() {throw new Error('Pure directory operations must not touch the DOM');}});
vm.runInContext(fs.readFileSync(path.join(root, 'dist/coverage.js'), 'utf8'), context);
const coverage = context.window.MoneyCoverage;
const fixture = {sources: {}, entities: [
  {id: '8035.T', name: 'Tokyo Electron', ticker: '8035.T', aliases: ['TEL'], listingStatus: 'public', researchStatus: 'ecosystem', financialTicker: null},
  {id: 'TEL', name: 'TE Connectivity', ticker: 'TEL', aliases: [], listingStatus: 'public', researchStatus: 'financial', financialTicker: 'TEL'},
  {id: 'SPCX', name: 'SpaceX', ticker: 'SPCX', aliases: ['SpaceXAI', 'SpaceX / xAI', 'xAI', 'Grok'], listingStatus: 'public', researchStatus: 'relationships', financialTicker: null},
  {id: 'GROQ', name: 'Groq', ticker: null, aliases: ['GroqCloud'], listingStatus: 'unlisted', researchStatus: 'relationships', financialTicker: null},
  {id: 'AAPL', name: 'Apple', ticker: 'AAPL', aliases: ['Apple Intelligence'], listingStatus: 'public', researchStatus: 'financial', financialTicker: 'AAPL'},
  {id: 'SOLIDIGM', name: 'Solidigm', ticker: null, aliases: [], listingStatus: 'subsidiary', researchStatus: 'relationships', financialTicker: null, parentId: 'SKHYNIX'},
  {id: 'PROJECTS', name: 'AI project developers', ticker: null, aliases: [], listingStatus: 'group', researchStatus: 'relationships', financialTicker: null},
  {id: 'UNKNOWN', name: 'Unverified counterparty', ticker: null, aliases: [], listingStatus: 'unknown', researchStatus: 'ecosystem', financialTicker: null}
]};
coverage.setData(fixture);
assert.equal(coverage.find('TEL')[0].id, 'TEL', 'An exact trading symbol outranks another company’s alias');
assert.equal(coverage.find('TEL')[1].id, '8035.T');
assert.equal(coverage.find('Tokyo Electron')[0].id, '8035.T');
for (const term of ['SPCX', 'SpaceX', 'SpaceXAI', 'SpaceX / xAI', 'x-AI', 'Grok']) assert.equal(coverage.find(term)[0].id, 'SPCX', term);
assert.equal(coverage.find('groq')[0].id, 'GROQ');
assert.ok(!coverage.find('groq').some(item => item.id === 'SPCX'), 'Groq and Grok must remain distinct');
assert.equal(coverage.find(' APPLE intelligence ')[0].id, 'AAPL');
assert.equal(coverage.find('appl', 1).length, 1);
assert.equal(coverage.find('', 0).length, 0);
assert.equal(coverage.find('').length, fixture.entities.length);
assert.equal(coverage.find('no-such-player').length, 0);
assert.equal(coverage.entity('missing'), null);
assert.equal(coverage.entity('SOLIDIGM').parentId, 'SKHYNIX');
assert.equal(coverage.entity('SOLIDIGM').ticker, null);
assert.equal(coverage.entity('SPCX').researchStatus, 'relationships');
assert.equal(coverage.entity('SPCX').listingStatus, 'public', 'Public listing does not imply financial research');
assert.equal(coverage.show('AAPL'), true);
assert.equal(opened, 'AAPL', 'Financial profiles open directly without changing views or accessing the DOM');
assert.equal(coverage.show('missing'), false);
fixture.entities[0].aliases.push('mutated');
assert.equal(coverage.find('mutated').length, 0, 'setData copies aliases without mutating or retaining the input array');
coverage.setData({entities: [], sources: {}});
assert.equal(coverage.find('').length, 0, 'setData resets the previous registry');
assert.equal(coverage.entity('TEL'), null);

const registryPath = path.join(root, 'dist/coverage.json');
if (fs.existsSync(registryPath)) {
  const registry = JSON.parse(fs.readFileSync(registryPath, 'utf8'));
  const financialData = JSON.parse(fs.readFileSync(path.join(root, 'dist/data.json'), 'utf8'));
  const finance = new Set(financialData.companies.map(company => company.ticker));
  coverage.setData(registry);
  assert.equal(coverage.find('').length, registry.entities.length);
  assert.equal(new Set(registry.entities.map(item => item.id)).size, registry.entities.length, 'Directory IDs must be unique');
  for (const item of registry.entities) {
    assert.ok(['public', 'unlisted', 'subsidiary', 'group', 'unknown'].includes(item.listingStatus), `${item.id}: listing status`);
    assert.ok(['financial', 'relationships', 'ecosystem'].includes(item.researchStatus), `${item.id}: research status`);
    if (item.parentId) assert.ok(coverage.entity(item.parentId), `${item.id}: missing parent`);
    if (item.researchStatus === 'financial') assert.ok(finance.has(item.financialTicker), `${item.id}: financial link must resolve`);
    else assert.ok(!item.financialTicker, `${item.id}: pending research must not claim financial coverage`);
    for (const id of item.sourceIds || []) assert.ok(registry.sources[id], `${item.id}: missing source ${id}`);
  }
  const covered = new Set(registry.entities.filter(item => item.researchStatus === 'financial').map(item => item.financialTicker));
  assert.equal(covered.size, finance.size, 'Every saved company financial profile remains discoverable');
  for (const ticker of finance) assert.ok(covered.has(ticker), ticker);
  for (const ticker of ['META', 'AAPL', 'INTC', 'TEL']) assert.equal(coverage.find(ticker)[0]?.ticker, ticker, `Exact ticker ${ticker}`);
  for (const term of ['Microsoft','Amazon','Google','NVIDIA','Meta','Apple','Intel','SpaceX','Tesla','Qualcomm','Tencent','SoftBank','TSMC','Samsung','SK hynix','ASML','Huawei','Cerebras','Tokyo Electron','Accenture','TCS','Kioxia','SMIC','Cambricon']) {
    assert.ok(coverage.find(term).length, `Core audit checklist: ${term}`);
  }
  assert.equal(registry.audit.totalEntities, registry.entities.length);
  assert.equal(registry.audit.financialCompanies, covered.size);
  const pending = registry.entities.filter(e => e.listingStatus === 'public' && !e.financialTicker);
  assert.equal(registry.audit.publicAwaitingFinancials, pending.length);
  assert.deepEqual([...registry.audit.publicFinancialGaps].sort(), pending.map(e => e.id).sort());
  assert.equal(coverage.entity('SBG_NOTE_INVESTORS').listingStatus, 'group');
  const spacex = coverage.find('SPCX')[0];
  assert.ok(spacex, 'SpaceX listed parent is included');
  for (const term of ['SpaceX', 'xAI', 'Grok']) assert.equal(coverage.find(term)[0]?.id, spacex.id, `${term} resolves to SpaceX parent`);
  assert.notEqual(coverage.find('Groq')[0]?.id, spacex.id, 'Groq is not the Grok alias');
  console.log(`Coverage registry: ${registry.entities.length} entities, ${covered.size} linked financial profiles.`);
} else {
  console.log('Registry integration checks pending: dist/coverage.json has not been generated yet.');
}
console.log('Coverage search, identity, status and direct-financial-opening checks passed.');
