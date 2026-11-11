'use strict';
const $ = (id) => document.getElementById(id);
const state = { connected: false, busy: false, method: 'bm25', fixtures: [], tab: 'timeline', result: null, planIndex: null,
                sessionId: null, turns: 0 };
const normalize = (s) => String(s ?? '');
const n = (tag, cls, content) => { const el = document.createElement(tag); if(cls)el.className=cls;if(content!==undefined)el.textContent=normalize(content);return el;};
const fmt = obj => JSON.stringify(obj, null, 2);
function toast(text) { const x=$('toast');x.textContent=text;x.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>x.hidden=true,5000); }
function setBusy(b){state.busy=b; $('sendBtn').disabled=b||!$('userInput').value.trim();$('typing').hidden=!b;}
function setMethod(m){state.method=m;document.querySelectorAll('.seg').forEach(b=>b.classList.toggle('active',b.dataset.method===m));}
function showIntro(yes){$('intro').hidden=!yes;$('intro').style.display=yes?'':'none';}
function scrollBottom(){requestAnimationFrame(()=>$('chatScroll').scrollTo({top:$('chatScroll').scrollHeight,behavior:'smooth'}));}
function setTab(tab){state.tab=tab;document.querySelectorAll('.trace-tab').forEach(t=>t.classList.toggle('active',t.dataset.tab===tab));renderInspector();}
function clearChat(){state.turns=0;state.result=null;state.sessionId=null;$('messages').replaceChildren();showIntro(true);['statCalls','statEvidence','statRepairs','statSkills'].forEach(x=>$(x).textContent='—');$('inspectorContent').innerHTML='<div class="empty-inspect"><div class="wireframe-icon">◎</div><h3>Chưa có lượt chạy</h3><p>Gửi một câu hỏi để xem Agent chọn function nào, thu evidence gì và lập kế hoạch ra sao.</p><div class="ghost-rows"><span></span><span></span><span></span></div></div>';}
function updateSource() {
  const live = $('sourceSelect').value === 'live';
  const source = live ? 'Đo thật từ Windows' : 'Replay mô phỏng';
  $('fixtureField').hidden = live;
  $('liveNote').hidden = !live;
  $('suggestions').hidden = live;
  $('liveSuggestions').hidden = !live;
  $('sourcePill').textContent = source.toUpperCase();
  $('sourceFooter').textContent = live ? 'Phép đo lấy từ máy Windows.' : 'Dữ liệu replay mô phỏng.';
  $('traceSource').textContent = state.result ? (state.result.mode === 'windows_live' ? 'Đo thật từ Windows' : 'Replay mô phỏng') : source;
  $('introSource').textContent = live ? 'Đang đo từ máy Windows này' : 'Đang dùng tình huống mô phỏng được chọn ở bên trái';
  $('introDescription').textContent = live ? 'Đọc gateway IPv4 mặc định và đo phản hồi mạng, DNS từ máy Windows.' : 'Đặt câu hỏi về WAN, Wi-Fi, DNS, DHCP hoặc sức khỏe gateway.';
  $('composerSource').textContent = live ? 'Kết quả lấy từ phép đo trên máy Windows này.' : 'Đang dùng dữ liệu mô phỏng.';
  $('guideToggle').disabled = live;
  $('skillToggle').disabled = live || !state.skillAvailable;
  const policy = $('policySelect');
  policy.querySelector('option[value=core]').disabled = live;
  if (live && policy.value === 'core') policy.value = policy.querySelector('option[value=react]').disabled ? 'dynamic' : 'react';
  state.sessionId = null;
}
function selectedFixture(){return state.fixtures.find(x=>x.id===$('fixtureSelect').value);}
function fixtureNote(){const x=selectedFixture();if(!x)return;$('fixtureNote').textContent=`${x.group} • ${x.split==='test'?'Test replay':'Dev replay'} • ${x.target==='gateway'?'Router':'Thiết bị: '+x.target}. Tất cả số đo đều giả lập.`;}
function setFixture(id){const opt=Array.from($('fixtureSelect').options).find(x=>x.value===id);if(opt){$('fixtureSelect').value=id;fixtureNote();}}
async function loadConfig(){try{let response=await fetch('/api/config');let config=await response.json();let health=config.status||{};state.connected=!!health.connected;let h=$('healthText');h.textContent=health.message||'Chưa xác định';$('gosBtn').disabled=!health.gos_available; state.skillAvailable=!!health.skill_context_available; $('methodNote').textContent=health.gos_available?'GoS đã sẵn sàng.':'GoS chưa sẵn sàng; có thể thử BM25.'; setMethod(config.default_method||'bm25');
const policy = $('policySelect');
policy.querySelector('option[value=react]').disabled = !config.react_available;
policy.value = config.default_policy || 'dynamic';
$('llmToggle').checked = policy.value === 'react';
$('modelField').hidden = !$('llmToggle').checked;h.parentElement.classList.toggle('offline',!state.connected);if(!response.ok)toast(config.error||'Không tải được dữ liệu Gateway LM');state.fixtures=config.fixtures||[];renderFixtures();
const source = $('sourceSelect');
source.querySelector('option[value=live]').disabled = !health.windows_live_available;
source.value = config.default_source === 'live' && health.windows_live_available ? 'live' : 'replay';
updateSource();}catch(e){state.connected=false;$('healthText').textContent='Backend chưa kết nối';$('healthText').parentElement.classList.add('offline');toast('Cần chạy python -m web_gateway.server trong Gateway_LM để gửi câu hỏi thật.');}}
function renderFixtures(){let el=$('fixtureSelect');el.replaceChildren();let current='';for(let f of state.fixtures){if(f.group!==current){current=f.group;let g=n('optgroup');g.label=current;el.appendChild(g);}let option=n('option','',f.label);option.value=f.id;el.appendChild(option);}if(!state.fixtures.length){let op=n('option','','Cần khởi động backend');op.value='GLM-21-1';el.appendChild(op);return;}setFixture(state.fixtures.some(x=>x.id==='GLM-21-1')?'GLM-21-1':state.fixtures[0].id);}
function message(kind,text,label,status){const item=n('div','message '+kind);let avatar=n('div','message-avatar '+(kind==='user'?'user-avatar':''),kind==='user'?'U':'✳');let bubble=n('div','bubble');let lbl=n('div','message-label',label|| (kind==='user'?'BẠN':'GATEWAY LM'));if(status){let st=n('span','answer-status '+(status==='PARTIAL'||status==='INCONCLUSIVE'?'partial':status==='BLOCKED'||status==='NEEDS_INPUT'?'blocked':''),status);lbl.appendChild(st);}bubble.appendChild(lbl);bubble.appendChild(n('div','bubble-body',text));if(kind==='assistant')item.appendChild(avatar);item.appendChild(bubble);if(kind==='user')item.appendChild(avatar);$('messages').appendChild(item);scrollBottom();return bubble;}
function enrichMessage(bubble,result){let meta=n('div','answer-meta');const fields=[['Workflow',result.workflow||'Chưa rõ'],['Functions',result.calls],['Repairs',result.repairs],['Policy',({react:'LangGraph ReAct',dynamic:'Dynamic',core:'Core'})[result.policy]],['Method',result.method.toUpperCase()],['LLM',result.llm_advisor_used?`${result.advice.length + Number(result.intake?.source === 'llm')} lượt`:result.llm_advisor_ready?'Chưa cần hỏi':result.llm_advisor_requested?'Chưa kết nối':'Tắt']];for(let [name,value] of fields){meta.appendChild(n('span','meta-chip',name+': '+value));}bubble.appendChild(meta);
if(result.runbooks?.length){let d=n('details','runbook-wrapper');d.appendChild(n('summary','','Runbook được truy xuất ('+result.runbooks.length+')'));for(let book of result.runbooks){let card=n('div','runbook-card');card.appendChild(n('b','',book.title+' · '+book.id));card.appendChild(n('div','',book.text));d.appendChild(card);}bubble.appendChild(d);}
let allWarnings=[...(result.warnings||[])];if(result.action==='ASK_USER'&&result.diagnosis==='target_ambiguous'){allWarnings.push('Bạn có thể trả lời câu hỏi bổ sung ngay ở ô chat; phiên làm việc giữ nguyên Case đang chờ.');}if(allWarnings.length){bubble.appendChild(n('div','warnings',allWarnings.join('\n')));}
const p=n('div','inspector-note',result.notice);p.style.marginTop='12px';bubble.appendChild(p);}
async function send(override){if(state.busy)return;let input=override??$('userInput').value.trim();if(!input)return;if(!state.connected){toast('Backend chưa kết nối. Hãy chạy web_gateway.server trong thư mục Gateway_LM.');return;}showIntro(false);$('userInput').value='';updateInput();message('user',input);setBusy(true);try{const payload={message:input,session_id:state.sessionId||undefined,source_mode:$('sourceSelect').value,fixture_id:$('fixtureSelect').value,method:state.method,policy:$('policySelect').value,with_skill_context:!$('skillToggle').disabled&&$('skillToggle').checked,with_guide:!$('guideToggle').disabled&&$('guideToggle').checked,with_llm:$('llmToggle').checked,model:$('modelName').value.trim()||'qwen3:1.7b'};let response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});let data=await response.json();if(!response.ok)throw Error(data.error+(data.hint?'\n'+data.hint:''));state.result=data;$('traceSource').textContent=data.mode==='windows_live'?'Đo thật từ Windows':'Replay mô phỏng';state.planIndex=null;state.sessionId=data.session_id||null;state.turns++;let answer=data.answer||'Không có câu trả lời';let bubble=message('assistant',answer,'GATEWAY LM · '+data.fixture,data.case_status);enrichMessage(bubble,data);renderInspector();updateStats(data); }catch(err){message('assistant','Không chạy được bộ chẩn đoán: '+err.message,'LỖI BACKEND','BLOCKED');toast(err.message);}finally{setBusy(false);scrollBottom();}}
function updateStats(r){$('statCalls').textContent=String(r.calls??'—');$('statEvidence').textContent=String(r.evidence?.length??0);$('statRepairs').textContent=String(r.repairs??0);$('statSkills').textContent=String(r.stages?.length??0);}
function renderInspector(){let content=$('inspectorContent');if(!state.result)return;let r=state.result;content.replaceChildren();let top=n('div','trace-overview');top.appendChild(n('span','','LAST RUN · '+r.fixture_id));top.appendChild(n('h3','',r.fixture));top.appendChild(n('p','',r.workflow+' · '+r.method.toUpperCase()+' · '+r.calls+' calls · '+r.repairs+' repairs'));content.appendChild(top);
if(state.tab==='timeline')renderTimeline(content,r);else if(state.tab==='evidence')renderEvidence(content,r);else if(state.tab==='contracts')renderContracts(content,r);else renderDAG(content,r);}
function renderContracts(content,r){content.appendChild(n('p','inspector-note','Route: '+(r.route||'—')+' · '+(r.decision_source||'')));let hist=n('div','kv-body',(r.revisions||[]).map(x=>'Revision '+x.revision+': '+(x.operators||[]).join(' → ')).join(String.fromCharCode(10))||'Không có kế hoạch.');content.appendChild(n('h4','','Lịch sử revision và toán tử repair'));content.appendChild(hist);const c=r.contracts||{};[['c0','Contract 0 · Retrieval → Resolver'],['a','Contract A · Planner → Runner'],['b','Contract B · Runner → Evidence'],['c','Contract C · Evidence → Planner']].forEach(([k,label])=>{let d=n('details','');d.appendChild(n('summary','',label));let pre=n('pre','kv-body',JSON.stringify(c[k]??null,null,2));d.appendChild(pre);content.appendChild(d);});}
function renderPolicy(content,r) {
  if (r.react) {
    const stages = r.react.steps.filter(step => step.node === 'tools').length;
    content.appendChild(n('div','inspector-note',`LangGraph ReAct đã điều phối ${stages} nhóm phép đo.`));
  }
  if (!r.policy_steps?.length) return;
  for (const step of r.policy_steps) {
    const details = n('details','kv');
    const summary = n('summary','kv-header');
    summary.appendChild(n('span','',step.selected || 'Không có mục tiêu hợp lệ'));
    summary.appendChild(n('span','kv-id','Sau lượt '+step.after_call));
    details.appendChild(summary);
    details.appendChild(n('div','kv-body',fmt({reason:step.reason, candidates:step.candidates, rejected:step.rejected})));
    content.appendChild(details);
  }
}
function renderSkillContext(content,r) {
  if (!r.skill_context) return;
  content.appendChild(n('div','trace-section-label','SKILL CONTEXT'));
  const bundles = r.skill_context.bundles || [];
  if (!bundles.length) content.appendChild(n('p','inspector-note','Không có bundle phù hợp trong ngân sách ngữ cảnh.'));
  for (const bundle of bundles) {
    const details = n('details','kv');
    details.appendChild(n('summary','kv-header',bundle.root));
    details.appendChild(n('div','kv-body',fmt(bundle)));
    content.appendChild(details);
  }
}
function processStep(content, number, title, question) {
  const section = n('section','process-step');
  section.appendChild(n('h3','',`${number}  ${title}`));
  section.appendChild(n('p','process-question',question));
  content.appendChild(section);
  return section;
}

