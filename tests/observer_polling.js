const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = new Map();
const pending = [];
let poll;
const context = {
  location: {search: ''}, URLSearchParams, console,
  document: {
    getElementById: id => {
      if (!elements.has(id)) elements.set(id, {textContent:'Loading', className:''});
      return elements.get(id);
    },
    querySelectorAll: () => [],
  },
  fetch: path => new Promise(resolve => pending.push({path, resolve})),
  setInterval: callback => {poll = callback;},
};
context.document.getElementById('objective');
vm.runInNewContext(fs.readFileSync('web/app.js','utf8'),context);
poll(); poll(); // Two polling periods elapse before the first network response.
for (const item of pending.slice(0,3)) {
  item.resolve({ok:true,json:async()=>item.path==='/api/context'?{objective:'Employee objective'}:[]});
}
setImmediate(() => {
  assert.equal(elements.get('objective').textContent,'Employee objective',
    'A slow but valid response must render even when another polling period has elapsed');
  assert.equal(pending.length,3,'Only one polling request batch may be outstanding');
  console.log('Observer slow-connection regression passed.');
});
