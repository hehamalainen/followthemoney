'use strict';
/* The directory records presence and research coverage separately from financial results. */
window.MoneyCoverage = (() => {
  let records = [], sources = {}, byId = new Map(), index = [], root = null, dialog = null;
  const state = {query: '', listing: 'all', research: 'all', tier: 'all'};
  const listingLabels = {public: 'Public company', unlisted: 'Unlisted company', subsidiary: 'Subsidiary', group: 'Group / project', unknown: 'Listing not verified'};
  const researchLabels = {financial: 'Financial profile', relationships: 'Relationships researched', ecosystem: 'Ecosystem mapped'};
  const tierLabels = {1: '1 · Models & platforms', 2: '2 · Compute & chips', 3: '3 · Physical infrastructure'};
  const quickSearches = [['Meta', 'META'], ['Apple', 'AAPL'], ['Intel', 'INTC'], ['SpaceX / xAI', 'SPCX'], ['Tesla', 'TSLA'], ['Qualcomm', 'QCOM'], ['Tencent', 'Tencent'], ['SoftBank', 'SoftBank Group']];
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const normalize = value => String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');
  const financial = item => item.researchStatus === 'financial' && Boolean(item.financialTicker);
  const safeUrl = value => /^https?:\/\//i.test(String(value ?? '')) ? String(value) : null;

  function setData(data) {
    records = Array.isArray(data?.entities) ? data.entities.map(item => ({...item, aliases: Array.isArray(item.aliases) ? [...item.aliases] : [], sourceIds: Array.isArray(item.sourceIds) ? [...item.sourceIds] : []})) : [];
    sources = data?.sources && typeof data.sources === 'object' ? {...data.sources} : {};
    byId = new Map(records.map(item => [item.id, item]));
    index = records.map((item, order) => ({item, order, ticker: normalize(item.ticker), name: normalize(item.name), id: normalize(item.id), aliases: item.aliases.map(normalize).filter(Boolean), role: normalize(item.role)}));
  }

  function find(term, limit = Infinity) {
    const query = normalize(term);
    const cap = Number.isFinite(Number(limit)) ? Math.max(0, Math.floor(Number(limit))) : Infinity;
    if (!query) return records.slice(0, cap);
    return index.map(entry => {
      let rank = Infinity;
      if (entry.ticker === query) rank = 0;
      else if (entry.name === query) rank = 1;
      else if (entry.aliases.includes(query)) rank = 2;
      else if (entry.id === query) rank = 3;
      else if (entry.ticker.startsWith(query) || entry.name.startsWith(query) || entry.aliases.some(alias => alias.startsWith(query))) rank = 4;
      else if ([entry.ticker, entry.name, entry.id, entry.role, ...entry.aliases].some(value => value.includes(query))) rank = 5;
      return {entry, rank};
    }).filter(match => Number.isFinite(match.rank)).sort((a, b) => a.rank - b.rank || a.entry.order - b.entry.order).slice(0, cap).map(match => match.entry.item);
  }

  function entity(id) { return byId.get(id) || null; }

  function coverageNote(item) {
    if (financial(item)) return 'Financial profile available';
    if (item.listingStatus === 'public') return 'Financial analysis not yet added';
    if (item.listingStatus === 'unlisted') return 'No listed share price';
    if (item.listingStatus === 'subsidiary') return 'Not an independent listed stock';
    if (item.listingStatus === 'group') return 'No single stock for this group or project';
    return 'Listing status has not been verified';
  }

  function stats() {
    return {total: records.length, financial: new Set(records.filter(financial).map(item => item.financialTicker)).size, public: records.filter(item => item.listingStatus === 'public').length};
  }

  function init() {
    const target = document.querySelector('#coverage-view');
    if (!target) return;
    if (root === target && root.querySelector('#cv-query')) return;
    root = target;
    root.innerHTML = `<div class="cv-heading"><div><div class="cv-eyebrow">THE AI ECONOMY / COMPANY DIRECTORY</div><h1>The AI players.<br><em>Clear coverage.</em></h1><p>Find the platforms, suppliers and capital behind AI.<br>See who is included, what is researched, and where they connect.</p></div><div class="cv-summary" aria-label="Directory coverage"></div></div>
      <div class="cv-explainer"><span class="cv-explainer-mark" aria-hidden="true">↗</span><p><strong>Being in the map is different from having a financial profile.</strong> The directory also includes companies awaiting financial research, unlisted businesses, subsidiaries and project groups. Missing financial data does not mean a company is losing money.</p></div>
      <div class="cv-quick"><span>Start with</span>${quickSearches.map(([label, query]) => `<button type="button" data-cv-query="${escape(query)}">${escape(label)}</button>`).join('')}</div>
      <form class="cv-filters" role="search" aria-label="Search the AI company directory"><label class="cv-search-label" for="cv-query">Company, ticker or alias<input id="cv-query" type="search" autocomplete="off" placeholder="Try Meta, Apple, Intel, xAI or a ticker" aria-controls="cv-results"></label><label for="cv-listing">Listing<select id="cv-listing"><option value="all">All listing statuses</option>${Object.entries(listingLabels).map(([key, label]) => `<option value="${key}">${label}</option>`).join('')}</select></label><label for="cv-research">Research<select id="cv-research"><option value="all">All research coverage</option>${Object.entries(researchLabels).map(([key, label]) => `<option value="${key}">${label}</option>`).join('')}</select></label><label for="cv-tier">Supply-chain tier<select id="cv-tier"><option value="all">All tiers</option>${Object.entries(tierLabels).map(([key, label]) => `<option value="${key}">${label}</option>`).join('')}</select></label><button type="button" class="cv-reset">Reset</button></form>
      <div class="cv-results-header"><p id="cv-result-count" role="status" aria-live="polite" aria-atomic="true"></p><span>Listing status and research coverage are separate.</span></div><div id="cv-results" class="cv-results"></div><p class="cv-footnote">A curated directory, not a market-cap ranking. Tier describes an economic role, not company quality. Parent companies, subsidiaries and project groups may overlap; their finances should not be added together.</p>`;
    root.querySelector('.cv-filters').addEventListener('submit', event => event.preventDefault());
    root.querySelector('#cv-query').addEventListener('input', event => {state.query = event.target.value; render();});
    for (const field of ['listing', 'research', 'tier']) root.querySelector('#cv-' + field).addEventListener('change', event => {state[field] = event.target.value; render();});
    root.querySelector('.cv-reset').addEventListener('click', () => {reset(); render(); root.querySelector('#cv-query').focus();});
    root.querySelectorAll('[data-cv-query]').forEach(button => button.addEventListener('click', () => open(button.dataset.cvQuery)));
    root.querySelector('#cv-results').addEventListener('click', event => {const button = event.target.closest('[data-cv-show]'); if (button) show(button.dataset.cvShow);});
    render();
  }

  function reset(query = '') {state.query = String(query ?? ''); state.listing = state.research = state.tier = 'all';}

  function render() {
    if (!root) {init(); return;}
    const counts = stats();
    root.querySelector('.cv-summary').innerHTML = `<div><strong>${counts.total}</strong><span>players in the directory</span></div><div><strong>${counts.financial}</strong><span>public financial profiles</span></div><p>${counts.public} public companies · ${counts.public - counts.financial} awaiting financial analysis</p>`;
    for (const field of ['query', 'listing', 'research', 'tier']) root.querySelector('#cv-' + field).value = state[field];
    const matches = find(state.query).filter(item => (state.listing === 'all' || item.listingStatus === state.listing) && (state.research === 'all' || item.researchStatus === state.research) && (state.tier === 'all' || String(item.tier) === state.tier));
    root.querySelector('#cv-result-count').textContent = `${matches.length} ${matches.length === 1 ? 'player' : 'players'}${state.query.trim() ? ` matching “${state.query.trim()}”` : ''} · ${counts.total} in the directory`;
    root.querySelectorAll('[data-cv-query]').forEach(button => button.setAttribute('aria-pressed', normalize(button.dataset.cvQuery) === normalize(state.query)));
    root.querySelector('#cv-results').innerHTML = matches.length ? matches.map(card).join('') : `<div class="cv-empty"><h2>No matching players</h2><p>Try a company name, ticker or alias, or reset the filters to search the whole directory.</p></div>`;
  }

  function card(item) {
    const researched = financial(item), parent = entity(item.parentId);
    return `<article class="cv-card"><div class="cv-card-top"><span class="cv-symbol">${escape(item.ticker || '—')}</span><span class="cv-listing cv-listing-${escape(item.listingStatus)}">${escape(listingLabels[item.listingStatus] || listingLabels.unknown)}</span></div><h2><button type="button" class="cv-name" data-cv-show="${escape(item.id)}">${escape(item.name)}</button></h2><p class="cv-role">${escape(item.role || 'Role has not yet been described.')}</p><p class="cv-context">${escape(item.region || 'Region not specified')}${item.tier ? ` · Tier ${escape(item.tier)}` : ''}${parent ? ` · Part of ${escape(parent.name)}` : ''}</p><div class="cv-card-footer"><div><span class="cv-research${researched ? ' cv-researched' : ''}">${escape(researchLabels[item.researchStatus] || 'Coverage pending')}</span><p>${escape(coverageNote(item))}</p></div><button type="button" class="cv-open" data-cv-show="${escape(item.id)}" aria-label="${escape((researched ? 'Open financial profile for ' : 'Explore ') + item.name)}">${researched ? 'Financials' : 'Explore'} <span aria-hidden="true">↗</span></button></div></article>`;
  }

  function open(query = '') {
    reset(query);
    if (typeof setView === 'function') setView('coverage');
    init(); render();
    root?.querySelector('#cv-query')?.focus({preventScroll: true});
  }

  function ensureDialog() {
    if (dialog?.isConnected) return dialog;
    dialog = document.createElement('dialog');
    dialog.className = 'cv-dialog';
    dialog.setAttribute('aria-labelledby', 'cv-dialog-title');
    document.body.appendChild(dialog);
    dialog.addEventListener('click', event => {
      if (event.target.closest('[data-cv-close]')) dialog.close();
      const parentButton = event.target.closest('[data-cv-parent]');
      if (parentButton) {dialog.close(); show(parentButton.dataset.cvParent);}
      const networkButton = event.target.closest('[data-cv-network]');
      if (networkButton) {
        dialog.close();
        if (typeof setView === 'function') setView('universe');
        window.MoneyUniverse?.selectNode(networkButton.dataset.cvNetwork);
      }
    });
    return dialog;
  }

  function show(id) {
    const item = entity(id);
    if (!item) return false;
    if (financial(item) && typeof openCompany === 'function') {openCompany(item.financialTicker); return true;}
    const panel = ensureDialog(), parent = entity(item.parentId);
    const links = [...new Map(item.sourceIds.map(key => sources[key]).filter(source => source && safeUrl(source.url)).map(source => [source.url, source])).values()];
    panel.innerHTML = `<button type="button" class="cv-dialog-close" data-cv-close aria-label="Close company details">×</button><div class="cv-eyebrow">COMPANY DIRECTORY${item.ticker ? ' / ' + escape(item.ticker) : ''}</div><h2 id="cv-dialog-title">${escape(item.name)}</h2><p class="cv-dialog-role">${escape(item.role || '')}</p><dl class="cv-status-grid"><div><dt>Listing status</dt><dd>${escape(listingLabels[item.listingStatus] || listingLabels.unknown)}</dd></div><div><dt>Research coverage</dt><dd>${escape(researchLabels[item.researchStatus] || 'Coverage pending')}</dd></div><div><dt>Region</dt><dd>${escape(item.region || 'Not specified')}</dd></div><div><dt>Economic role</dt><dd>${escape(tierLabels[item.tier] || 'Tier not assigned')}</dd></div></dl><div class="cv-coverage-note"><strong>${escape(coverageNote(item))}</strong><p>${financial(item) ? 'The financial profile is temporarily unavailable in this view.' : item.listingStatus === 'public' ? 'This company is included in the ecosystem. Its profit, cash flow, valuation and debt have not yet been added to the financial comparison.' : item.listingStatus === 'unlisted' ? 'This entity can participate in documented money flows without having publicly traded shares.' : item.listingStatus === 'subsidiary' ? 'A parent may be publicly traded; that does not give this subsidiary its own listed stock or standalone financial profile.' : item.listingStatus === 'group' ? 'This entry represents a group, project or aggregate counterparty. It should not be treated as a single listed security.' : 'The directory does not infer a public or private listing from the absence of a ticker.'}</p></div>${item.note ? `<h3>What to know</h3><p>${escape(item.note)}</p>` : ''}${parent ? `<h3>Parent or associated group</h3><button type="button" class="cv-parent" data-cv-parent="${escape(parent.id)}">${escape(parent.name)}${parent.ticker ? ' · ' + escape(parent.ticker) : ''} <span aria-hidden="true">↗</span></button>` : ''}${item.aliases.length ? `<h3>Also searchable as</h3><p class="cv-aliases">${item.aliases.map(escape).join(' · ')}</p>` : ''}<button type="button" class="cv-network" data-cv-network="${escape(item.id)}">Show in money network <span aria-hidden="true">↗</span></button><h3>Sources</h3><div class="cv-sources">${links.map(source => `<a href="${escape(safeUrl(source.url))}" target="_blank" rel="noopener noreferrer">${escape(source.title || source.label || 'Source')}${source.date ? `<small>${escape(source.date)}</small>` : ''}<span aria-hidden="true">↗</span></a>`).join('') || '<p>No source record is attached to this directory entry yet.</p>'}</div>`;
    if (!panel.open) panel.showModal();
    panel.scrollTop = 0;
    return true;
  }

  return {setData, init, render, open, find, entity, show};
})();
