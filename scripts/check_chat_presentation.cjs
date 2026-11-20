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
  replaceChildren() { this.children = []; }
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
  caveats:['ICMP/DNS phản hồi chưa chứng minh truy cập web hoặc nguyên nhân gốc.'],
  claim_details:['Có mất gói tới IP Internet kiểm tra.'],
  measurement_details:['Số đo bổ sung.'],
});
const details = bubble.children.find(n=>n.tag==='details');
assert(details && !details.open,'Technical details must default to closed');
assert.equal(details.children[0].textContent,'Chi tiết phép đo');
assert(!bubble.children.some(n=>n.className==='answer-meta'));
assert(!bubble.children.some(n=>n.className==='answer-notes'));
const notes = details.children.find(n=>n.className==='answer-notes');
assert.deepEqual(notes.children.map(n=>n.textContent),[
  'Số đo bổ sung.',
  'Có mất gói tới IP Internet kiểm tra.',
  'ICMP/DNS phản hồi chưa chứng minh truy cập web hoặc nguyên nhân gốc.',
]);
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
for (const [kind, label] of Object.entries({
  instant: 'Tức thì', evidence: 'Có bằng chứng', proposal: 'Đề xuất lệnh', knowledge: 'Kiến thức',
})) {
  const answer = sandbox.message('assistant', 'Dữ liệu mô phỏng.');
  const envelope = {schema_version:'1.0',request_id:1,command:'set_guest_wifi',
    target:{type:'gateway'},arguments:{enabled:true}};
  sandbox.enrichMessage(answer, {
    mode:'replay_sim',answer_kind:kind, calls:0, timings_ms:{total:30.4},
    command_proposal:kind === 'proposal' ? {executed:false, envelope} : undefined,
    knowledge:kind === 'knowledge' ? {passages:['wb.vi.placement']} : undefined,
  });
  assert(answer.children[0].children.some(node=>node.textContent===label));
  const details = answer.children.find(node=>node.tag==='details');
  assert(details.children.find(node=>node.className==='answer-meta')
    .children.some(node=>node.textContent==='Thời gian: 30.4 ms'));
  if (kind === 'proposal') {
    assert.equal(details.children[0].textContent,'Chi tiết đề xuất');
    assert.deepEqual(JSON.parse(details.children.find(node=>node.tag==='pre').textContent), envelope);
    assert(!details.children.some(node=>node.tag==='button'), 'Proposal is display-only');
  }
}
const incidents = require('../data/skill_expansion_v1/incidents_v1/router_incidents_v1.json').incidents;
const options = new Element('optgroup');
const rows = incidents.map(row=>({id:row.id, title:row.title_vi}));
sandbox.renderIncidentOptions(options, rows);
sandbox.renderIncidentOptions(options, rows);
assert.equal(options.children.length, 14);
assert.deepEqual(options.children.map(node=>[node.value,node.textContent]),
  incidents.map(row=>[row.id,row.title_vi]));
const index = fs.readFileSync(path.join(__dirname,'../web_gateway/static/index.html'),'utf8');
for (const id of ['normal', 'fault', 'missing']) assert(index.includes(`<option value="${id}">`));
assert(index.includes('<optgroup id="incidentOptions"'));
const incident = incidents[0];
const guidance = {
  label:'khuyến nghị — chưa thực hiện, áp dụng trên router của bạn',
  steps:incident.fix_vi, sources:incident.sources,
};
for (const [verdict, ids, visible] of [['FAULT',['proof'],true], ['FAULT',[],false], ['UNKNOWN',[],false]]) {
  const answer = sandbox.message('assistant', 'Pool DHCP hết địa chỉ.');
  sandbox.enrichMessage(answer, {mode:'replay_sim', verdict, evidence_ids:ids, incident_guidance:guidance});
  const card = answer.children.find(node=>node.className==='runbook-card');
  assert.equal(!!card, visible);
  if (!visible) continue;
  assert.equal(card.children[0].textContent, 'Cách xử lý');
  assert.equal(card.children[1].textContent, guidance.label);
  assert.deepEqual(card.children.find(node=>node.tag==='ul').children.map(node=>node.textContent), guidance.steps);
  assert.deepEqual(card.children.filter(node=>node.tag==='a').map(node=>node.href), guidance.sources);
  assert(card.children.filter(node=>node.tag==='a').every(node=>node.rel==='noopener noreferrer'));
  assert(!card.children.some(node=>node.tag==='button' || node.tag==='form'));
}
console.log('Chat presentation: PASS (details, caveats, RPC count, 4 replay badges, 14 incident options, 3 advisory cases)');
