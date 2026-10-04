// Check the spatial mathematics, research screens and mode-specific camera target.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const root=path.resolve(__dirname,'..');
const read=name=>fs.readFileSync(path.join(root,'dist',name),'utf8');
const companies=JSON.parse(read('data.json')).companies;
const fixture=JSON.parse(read('scenarios.json'));
const registry=JSON.parse(read('coverage.json'));
const ctx=vm.createContext({window:{},fixture,companies,circulationData:JSON.parse(read('circulation.json')),val:(c,k)=>c.metrics[k]?.value??null});
vm.runInContext(read('coverage.js'),ctx);
ctx.window.MoneyCoverage.setData(registry);
vm.runInContext(read('scenarios.js')+'\nscenariosData=fixture;',ctx);
// Test-only access to the closure; production exports do not expose mutable state.
const source=read('universe.js').replace('return{init,setActive,',`return{__test:{
  setup(){root={querySelector:()=>({})};sync=()=>{};focusPanel=()=>{};announce=()=>{};buildNodes()},
  mode(mode){if(mode)state.mode=mode;return state.mode},target(){return state.targetCenter},
  nodeIds(){return currentNodes().map(n=>n.id)},node(id){return nodes.find(n=>n.id===id)},
  position(id){return worldPoint(currentNodes().find(n=>n.id===id))}
 },init,setActive,`);
vm.runInContext(source,ctx);
const u=ctx.window.MoneyUniverse,near=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,`${a} != ${b}`);
for(let lens=0;lens<3;lens++){
  const p=fixture.scenarios[lens].path;
  p.forEach((v,i)=>near(u.scenarioValue(lens,2026+i),v));
  near(u.scenarioValue(lens,2027.5),(p[1]+p[2])/2);
  near(u.scenarioValue(lens,2020),p[0]);near(u.scenarioValue(lens,2040),p[4]);
}
const expected=[['SNPS','TEL'],['SNPS','NOW','CRM','MDB','TEL','WDAY','PATH'],['CRM','WDAY']];
for(let i=0;i<3;i++)assert.deepEqual(companies.filter(c=>u.strictCandidate(c,i)).map(c=>c.ticker).sort(),expected[i].sort());
const tel=companies.find(c=>c.ticker==='TEL');
for(const mutate of [c=>c.stale=true,c=>c.metrics.net.value=0,c=>delete c.metrics.fcf,c=>c.metrics.fcf.value=-1,c=>c.revenueGrowth=9.99,c=>c.market.excess=0,c=>c.market.boomExcess=0,c=>c.market.boomComparable=false]){
  const c=structuredClone(tel);mutate(c);assert.equal(u.strictCandidate(c,0),false);
}
const boundary=structuredClone(tel);boundary.revenueGrowth=10;assert.equal(u.strictCandidate(boundary,0),true);
vm.runInContext("recognitionWindow='recent';recognitionGap=50",ctx);
for(let i=0;i<3;i++)assert.deepEqual(companies.filter(c=>u.strictCandidate(c,i)).map(c=>c.ticker).sort(),expected[i].sort());
const origin=u.spatialPoint({x:0,y:0,z:0},0,0,1,1200,850);
near(origin.x,1200*.665);near(origin.y,850*.43);
const point={x:160,y:-90,z:0},p1=u.spatialPoint(point,0,0,1,1200,850),p2=u.spatialPoint(point,0,0,2,1200,850);
near(p2.x-origin.x,2*(p1.x-origin.x));near(p2.y-origin.y,2*(p1.y-origin.y));
assert.ok(u.spatialPoint({x:0,y:0,z:400},0,0,1,1200,850).scale<origin.scale);
assert.notEqual(u.spatialPoint(point,.6,.3,1,1200,850).x,p1.x);
const a={x:-110,y:35,z:70},b={x:310,y:-90,z:-280},original=JSON.stringify([a,b]);
for(let index=0;index<8;index++)for(const t of [0,.25,.5,.75,1]){
  const p=u.curvePoint(a,b,t,index);Object.values(p).forEach(v=>assert.ok(Number.isFinite(v)));
  if(t===0||t===1)for(const k of ['x','y','z'])near(p[k],(t?b:a)[k]);
}
assert.equal(JSON.stringify([a,b]),original);
u.__test.setup();
assert.equal(u.__test.nodeIds().length,registry.entities.length);
assert.equal(new Set(u.__test.nodeIds()).size,registry.entities.length);
for(const entry of registry.entities)assert.ok(u.__test.nodeIds().includes(entry.id),entry.id);
for(const ticker of ['META','AAPL','INTC']){
  const entry=registry.entities.find(e=>e.financialTicker===ticker);
  u.selectNode(entry.id);
  assert.equal(u.__test.mode(),'evidence','Financial companies stay in the money network');
}
assert.equal(u.__test.node('SPCX').company,undefined,'Pending public research cannot inherit financials');
assert.equal(u.__test.node('MUFG').listingStatus,'subsidiary');
assert.equal(u.__test.node('MUFG').ticker,null);
const connected=new Set(ctx.circulationData.edges.flatMap(e=>[e.from,e.to]));
for(const entry of registry.entities)assert.equal(u.__test.node(entry.id).linked,connected.has(entry.id));
u.__test.mode('future');
assert.equal(u.__test.nodeIds().length,companies.length);
assert.ok(!u.__test.nodeIds().includes('SPCX'),'No unsupported future rating for newly covered companies');
u.selectNode('SPCX');
assert.equal(u.__test.mode(),'evidence','Selecting a pending company restores the evidence map');
for(const mode of ['evidence','future']){
  u.__test.mode(mode);
  for(const id of ['MSFT','NVDA']){
    u.selectNode(id);const target=u.__test.target(),position=u.__test.position(id);
    for(const k of ['x','y','z'])near(target[k],position[k]);
  }
}
console.log('Spatial checks passed: full registry coverage, honest mode transitions, scenario paths, strict screens, projection, curves and camera targeting.');
