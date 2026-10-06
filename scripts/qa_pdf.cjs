'use strict';
const fs=require('fs'),vm=require('vm'),path=require('path'),os=require('os'),assert=require('assert/strict');
const {createRealAppContext,inspectPdf}=require('./test_support.cjs');
const root=path.resolve(__dirname,'..');
const input=Object.fromEntries(['data','scenarios','valuation','circulation'].map(n=>[n,JSON.parse(fs.readFileSync(path.join(root,'dist',n+'.json')))]));
const {context,elements}=createRealAppContext(root,input);
const run=code=>vm.runInContext(code,context);
const clean=text=>{context.expectedText=text;return run("pdfText(expectedText).replace(/\\s+/g,' ').trim()");};
const inspect=async bytes=>{context.pdfBytes=bytes;return await run('('+inspectPdf.toString()+')(pdfBytes)');};
function hasText(pdf,text){assert.ok(pdf.text.includes(clean(text)),`PDF missing content: ${text}`);}
function expectedUrls(model){return [...new Set(model.sections.flatMap(s=>(s.sources||[]).map(source=>new URL(source.url).href)))].sort();}
function verifyModel(kind,model){
 assert.ok(model.sections.length,kind+' must have content sections');
 const section=heading=>model.sections.find(s=>s.heading===heading);
 if(['circulation','full'].includes(kind)){
  assert.equal(model.sections.filter(s=>s.diagram).length,input.circulation.cases.length);
  assert.equal(section('Filtered relationship ledger').table.rows.length,input.circulation.edges.length);
 }
 if(['valuation','full'].includes(kind))assert.equal(section('Valuation and financing').table.rows.length,input.data.companies.length);
 if(kind==='company')assert.equal(section('Business and reported financials').table.rows.length,11);
 if(['scenario','full'].includes(kind))for(const s of kind==='full'?input.scenarios.scenarios:[input.scenarios.scenarios[0]])assert.ok(section('2030: '+s.name));
}
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ai-money-map-pdf-qa-'));
 for(const kind of ['circulation','valuation','scenario','company','full']){
  context.kind=kind;
  const model=run("makeReportModel(kind,'SNPS')");verifyModel(kind,model);context.model=model;
  const bytes=await run('buildResearchPdf(model)');assert.equal(Buffer.from(bytes).subarray(0,5).toString(),'%PDF-');
  const pdf=await inspect(bytes);assert.ok(pdf.pages>0);
  hasText(pdf,model.title);
  // This checks the serialized artifact, so an empty or skipped body cannot pass.
  for(const section of model.sections)if(section.heading)hasText(pdf,section.heading);
  // Input fixtures are independent of the report model: dropping narrative
  // content from either model creation or serialization must fail this check.
  if(['circulation','full'].includes(kind)){
   hasText(pdf,input.circulation.edges[0].amountLabel);
   for(const c of input.circulation.cases){hasText(pdf,c.summary);hasText(pdf,c.limitation);}
  }
  if(['valuation','full'].includes(kind)){
   for(const paragraph of input.valuation.methodology)hasText(pdf,paragraph);
   hasText(pdf,'MongoDB / MDB');hasText(pdf,'UiPath / PATH');
   hasText(pdf,'USD 0 / USD 1.00B');hasText(pdf,'USD 0 / USD 607.41M');
   assert.ok(!pdf.text.includes('USD 0.00M'));
  }
  if(kind==='company'){
   const c=input.data.companies.find(c=>c.ticker==='SNPS');context.expectedAmount=c.metrics.revenue.value;context.expectedCurrency=c.currency;
   hasText(pdf,run('reportCurrency(expectedAmount,expectedCurrency)'));hasText(pdf,'Counterargument and evidence');
   hasText(pdf,c.role);hasText(pdf,c.fcfDefinition);
  }
  if(['scenario','full'].includes(kind)){
   for(const s of kind==='full'?input.scenarios.scenarios:[input.scenarios.scenarios[0]]){hasText(pdf,s.summary);hasText(pdf,s.risk);}
   for(const ticker of input.scenarios.scenarios[0].winners)hasText(pdf,input.data.companies.find(c=>c.ticker===ticker).name+' ('+ticker+')');
  }
  assert.deepEqual([...new Set(Array.from(pdf.urls))].sort(),expectedUrls(model),kind+' source annotations');
  fs.writeFileSync(path.join(dir,'ai-money-map-'+kind+'.pdf'),bytes);
  console.log(kind+':',pdf.pages+' pages, verified text, amounts and '+pdf.urls.length+' safe source annotations');
 }
 // A syntactically valid but empty report must be rejected.
 await assert.rejects(()=>run("buildResearchPdf({title:'Empty',sections:[]})"),/content sections/);
 // Test the final PDF annotations, not just an HTML allowlist.
 context.sourceFixture={title:'Source safety fixture',subtitle:'Checks',sections:[{heading:'Evidence',sources:[
  ...['https://example.com/report?a=1&b=2','http://example.org/source'].map(url=>({title:'Valid reference',url})),
  ...['javascript:alert(1)','data:text/html,unsafe','file:///tmp/test','mailto:x@example.com','/relative','https://',null].map(url=>({title:'Unavailable reference',url}))
 ]}]};
 const sourcePdf=await inspect(await run('buildResearchPdf(sourceFixture)'));
 assert.deepEqual(Array.from(sourcePdf.urls),['https://example.com/report?a=1&b=2','http://example.org/source']);
 hasText(sourcePdf,'Unavailable reference (link unavailable)');assert.ok(!sourcePdf.text.includes('javascript:'));
 // Empty filters are legitimate reports and must explain why no rows appear.
 elements.get('#valuation-query').value='NO_MATCH_FOR_PDF_TEST';
 const empty=await inspect(await run("buildResearchPdf(makeReportModel('valuation'))"));
 hasText(empty,'Scope: 0 companies.');hasText(empty,'No rows match the current filters.');
 console.log('PDF artifacts:',dir);
 console.log('PDF regression checks passed, using production formatters and serialized content.');
})().catch(e=>{console.error(e);process.exit(1)});