function renderReasoning(section, result) {
  if (!result.advice?.length) {
    const explanation = result.llm_advisor_ready
      ? 'Chưa cần hỏi LLM để chọn phép đo.'
      : result.llm_advisor_requested ? 'LLM chưa kết nối. Hệ thống dùng policy hiện có.' : 'LLM đang tắt.';
    section.appendChild(n('p','inspector-note',explanation));
    return;
  }
  for (const advice of result.advice) {
    const card = n('div','reason-card');
    card.appendChild(n('strong','',`${advice.model || 'LLM'} · ${advice.accepted ? 'Đề xuất được chấp nhận' : 'Giữ lựa chọn mặc định'}`));
    if (advice.failed_check) card.appendChild(n('p','',`Phép đo trước đó lỗi: ${advice.failed_check.function}.`));
    if (advice.hypothesis) card.appendChild(n('p','','Giả thuyết của LLM: '+advice.hypothesis));
    card.appendChild(n('p','',`Phép đo được chọn: ${advice.selected}`));
    const ids = advice.evidence_ids || advice.input_evidence_ids || [];
    if (ids.length) card.appendChild(n('small','',`Bằng chứng tham chiếu: ${ids.join(', ')}`));
    section.appendChild(card);
  }
}

function renderTimeline(content, result) {
  const understand = processStep(content,1,'🧠 Bộ hiểu yêu cầu','Người dùng đang gặp vấn đề gì, trên thiết bị nào?');
  const workflows = {'WF-INTERNET':'Không vào Internet từ thiết bị','WF-018':'Kết nối WAN',
    'WF-023':'Phân giải tên miền (DNS)','WF-024':'Cấp địa chỉ IP (DHCP)',
    'WF-039':'Sức khỏe hệ thống','WF-WRITE':'Yêu cầu thay đổi cấu hình',
    'LIVE-GATEWAY':'Gateway mặc định','LIVE-INTERNET':'Kết nối IPv4 từ Windows',
    'LIVE-QUALITY':'Chất lượng kết nối từ Windows','LIVE-THROUGHPUT':'Tốc độ tải và chất lượng kết nối',
    'LIVE-DNS':'Phân giải DNS từ Windows','WF-001':'Thiết bị đang kết nối','WF-006':'Tín hiệu và kênh Wi-Fi'};
  const target = result.target?.selector || (result.target?.scope === 'gateway' ? 'Router' : 'Chưa xác định');
  understand.appendChild(n('p','',result.request));
  understand.appendChild(n('div','inspector-note',`${workflows[result.workflow] || 'Chưa xác định yêu cầu'} · ${target}`));
  if (result.intake?.source === 'llm') {
    const outcome = result.intake.accepted ? 'đã nhận diện yêu cầu' : 'chưa xác định được luồng phù hợp';
    understand.appendChild(n('small','',`${result.intake.model} ${outcome}.`));
  }

  const decide = processStep(content,2,'🎯 Bộ quyết định kiểm tra','Tôi đã biết gì và cần kiểm tra điều gì tiếp theo?');
  renderReasoning(decide,result);
  renderPolicy(decide,result);

  const prepare = processStep(content,3,'🧩 Bộ chuẩn bị thao tác','Cần dùng những function nào và gọi theo thứ tự nào?');
  for (const plan of result.plans || []) {
    const details = n('details','kv');
    const goals = (plan.goals || []).join(' + ');
    details.appendChild(n('summary','kv-header',`Kế hoạch ${plan.revision} · ${goals}`));
    const functions = Object.values(plan.nodes || {}).map(node => node.function_id);
    const dependencies = (plan.edges || []).map(edge => `${edge.source} → ${edge.target}`);
    details.appendChild(n('div','kv-body',functions.concat(dependencies).join('\n')));
    prepare.appendChild(details);
  }
  if (!result.plans?.length) prepare.appendChild(n('p','inspector-note','Chưa có kế hoạch thực thi.'));
  renderSkillContext(prepare,result);

  const execute = processStep(content,4,'⚙️ Bộ thực thi & xác minh','Gọi function, kết quả có đáng tin cậy không?');
  if (!result.timeline?.length) execute.appendChild(n('p','inspector-note','Chưa gọi function.'));
  for (const item of result.timeline || []) {
    const verified = item.status === 'OK' && item.node_state === 'SUCCEEDED';
    const row = n('div',`step${verified ? '' : ' failed'}`);
    row.appendChild(n('h4','',`${item.index}. ${item.function_id}`));
    row.appendChild(n('small','',verified ? `${item.evidence_id} · ${JSON.stringify(item.value)}`
      : `${item.status} · chưa dùng làm bằng chứng`));
    execute.appendChild(row);
  }

  const assess = processStep(content,5,'🔍 Bộ đánh giá kết quả','Đã đủ bằng chứng kết luận chưa, hay phải kiểm tra tiếp?');
  const verdicts = {RESOLVED:'Đã đủ bằng chứng',PARTIAL:'Mới xác minh được một phần',
    NEEDS_INPUT:'Cần người dùng bổ sung',INCONCLUSIVE:'Chưa đủ bằng chứng',BLOCKED:'Yêu cầu bị chặn'};
  assess.appendChild(n('strong','',verdicts[result.case_status] || result.case_status));
  assess.appendChild(n('p','',result.answer));
  if (result.evidence_ids?.length) {
    assess.appendChild(n('small','',`Bằng chứng dùng để kết luận: ${result.evidence_ids.join(', ')}`));
  }
}
function renderEvidence(content,r){content.appendChild(n('div','trace-section-label','OBSERVED EVIDENCE'));let source=r.evidence||[];if(!source.length){content.appendChild(n('p','inspector-note','Chưa có evidence. Hệ thống chưa thực thi kiểm tra nào.'));return;}for(let e of source){let details=n('details','kv');let summary=n('summary','kv-header');let name=n('span','',e.port);let id=n('span','kv-id',e.id+' · '+e.status);summary.appendChild(name);summary.appendChild(id);details.appendChild(summary);let body=n('div','kv-body');body.textContent=fmt({function:e.function_id,target:e.target,source:e.source,status:e.status,value:e.value,ttl_s:e.ttl_s});details.appendChild(body);content.appendChild(details);}content.appendChild(n('p','inspector-note',r.mode==='windows_live'?'Số đo trực tiếp từ Windows. Xem bước đánh giá để biết bằng chứng nào được dùng.':'Bằng chứng lấy từ tình huống mô phỏng.'));}
function renderDAG(content,r){content.appendChild(n('div','trace-section-label','EXECUTION DAG'));let plans=r.plans||[];if(!plans.length){content.appendChild(n('p','inspector-note','Không có DAG do yêu cầu chưa được lập kế hoạch hoặc đã bị chặn.'));return;}const index = state.planIndex ?? (plans.length - 1);
const chooser = n('select','dag-select');
chooser.setAttribute('aria-label','Chọn phiên bản kế hoạch');
plans.forEach((item,i)=>{const option=n('option','',`Plan ${item.revision} · ${(item.goals||[]).join(' + ')}`);option.value=i;chooser.appendChild(option);});
chooser.value=index;
chooser.addEventListener('change',()=>{state.planIndex=Number(chooser.value);renderInspector();$('inspectorContent').querySelector('.dag-select')?.focus();});
content.appendChild(chooser);
let plan=plans[index];
const check = plan.audit?.find(entry => entry.operator === 'SKILLDAG_CHECK');
if (check) {
  content.appendChild(n('p','inspector-note',`SkillDAG đã kiểm nhóm ${check.expanded.join(', ')}.`));
}
let nodes=Object.keys(plan.nodes||{});if(!nodes.length){content.appendChild(n('p','inspector-note','Kế hoạch không cần gọi function.'));return;}let deps=plan.edges||[];let levels={};for(let id of nodes)levels[id]=0;for(let j=0;j<nodes.length;j++){let changed=false;for(let edge of deps){if(levels[edge.source]!==undefined&&levels[edge.target]!==undefined&&levels[edge.target]<levels[edge.source]+1){levels[edge.target]=levels[edge.source]+1;changed=true;}}if(!changed)break;}let groups={};for(let id of nodes)(groups[levels[id]]??=[]).push(id);const maxL=Math.max(...Object.keys(groups).map(Number)),maxR=Math.max(...Object.values(groups).map(v=>v.length)),W=660,H=Math.max(210,(maxL+1)*93+30);let svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('role','img');svg.setAttribute('aria-label','Đồ thị thực thi: '+nodes.join(', '));let pos={};Object.entries(groups).forEach(([lev,ids])=>{ids.sort();ids.forEach((id,i)=>{pos[id]={x:(W-(ids.length-1)*175)/2+i*175,y:35+Number(lev)*93};});});function addSVG(tag,attrs,txt){let a=document.createElementNS('http://www.w3.org/2000/svg',tag);for(let [k,v] of Object.entries(attrs))a.setAttribute(k,v);if(txt!==undefined)a.textContent=txt;svg.appendChild(a);return a;}for(let e of deps){let a=pos[e.source],b=pos[e.target];if(!a||!b)continue;addSVG('path',{d:`M ${a.x} ${a.y+29} C ${a.x} ${a.y+57}, ${b.x} ${b.y-28}, ${b.x} ${b.y-16}`,stroke:e.kind==='ORDER'?'#b8a5db':'#4e8f9c','stroke-width':'2',fill:'none'});addSVG('path',{d:`M ${b.x-4} ${b.y-22} L ${b.x} ${b.y-14} L ${b.x+4} ${b.y-22}`,stroke:'#6bb4bd','stroke-width':'1.5',fill:'none'});}for(let id of nodes){let p=pos[id], node=plan.nodes[id];let status=normalize(node?.state);let fill=status==='SUCCEEDED'?'#214a49':status==='FAILED'?'#5a3035':'#1b3147';let stroke=status==='SUCCEEDED'?'#64cfbd':status==='FAILED'?'#e2a7a5':'#51758e';addSVG('rect',{x:p.x-80,y:p.y-13,width:160,height:45,rx:9,fill,stroke,'stroke-width':1});addSVG('text',{x:p.x,y:p.y+5,'text-anchor':'middle','font-size':12,fill:'#e3f4f4','font-family':'ui-monospace,Consolas,monospace'},id.length>21?id.slice(0,20)+'…':id);addSVG('text',{x:p.x,y:p.y+21,'text-anchor':'middle','font-size':8,fill:status==='SUCCEEDED'?'#9bf4ce':'#8baec4'},status||'PENDING');}
let wrap=n('div','dag-canvas');wrap.appendChild(svg);content.appendChild(wrap);content.appendChild(n('p','dag-caption','Mũi tên biểu thị DATA, STATE hoặc ORDER dependency. DAG là kế hoạch thực thi được tạo bởi Graph Compiler. Mỗi lượt hỏi có thể tạo plan khác nhau.'));content.appendChild(n('div','trace-section-label','DEPENDENCY EDGES'));if(!deps.length)content.appendChild(n('p','inspector-note','Các node không có dependency với nhau.'));for(let e of deps){content.appendChild(n('span','tag',e.source+' → '+e.target+' · '+e.kind));}}
function updateInput(){let ta=$('userInput');$('charCount').textContent=ta.value.length+'/2000';ta.style.height='auto';ta.style.height=Math.min(135,Math.max(34,ta.scrollHeight))+'px';$('sendBtn').disabled=state.busy||!ta.value.trim();}
$('sendBtn').addEventListener('click',()=>send());$('userInput').addEventListener('input',updateInput);$('userInput').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});$('clearBtn').addEventListener('click',clearChat);
$('sourceSelect').addEventListener('change',updateSource);
$('fixtureSelect').addEventListener('change',()=>{state.sessionId=null;fixtureNote();});$('llmToggle').addEventListener('change',e=>{ $('modelField').hidden=!e.target.checked; });document.querySelectorAll('.seg').forEach(b=>b.addEventListener('click',()=>setMethod(b.dataset.method)));
document.querySelectorAll('.trace-tab').forEach(b=>b.addEventListener('click',()=>setTab(b.dataset.tab)));
document.querySelectorAll('.suggestion').forEach(b=>b.addEventListener('click',()=>{state.sessionId=null;setFixture(b.dataset.fixture);send(b.dataset.query);}));
$('menuBtn').addEventListener('click',()=>{$('sidebar').classList.toggle('open');$('inspector').classList.remove('open')});$('traceBtn').addEventListener('click',()=>{$('inspector').classList.toggle('open');$('sidebar').classList.remove('open')});
$('chatScroll').addEventListener('click',()=>{$('sidebar').classList.remove('open');$('inspector').classList.remove('open')});
loadConfig();updateInput();
