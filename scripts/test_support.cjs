// Load production functions without networking or browser bootstrap side effects.

function createRealAppContext(root, input) {
  const fs = require('fs'), path = require('path'), vm = require('vm');
  const elements = new Map();
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, {
      value: selector === '#valuation-focus' ? 'all' : '',
      addEventListener() {}, showModal() { this.open = true; },
    });
    return elements.get(selector);
  };
  const context = vm.createContext({
    input, URL, setTimeout, clearTimeout,
    document: { querySelector: element, querySelectorAll: () => [] },
    window: { addEventListener() {} },
    // Deliberately prevent bootstrap rendering and all network access.
    fetch: () => new Promise(() => {}),
  });
  for (const name of ['vendor/pdf-lib.min', 'reports', 'expansion', 'scenarios', 'app']) {
    vm.runInContext(fs.readFileSync(path.join(root, 'dist', name + '.js'), 'utf8'), context,
      { filename: name + '.js' });
  }
  vm.runInContext('data=input.data;companies=data.companies;scenariosData=input.scenarios;valuationData=input.valuation;circulationData=input.circulation;', context);
  return { context, elements };
}

// Execute this function inside the VM that owns PDFLib, e.g.
// vm.runInContext('(' + inspectPdf.toString() + ')(pdfBytes)', context).
// The current renderer sanitizes to ASCII and emits hex Tj operands with
// StandardFonts. This is an assertion helper for this renderer, not a general
// PDF text extractor or a replacement for visual layout inspection.
async function inspectPdf(bytes) {
  const doc = await PDFLib.PDFDocument.load(bytes), texts = [], urls = [];
  for (const page of doc.getPages()) {
    const contents = page.node.Contents();
    const refs = contents instanceof PDFLib.PDFArray ? contents.asArray() : [contents];
    for (const ref of refs.filter(Boolean)) {
      const raw = doc.context.lookup(ref);
      const decoded = PDFLib.decodePDFRawStream(raw).decode();
      const operators = Array.from(decoded, c => String.fromCharCode(c)).join('');
      for (const match of operators.matchAll(/<([0-9A-Fa-f]+)>\s*Tj/g)) {
        texts.push(PDFLib.PDFHexString.of(match[1]).decodeText());
      }
    }
    for (const ref of page.node.Annots()?.asArray() || []) {
      const annotation = doc.context.lookup(ref, PDFLib.PDFDict);
      const action = annotation.lookup(PDFLib.PDFName.of('A'), PDFLib.PDFDict);
      if (action?.lookup(PDFLib.PDFName.of('S'))?.toString() === '/URI') {
        urls.push(action.lookup(PDFLib.PDFName.of('URI')).decodeText());
      }
    }
  }
  return { pages: doc.getPageCount(), text: texts.join(' ').replace(/\s+/g, ' ').trim(), urls };
}

module.exports = { createRealAppContext, inspectPdf };
