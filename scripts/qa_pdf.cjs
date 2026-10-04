const fs=require('fs'),vm=require('vm'),path=require('path'),os=require('os'),assert=require('assert/strict');
const root=path.resolve(__dirname,'..');
const input=Object.fromEntries(['data','scenarios','valuation','circulation'].map(n=>[n,JSON.parse(fs.readFileSync(path.join(root,'dist',n+'.json')))]));
const context=vm.createContext({setTimeout,clearTimeout,input,companies:input.data.companies,val:(c,k)=>c.metrics[k]?.value??null,esc:x=>String(x??''),money:(n,cur='USD')=>n==null?'Unavailable':cur+' '+n,pct:n=>n==null?'Unavailable':n.toFixed(1)+'%',date:d=>d||'Unavailable',$:id=>({value:id==='#valuation-focus'?'all':''})});
vm.runInContext(fs.readFileSync(path.join(root,'dist/vendor/pdf-lib.min.js'),'utf8'),context);
for(const name of ['scenarios','expansion','reports'])vm.runInContext(fs.readFileSync(path.join(root,'dist',name+'.js'),'utf8'),context);
vm.runInContext('scenariosData=input.scenarios;valuationData=input.valuation;circulationData=input.circulation;',context);
(async()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ai-money-map-pdf-qa-'));
  for(const kind of ['circulation','valuation','scenario','company','full']){
    context.kind=kind;
    const bytes=await vm.runInContext("buildResearchPdf(makeReportModel(kind,'SNPS'))",context);
    assert.equal(Buffer.from(bytes).subarray(0,5).toString(),'%PDF-');
    context.pdfBytes=bytes;
    const parsed=await vm.runInContext('PDFLib.PDFDocument.load(pdfBytes)',context);
    assert.ok(parsed.getPageCount()>0,kind+' PDF has no pages');
    const file=path.join(dir,'ai-money-map-'+kind+'.pdf');
    fs.writeFileSync(file,bytes);
    console.log(file,bytes.length+' bytes',parsed.getPageCount()+' pages');
  }
})().catch(e=>{console.error(e);process.exit(1)});
