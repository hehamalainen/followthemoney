'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const {createRealAppContext}=require('./test_support.cjs');
const root=path.resolve(__dirname,'..');
const input=Object.fromEntries(['data','scenarios','valuation','circulation','coverage'].map(n=>[n,JSON.parse(fs.readFileSync(path.join(root,'dist',n+'.json')))]));
const {context,elements}=createRealAppContext(root,input);
const run=source=>vm.runInContext(source,context);
for(const [n,app,pdf] of [[0,'$0','USD 0'],[-0,'$0','USD 0'],[12,'$12','USD 12.00'],[-12,'−$12','USD -12.00'],[1234,'$1.23K','USD 1.23K'],[1e6,'$1M','USD 1.00M'],[1e9,'$1B','USD 1.00B'],[1e12,'$1T','USD 1.00T']]){
 context.amount=n;assert.equal(run('money(amount)'),app);assert.equal(run('reportCurrency(amount)'),pdf);
}
for(const n of [null,undefined,NaN,Infinity,-Infinity,'0']){
 context.amount=n;assert.equal(run('money(amount)'),'—');assert.equal(run('reportCurrency(amount)'),'Unavailable');
}
assert.equal(run("money(0,'EUR')"),'€0');assert.equal(run("reportCurrency(0,'JPY')"),'JPY 0');
const invalid=['javascript:alert(1)','JaVaScRiPt:alert(1)','data:text/html,test','file:///tmp/a','mailto:a@example.com','//example.com','/relative','https://','https://example.com/\nattack','https://example.com/ a',' https://example.com',null,undefined];
for(const raw of invalid){
 context.raw=raw;assert.equal(run('safeSourceUrl(raw)'),null);
 assert.ok(!run("sourceAnchor(raw,'<test>')").includes('<a '));
 run(`circulationData.sources.test={title:'bad',url:raw};scenariosData.sources.test={title:'bad',url:raw};`);
 for(const call of ["sourceMarkup(['test'])","sourceLink('test')"])assert.ok(!run(call).includes('<a '));
 run(`valuationData.companies.MDB.sources=[{label:'bad',url:raw}];companies.find(c=>c.ticker==='MDB').sources=[{label:'bad',url:raw}];companies.find(c=>c.ticker==='MDB').market.source=raw;companies.find(c=>c.ticker==='MDB').market.benchmarkSource=raw;`);
 for(const call of ["valuationDetail(companies.find(c=>c.ticker==='MDB'))","marketDetail(companies.find(c=>c.ticker==='MDB'))"]){
  const html=run(call);assert.ok(!/href\s*=/.test(html),call);
 }
 run("openCompany('MDB')");assert.ok(!elements.get('#company-content').innerHTML.includes('href="javascript:'));
}
for(const raw of ['https://example.com/path?a=1&b=2','http://example.com/','HTTPS://example.com/a']){
 context.raw=raw;assert.equal(run('safeSourceUrl(raw)'),new URL(raw).href);
 const html=run("sourceAnchor(raw,'<unsafe label>')");assert.ok(html.includes('<a href="'));assert.ok(html.includes('&lt;unsafe label&gt;'));assert.ok(!html.includes('<unsafe label>'));
}
// Check every active source family in the committed inputs, not only fixtures.
const saved=Object.fromEntries(['data','scenarios','valuation','circulation','coverage'].map(n=>[n,JSON.parse(fs.readFileSync(path.join(root,'dist',n+'.json')))]));
const urls=[...saved.data.companies.flatMap(c=>[...c.sources.map(s=>s.url),c.market.source,c.market.benchmarkSource]),...Object.values(saved.valuation.companies).flatMap(v=>v.sources.map(s=>s.url)),...['scenarios','circulation','coverage'].flatMap(k=>Object.values(saved[k].sources).map(s=>s.url))];
for(const raw of urls){context.raw=raw;assert.ok(run('safeSourceUrl(raw)'),`Invalid committed source URL: ${raw}`);}
console.log('Display checks passed: zero/small/missing amounts, production source renderers, unsafe schemes and committed source URLs.');
