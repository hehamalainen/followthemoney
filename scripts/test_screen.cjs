// Exercise real screen functions without a browser or network.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const root=path.resolve(__dirname,'..'),data=JSON.parse(fs.readFileSync(path.join(root,'dist/data.json'))),s=JSON.parse(fs.readFileSync(path.join(root,'dist/scenarios.json')));
const ctx=vm.createContext({fixture:s,val:(c,k)=>c.metrics[k]?.value??null});
vm.runInContext(fs.readFileSync(path.join(root,'dist/scenarios.js'),'utf8')+'\nscenariosData=fixture;',ctx);
function hidden(c,i=0,window='both',gap=0){ctx.company=c;vm.runInContext(`recognitionWindow=${JSON.stringify(window)};recognitionGap=${gap}`,ctx);return vm.runInContext(`Boolean(hiddenInScenario(company,${i}))`,ctx)}
function clone(t){return structuredClone(data.companies.find(c=>c.ticker===t))}
assert.deepEqual(data.companies.filter(c=>hidden(c)).map(c=>c.ticker).sort(),['SNPS','TEL']);
assert.deepEqual(data.companies.filter(c=>hidden(c,2)).map(c=>c.ticker).sort(),['CRM','WDAY']);
assert.equal(data.companies.filter(c=>hidden(c,1)).length,7);
assert.equal(hidden(clone('AVGO'),0),false); // A recent laggard that already joined the boom.
assert.equal(hidden(clone('AVGO'),0,'recent'),true);
for(const mutate of [c=>c.stale=true,c=>c.metrics.net.value=0,c=>delete c.metrics.fcf,c=>c.metrics.fcf.value=-1,c=>c.revenueGrowth=9.99,c=>c.market.excess=0,c=>c.market.boomExcess=0,c=>c.market.boomComparable=false]) {const c=clone('TEL');mutate(c);assert.equal(hidden(c),false)}
const boundary=clone('TEL');boundary.revenueGrowth=10;assert.equal(hidden(boundary),true);
assert.equal(hidden(clone('TEL'),0,'both',-20),false);
console.log('Screen gates verified: fresh evidence, positive profit/cash, growth boundary, strict lag boundaries, two windows, missing data, and scenario-specific shortlists.');
