// Execute the production rendering functions without a browser/network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor(tag, cls = '', text = '') {
    Object.assign(this, {tag, className:cls, textContent:text, children:[], style:{}, open:false});
  }
  appendChild(child) { this.children.push(child); return child; }
}
const messages = new Element('div');
const sandbox = {
  n:(...args)=>new Element(...args),
  $:id=>{assert.equal(id,'messages');return messages;},
  scrollBottom:()=>{},
};
vm.createContext(sandbox);
const source = fs.readFileSync(path.join(__dirname,'../web_gateway/static/app.js'),'utf8');
const start = source.indexOf('function message(');
const end = source.indexOf('async function send(',start);
assert(start>=0 && end>start);
vm.runInContext(source.slice(start,end),sandbox);
const bubble = sandbox.message('assistant','SSID: Synthetic AP.','GATEWAY LM','MEASURED');
sandbox.enrichMessage(bubble,{
  case_status:'MEASURED',mode:'linux_live',catalog_total:120,workflow:'LAPTOP-SKILL-CHAT',
  calls:3,repairs:0,method:'core',advice:[{},{}],model_calls:4,llm_advisor_used:true,
  answer_synthesis:{used_llm:true},notice:'Scoped measurements only.',warnings:['Actionable warning'],
});
const details = bubble.children.find(n=>n.tag==='details');
assert(details && !details.open,'Technical details must default to closed');
assert.equal(details.children[0].textContent,'Chi tiết phép đo');
assert(!bubble.children.some(n=>n.className==='answer-meta'));
const meta = details.children.find(n=>n.className==='answer-meta');
assert(meta.children.some(n=>n.textContent==='LLM: 4 lượt'));
assert(bubble.children.some(n=>n.className==='warnings' && n.textContent==='Actionable warning'));
assert.equal(bubble.children[0].children[0].textContent,'Đã có số đo');
const diagnostic = sandbox.message('assistant','Chưa đủ bằng chứng.','GATEWAY LM','INCONCLUSIVE');
assert.equal(diagnostic.children[0].children[0].textContent,'Chưa đủ chẩn đoán');
assert(diagnostic.children[0].children[0].className.includes('partial'));
const unavailable = sandbox.message('assistant','Chưa có dữ liệu.','GATEWAY LM','UNAVAILABLE');
assert(unavailable.children[0].children[0].className.includes('blocked'));
const rejected = sandbox.message('assistant','Chưa đủ dữ liệu.','GATEWAY LM','NEEDS_INPUT');
sandbox.enrichMessage(rejected,{calls:0,repairs:0,model_calls:2,llm_advisor_used:false,
  llm_advisor_ready:true,case_status:'NEEDS_INPUT'});
assert(rejected.children.find(n=>n.tag==='details').children.find(n=>n.className==='answer-meta')
  .children.some(n=>n.textContent==='LLM: 2 lượt'));
console.log('Chat presentation: PASS (closed details, truthful badges, RPC count, warnings)');
