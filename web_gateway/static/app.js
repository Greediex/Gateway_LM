'use strict';
const $ = (id) => document.getElementById(id);
const state = { connected: false, busy: false, method: 'bm25', fixtures: [], tab: 'timeline', result: null, planIndex: null,
                sessionId: null, turns: 0, chatGeneration: 0, livePlatform: 'Windows', linuxLiveAvailable: false, networkRequest: 0 };
const normalize = (s) => String(s ?? '');
const n = (tag, cls, content) => { const el = document.createElement(tag); if(cls)el.className=cls;if(content!==undefined)el.textContent=normalize(content);return el;};
const fmt = obj => JSON.stringify(obj, null, 2);
function toast(text) { const x=$('toast');x.textContent=text;x.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>x.hidden=true,5000); }
function setBusy(b){state.busy=b; $('sendBtn').disabled=b||!$('userInput').value.trim();$('typing').hidden=!b;}
function setMethod(m){state.method=m;document.querySelectorAll('.seg').forEach(b=>b.classList.toggle('active',b.dataset.method===m));}
function showIntro(yes){$('intro').hidden=!yes;$('intro').style.display=yes?'':'none';}
function scrollBottom(){requestAnimationFrame(()=>$('chatScroll').scrollTo({top:$('chatScroll').scrollHeight,behavior:'smooth'}));}
function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll('.trace-tab').forEach(button => {
    const selected = button.dataset.tab === tab;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-selected', String(selected));
  });
  renderInspector();
}
function setInspector(open) {
  const inspector = $('inspector');
  inspector.hidden = !open;
  inspector.classList.toggle('open', open);
  $('traceBtn').setAttribute('aria-expanded', String(open));
  if (open) {
    setTab('graph');
    inspector.querySelector('[data-tab="graph"]').focus();
  } else {
    removeGraphPanel();
    $('inspectorContent').replaceChildren();
  }
}
function releaseChatSession(){if(state.sessionId && state.result?.catalog_total){fetch('/api/skills/close',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:state.sessionId})}).catch(()=>{});}state.sessionId=null;}
function clearChat() {
  state.chatGeneration++;
  releaseChatSession();
  state.turns = 0;
  state.result = null;
  $('messages').replaceChildren();
  showIntro(true);
  ['statCalls', 'statEvidence', 'statRepairs', 'statSkills'].forEach(id => $(id).textContent = '—');
  renderInspector();
}
function updateSource() {
  const mode = $('sourceSelect').value;
  const live = mode === 'live';
  const replaySim = mode === 'replay_sim';
  if (mode !== state.sourceMode && (replaySim || state.sourceMode === 'replay_sim')) clearChat();
  else {state.chatGeneration++; releaseChatSession();}
  state.sourceMode = mode;
  const platform = state.livePlatform;
  const linuxLive = live && state.linuxLiveAvailable && platform === 'Linux';
  const source = live ? `Đo thật từ ${platform}` : replaySim ? $('replaySimOption').textContent : 'Replay mô phỏng';
  resetNetwork();
  $('networkOverview').hidden = !linuxLive;
  $('liveWifiSuggestion').hidden = !linuxLive;
  $('liveNote').textContent = `Đo từ máy ${platform} đang dùng gateway mặc định.`;
  const dns = $('liveDnsSuggestion');
  dns.dataset.query = `Kiểm tra DNS từ máy ${platform} này.`;
  dns.querySelector('small').textContent = `Thử phân giải example.com từ ${platform}`;
  $('fixtureField').hidden = live || replaySim;
  $('scenarioField').hidden = !replaySim;
  $('inferenceSettings').hidden = replaySim;
  $('liveNote').hidden = !live;
  $('suggestions').hidden = live || replaySim;
  $('liveSuggestions').hidden = !live;
  $('sourcePill').textContent = source.toUpperCase();
  $('sourceFooter').textContent = live ? `Phép đo lấy từ máy ${platform}.` : 'Dữ liệu replay mô phỏng.';
  $('traceSource').textContent = state.result ? sourceLabel(state.result.mode) : source;
  $('introSource').textContent = live ? `Đang đo từ máy ${platform} này` : 'Đang dùng tình huống mô phỏng được chọn ở bên trái';
  $('introDescription').textContent = live ? `Đọc gateway IPv4 mặc định và đo phản hồi mạng, DNS từ máy ${platform}.` : 'Đặt câu hỏi về WAN, Wi-Fi, DNS, DHCP hoặc sức khỏe gateway.';
  $('composerSource').textContent = live ? `Kết quả lấy từ phép đo trên máy ${platform} này.` : 'Đang dùng dữ liệu mô phỏng.';
  $('guideToggle').disabled = live;
  $('skillToggle').disabled = live || !state.skillAvailable;
  const policy = $('policySelect');
  if (linuxLive && !state.linuxControls) {
    state.nonLinuxControls = {policy: policy.value, llm: $('llmToggle').checked};
  } else if (!linuxLive && state.linuxControls && state.nonLinuxControls) {
    policy.value = state.nonLinuxControls.policy;
    $('llmToggle').checked = state.nonLinuxControls.llm;
  }
  state.linuxControls = linuxLive;
  policy.disabled = linuxLive;
  policy.querySelector('option[value=dynamic]').textContent = linuxLive ? 'LLM → Skills → Core v0.2' : 'Dynamic Agent';
  policy.querySelector('option[value=react]').disabled = linuxLive || !state.reactAvailable;
  policy.querySelector('option[value=core]').disabled = live;
  $('llmToggle').disabled = false;
  $('modelName').disabled = linuxLive;
  $('bm25Btn').disabled = linuxLive;
  $('gosBtn').disabled = linuxLive || !state.gosAvailable;
  $('methodNote').textContent = linuxLive ? 'LLM local tra catalog · Core READ v0.2' : state.gosAvailable ? 'GoS đã sẵn sàng.' : 'GoS chưa sẵn sàng; có thể thử BM25.';
  if (linuxLive) {
    policy.value = 'dynamic';
    $('llmToggle').checked = true;
  } else if (live && policy.value === 'core') {
    policy.value = state.reactAvailable ? 'react' : 'dynamic';
  }
  $('modelField').hidden = linuxLive || !$('llmToggle').checked;
  state.sessionId = null;
}
function sourceLabel(mode) {
  return mode === 'linux_live' ? 'Đo thật từ Linux' : mode === 'windows_live' ? 'Đo thật từ Windows' : mode === 'replay_sim' ? 'Replay mô phỏng Skill' : 'Replay mô phỏng';
}
function resetNetwork(message = 'Chưa đo. Bấm Làm mới để thu bằng chứng.') {
  state.networkRequest++;
  clearTimeout(state.networkTimer);
  state.networkDeadline = null;
  $('networkResults').replaceChildren();
  $('networkState').textContent = message;
  $('networkState').className = 'network-state';
  $('networkRefresh').disabled = false;
  $('routerHealth').textContent = 'Sức khỏe router: UNAVAILABLE — chưa có phép đo CPU/RAM/service trên router.';
}
function expireNetwork() {
  if (state.networkDeadline !== null && performance.now() >= state.networkDeadline) {
    resetNetwork('STALE · Bằng chứng đã hết hạn. Bấm Làm mới để đo lại.');
    $('networkState').classList.add('network-warning');
  }
}
function networkTime(value) {
  const date = new Date(value);
  return value && Number.isFinite(date.getTime()) ? date.toLocaleString('vi-VN') : 'chưa rõ thời gian';
}
function networkFact(port, fact) {
  const card = n('details', 'network-fact');
  const labels = {'laptop.route':'Tuyến IPv4 thực tế', 'laptop.wifi':'Wi-Fi laptop',
    'laptop.gateway_probe':'Ping gateway', 'laptop.internet_probe':'Ping IP Internet', 'laptop.dns':'Phân giải DNS'};
  card.appendChild(n('summary', '', labels[port] || port));
  const values = fact.value || {};
  const fields = {
    interface:['Interface'], source_ipv4:['IPv4 nguồn'], gateway:['Gateway'], associated:['Đã kết nối Wi-Fi'],
    ssid:['SSID'], bssid:['BSSID'], signal_pct:['Signal', '%', 0], channel:['Kênh', '', 1],
    frequency_mhz:['Tần số', 'MHz', 1], ap_rate_mbps:['Tốc độ AP quảng bá', 'Mbps', 0],
    radio_enabled:['Radio bật'], destination:['Đích ping'], sent:['Gói gửi', 'gói', 0],
    received:['Gói nhận', 'gói', 0], loss_pct:['Mất gói', '%', 0], latency_ms:['Độ trễ', 'ms', 0],
    query:['Tên miền'], resolved:['Phân giải thành công']
  };
  const rows = n('dl', 'network-values');
  for (const [key, [label, unit, minimum]] of Object.entries(fields)) {
    if (!(key in values)) continue;
    const value = values[key];
    const missing = value === null || value === '' || (minimum !== undefined && (typeof value !== 'number' || value < minimum));
    rows.appendChild(n('dt', '', label));
    rows.appendChild(n('dd', '', missing ? 'Chưa có số đo' : typeof value === 'boolean' ? (value ? 'Có' : 'Không') : `${value}${unit ? ' ' + unit : ''}`));
  }
  card.appendChild(rows);
  card.appendChild(n('p', 'network-note', `Evidence: ${fact.evidence_id || 'thiếu ID'} · Đo lúc: ${networkTime(fact.observed_at)} · TTL: ${Math.round(fact.expires_in_s)} s`));
  card.appendChild(n('p', 'network-note', `Nguồn: ${fact.source || 'chưa rõ'} · Scope: ${fact.scope || 'chưa rõ'} · Target: ${typeof fact.target === 'object' ? fmt(fact.target) : fact.target || 'chưa rõ'}`));
  return card;
}
async function refreshNetwork() {
  if ($('networkOverview').hidden || $('sourceSelect').value !== 'live' || !state.linuxLiveAvailable) return;
  resetNetwork('Đang đo · Đang thu và xác minh bằng chứng từ Linux…');
  const request = state.networkRequest;
  $('networkRefresh').disabled = true;
  try {
    const response = await fetch('/api/network', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const data = await response.json();
    if (request !== state.networkRequest) return;
    if (!response.ok) throw Error(data.error || 'Không lấy được snapshot mạng.');
    if (data.mode !== 'linux_live' || !data.snapshot || !Array.isArray(data.features)) throw Error('Snapshot mạng không đúng định dạng.');
    const facts = data.snapshot.facts || {};
    const receivedAt = performance.now();
    const expiresAt = data.expires_at === undefined ? null : Date.parse(data.expires_at);
    const ttl = Math.min(Number(data.expires_in_s),
      ...(expiresAt === null ? [] : [(expiresAt - Date.now()) / 1000]));
    if (!Number.isFinite(ttl) || ttl <= 0) {
      resetNetwork('STALE · Snapshot đã hết hạn hoặc thiếu thời hạn. Bấm Làm mới để đo lại.');
      return;
    }
    const results = $('networkResults');
    const missing = [...new Set([...(data.snapshot.missing_ports || []), ...data.features.flatMap(f => f.missing_ports || [])])];
    const incomplete = !Object.keys(facts).length || !data.features.length || missing.length || (data.errors || []).length || data.features.some(f => !['MEASURED', 'ISSUE'].includes(f.status));
    const issue = data.features.some(f => f.status === 'ISSUE');
    const status = incomplete ? 'INCOMPLETE · Còn thiếu bằng chứng' : issue ? 'ISSUE · Có vấn đề được ghi nhận' : 'MEASURED · Đã nhận bằng chứng';
    $('networkState').textContent = `${status} · ${networkTime(data.generated_at)} · TTL ${Math.round(ttl)} s · ${data.calls ?? '—'} calls`;
    $('networkState').className = 'network-state' + (incomplete || issue ? ' network-warning' : '');
    results.appendChild(n('p', 'network-note', `Tuyến Internet: ${data.route_interface || 'chưa xác định'} · Wi-Fi: ${data.wifi_interface || 'chưa xác định'} · ${data.route_uses_wifi === true ? 'Tuyến đang đi qua Wi-Fi.' : data.route_uses_wifi === false ? 'Tuyến không đi qua Wi-Fi; phép đo Internet không chứng minh chất lượng Wi-Fi.' : 'Chưa xác định tuyến có dùng Wi-Fi.'}`));
    const features = n('div', 'network-features');
    for (const feature of data.features) {
      const card = n('article', 'network-feature');
      card.appendChild(n('h3', '', feature.title || feature.feature_id));
      card.appendChild(n('p', 'network-feature-status', `${feature.availability || 'UNAVAILABLE'} · ${feature.status || 'INCOMPLETE'} · ${feature.code || ''}`));
      card.appendChild(n('p', '', feature.summary || 'Chưa đủ bằng chứng để kết luận.'));
      const ids = feature.evidence_ids || [];
      const evidence = n('details', 'network-note');
      const compactIds = ids.map(id => id.length > 20 ? `${id.slice(0, 10)}…${id.slice(-6)}` : id).join(', ');
      const evidenceSummary = n('summary', '', `Evidence (${ids.length}): ${compactIds || 'chưa có'}`);
      evidenceSummary.title = ids.join(', ');
      evidence.appendChild(evidenceSummary);
      evidence.appendChild(n('p', '', ids.join(', ') || 'Chưa có evidence.'));
      card.appendChild(evidence);
      for (const step of feature.next_steps || []) card.appendChild(n('p', 'network-note', step));
      features.appendChild(card);
    }
    results.appendChild(features);
    if (missing.length) results.appendChild(n('p', 'network-warning', `Thiếu bằng chứng: ${missing.join(', ')}`));
    for (const error of data.errors || []) results.appendChild(n('p', 'network-warning', typeof error === 'string' ? error : fmt(error)));
    for (const [port, fact] of Object.entries(facts)) results.appendChild(networkFact(port, fact));
    $('routerHealth').textContent = `Sức khỏe router: UNAVAILABLE — ${data.router_health?.reason || 'chưa có phép đo CPU/RAM/service trên router.'}`;
    state.networkDeadline = receivedAt + ttl * 1000;
    state.networkTimer = setTimeout(expireNetwork, Math.max(0, state.networkDeadline - performance.now()) + 5);
  } catch (error) {
    if (request !== state.networkRequest) return;
    resetNetwork(`LỖI · ${error.message} Chưa có kết luận mạng; bấm Làm mới để thử lại.`);
    $('networkState').classList.add('network-warning');
  } finally {
    if (request === state.networkRequest) $('networkRefresh').disabled = false;
  }
}
document.addEventListener('visibilitychange', expireNetwork);
window.addEventListener('focus', expireNetwork);
$('networkRefresh').addEventListener('click', refreshNetwork);
function selectedFixture(){return state.fixtures.find(x=>x.id===$('fixtureSelect').value);}
function fixtureNote(){const x=selectedFixture();if(!x)return;$('fixtureNote').textContent=`${x.group} • ${x.split==='test'?'Test replay':'Dev replay'} • ${x.target==='gateway'?'Router':'Thiết bị: '+x.target}. Tất cả số đo đều giả lập.`;}
function setFixture(id){const opt=Array.from($('fixtureSelect').options).find(x=>x.value===id);if(opt){$('fixtureSelect').value=id;fixtureNote();}}
async function loadConfig(){try{let response=await fetch('/api/config');let config=await response.json();let health=config.status||{};state.connected=!!health.connected;state.gosAvailable=!!health.gos_available;state.reactAvailable=!!config.react_available;let h=$('healthText');h.textContent=health.message||'Chưa xác định';$('gosBtn').disabled=!health.gos_available; state.skillAvailable=!!health.skill_context_available; $('methodNote').textContent=health.gos_available?'GoS đã sẵn sàng.':'GoS chưa sẵn sàng; có thể thử BM25.'; setMethod(config.default_method||'bm25');
const policy = $('policySelect');
policy.querySelector('option[value=react]').disabled = !config.react_available;
policy.value = config.default_policy || 'dynamic';
$('llmToggle').checked = policy.value === 'react';
$('modelField').hidden = !$('llmToggle').checked;h.parentElement.classList.toggle('offline',!state.connected);if(!response.ok)toast(config.error||'Không tải được dữ liệu Gateway LM');state.fixtures=config.fixtures||[];renderFixtures();
const source = $('sourceSelect');
state.linuxLiveAvailable = !!health.linux_live_available;
state.livePlatform = health.live_platform === 'Linux' || state.linuxLiveAvailable ? 'Linux' : 'Windows';
const liveAvailable = !!(health.live_available ?? (health.windows_live_available || health.linux_live_available));
source.querySelector('option[value=live]').disabled = !liveAvailable;
source.querySelector('option[value=live]').textContent = `Đo thật từ ${state.livePlatform}`;
if (Number.isInteger(config.replay_sim_skill_count)) {
  const igate = Number.isInteger(config.igate_simulated) ? ` + ${config.igate_simulated} iGate` : '';
  $('replaySimOption').textContent = `Replay mô phỏng (${config.replay_sim_skill_count} Skill${igate})`;
}
// Owner's choice: open on the simulated 101-Skill replay; laptop live stays selectable.
source.value = Number.isInteger(config.replay_sim_skill_count) ? 'replay_sim'
  : config.default_source === 'live' && liveAvailable ? 'live' : 'replay';
updateSource();}catch(e){state.connected=false;$('healthText').textContent='Backend chưa kết nối';$('healthText').parentElement.classList.add('offline');toast('Cần chạy python -m web_gateway.server trong Gateway_LM để gửi câu hỏi thật.');}}
function renderFixtures(){let el=$('fixtureSelect');el.replaceChildren();let current='';for(let f of state.fixtures){if(f.group!==current){current=f.group;let g=n('optgroup');g.label=current;el.appendChild(g);}let option=n('option','',f.label);option.value=f.id;el.appendChild(option);}if(!state.fixtures.length){let op=n('option','','Cần khởi động backend');op.value='GLM-21-1';el.appendChild(op);return;}setFixture(state.fixtures.some(x=>x.id==='GLM-21-1')?'GLM-21-1':state.fixtures[0].id);}
function message(kind,text,label,status){const item=n('div','message '+kind);let avatar=n('div','message-avatar '+(kind==='user'?'user-avatar':''),kind==='user'?'U':'✳');let bubble=n('div','bubble');let lbl=n('div','message-label',label|| (kind==='user'?'BẠN':'GATEWAY LM'));if(status){let st=n('span','answer-status '+(status==='PARTIAL'||status==='INCONCLUSIVE'?'partial':['BLOCKED','NEEDS_INPUT','UNAVAILABLE'].includes(status)?'blocked':''),({MEASURED:'Đã có số đo',INCONCLUSIVE:'Chưa đủ chẩn đoán',PARTIAL:'Còn thiếu dữ liệu',NEEDS_INPUT:'Cần làm rõ',BLOCKED:'Chỉ đọc',UNAVAILABLE:'Chưa có dữ liệu'})[status]||status);st.title=status==='MEASURED'?'Phép đo hoàn tất, không phải kết luận sức khỏe hoặc đã khắc phục.':status;lbl.appendChild(st);}bubble.appendChild(lbl);bubble.appendChild(n('div','bubble-body',text));if(kind==='assistant')item.appendChild(avatar);item.appendChild(bubble);if(kind==='user')item.appendChild(avatar);$('messages').appendChild(item);scrollBottom();return bubble;}
function enrichMessage(bubble,result){const details=n('details','answer-details');details.appendChild(n('summary','','Chi tiết phép đo'));let meta=n('div','answer-meta');const fields=[['Workflow',result.workflow||'Chưa rõ'],['Functions',result.calls],['Repairs',result.repairs],['Policy',result.mode === 'linux_live' ? (result.catalog_total ? 'LLM + Skill session' : 'Core READ v0.2') : ({react:'LangGraph ReAct',dynamic:'Dynamic',core:'Core'})[result.policy]],['Method',String(result.method||'core').toUpperCase()],['LLM',(result.model_calls>0||result.llm_advisor_used)?`${result.model_calls ?? ((result.advice||[]).length + Number(result.intake?.source === 'llm' && !result.intake?.shared_with_selection))} lượt`:result.llm_advisor_ready?'Chưa cần hỏi':result.llm_advisor_requested?'Chưa kết nối':'Tắt']];for(let [name,value] of fields){meta.appendChild(n('span','meta-chip',name+': '+value));}details.appendChild(meta);bubble.appendChild(details);
if (result.mode === 'replay_sim') {
  const badge = {instant:'Tức thì',evidence:'Có bằng chứng',proposal:'Đề xuất lệnh',knowledge:'Kiến thức'}[result.answer_kind];
  if (badge) bubble.children[0].appendChild(n('span','answer-status answer-kind',badge));
  if (Number.isFinite(result.timings_ms?.total)) {
    meta.appendChild(n('span','meta-chip',`Thời gian: ${result.timings_ms.total} ms`));
  }
  if (result.command_proposal?.executed === false && result.command_proposal.envelope) {
    details.children[0].textContent = 'Chi tiết đề xuất';
    details.appendChild(n('pre','kv-body',JSON.stringify(result.command_proposal.envelope,null,2)));
  } else if (result.knowledge) {
    details.children[0].textContent = 'Nguồn kiến thức (draft)';
    details.appendChild(n('p','inspector-note',(result.knowledge.passages || []).join(', ')));
  }
}
if(result.runtime_features){const r=n('pre','kv-body',JSON.stringify(result.runtime_features,null,2));details.appendChild(r);}
const notes = [...(result.measurement_details || []), ...(result.claim_details || []), ...(result.caveats || [])];
if (notes.length) {
  const list = n('ul', 'answer-notes');
  for (const note of notes) list.appendChild(n('li', '', note));
  details.appendChild(list);
}
if(result.runbooks?.length){let d=n('details','runbook-wrapper');d.appendChild(n('summary','','Runbook được truy xuất ('+result.runbooks.length+')'));for(let book of result.runbooks){let card=n('div','runbook-card');card.appendChild(n('b','',book.title+' · '+book.id));card.appendChild(n('div','',book.text));d.appendChild(card);}bubble.appendChild(d);}
let allWarnings=[...(result.warnings||[])];if(result.action==='ASK_USER'&&result.diagnosis==='target_ambiguous'){allWarnings.push('Bạn có thể trả lời câu hỏi bổ sung ngay ở ô chat; phiên làm việc giữ nguyên Case đang chờ.');}if(allWarnings.length){bubble.appendChild(n('div','warnings',allWarnings.join('\n')));}
details.appendChild(n('span','meta-chip','Trạng thái đo: '+(result.case_status||'Chưa rõ')));if(result.answer_synthesis){details.appendChild(n('span','meta-chip','Diễn đạt: '+(result.answer_synthesis.used_llm?'LLM đã kiểm chứng':result.answer_synthesis.reason)));}const p=n('div','inspector-note',result.notice||'');p.style.marginTop='12px';details.appendChild(p);}
async function send(override) {
  if(state.busy)return;
  const input=override??$('userInput').value.trim();
  if(!input)return;
  if(!state.connected){toast('Backend chưa kết nối. Hãy chạy web_gateway.server trong thư mục Gateway_LM.');return;}
  const generation=state.chatGeneration;
  const sourceMode=$('sourceSelect').value;
  showIntro(false);$('userInput').value='';updateInput();message('user',input);setBusy(true);
  try {
    const common={message:input,session_id:state.sessionId||undefined,source_mode:sourceMode};
    const payload=sourceMode==='replay_sim'?{...common,scenario:$('scenarioSelect').value}:{...common,
      fixture_id:$('fixtureSelect').value,method:state.method,policy:$('policySelect').value,
      with_skill_context:!$('skillToggle').disabled&&$('skillToggle').checked,
      with_guide:!$('guideToggle').disabled&&$('guideToggle').checked,
      with_llm:true,model:$('modelName').value.trim()||'qwen3:4b'};
    let response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    let data=await response.json();
    if(response.status===410 && payload.session_id && payload.with_llm && payload.source_mode==='live'){
      const resumed=await fetch('/api/skills/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:payload.session_id})});
      if(resumed.ok){response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});data=await response.json();}
    }
    if(generation!==state.chatGeneration){
      if(data.catalog_total && data.session_id) fetch('/api/skills/close',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:data.session_id})}).catch(()=>{});
      return;
    }
    if(response.status===410) state.sessionId=null;
    if(sourceMode==='replay_sim' && data.reason==='skill_deployment_not_approved'){
      message('assistant',data.error,'REPLAY MÔ PHỎNG','BLOCKED');
      return;
    }
    if(!response.ok)throw Error(data.error+(response.status===410?' · Phiên cũ đã hết hạn; gửi lại câu hỏi để tạo phiên mới.':data.hint?'\n'+data.hint:''));
    state.result=data;$('traceSource').textContent=sourceLabel(data.mode);state.planIndex=null;
    state.sessionId=data.session_id||null;state.turns++;
    const chatStatus=['MEASURED','PARTIAL'].includes(data.case_status)&&data.diagnostic_status==='INCONCLUSIVE'?'INCONCLUSIVE':data.case_status;
    const bubble=message('assistant',data.answer||'Không có câu trả lời',data.catalog_total?'GATEWAY LM':'GATEWAY LM · '+data.fixture,chatStatus);
    enrichMessage(bubble,data);renderInspector();updateStats(data);
  } catch(err) {
    if(generation===state.chatGeneration){
      const problem=sourceMode==='replay_sim'?err.message:'Không chạy được bộ chẩn đoán: '+err.message;
      message('assistant',problem,sourceMode==='replay_sim'?'REPLAY MÔ PHỎNG':'LỖI BACKEND','BLOCKED');toast(err.message);
    }
  } finally {setBusy(false);scrollBottom();}
}
function updateStats(r){$('statCalls').textContent=String(r.calls??'—');$('statEvidence').textContent=String(r.evidence?.length??0);$('statRepairs').textContent=String(r.repairs??0);$('statSkills').textContent=String(r.skill_runs?.length??r.stages?.length??0);}
function renderInspector() {
  if ($('inspector').hidden) return;
  const content = $('inspectorContent');
  const result = state.result;
  if (state.tab === 'graph') {
    renderGraph(content, result, $('sourceSelect').value === 'replay_sim' ? 'replay_sim' : result?.mode);
    return;
  }
  removeGraphPanel();
  content.replaceChildren();
  if (!result) {
    const empty = n('div', 'empty-inspect');
    empty.append(n('h3', '', 'Chưa có lượt chạy'), n('p', '', 'Gửi một câu hỏi để xem dấu vết thực thi.'));
    content.appendChild(empty);
    return;
  }
  const top = n('div', 'trace-overview');
  top.append(n('span', '', 'LAST RUN · ' + result.fixture_id), n('h3', '', result.fixture),
    n('p', '', result.workflow + ' · ' + result.method.toUpperCase() + ' · ' + result.calls + ' calls · ' + result.repairs + ' repairs'));
  content.appendChild(top);
  if (state.tab === 'timeline') renderTimeline(content, result);
  else if (state.tab === 'evidence') renderEvidence(content, result);
  else if (state.tab === 'contracts') renderContracts(content, result);
  else renderDAG(content, result);
}
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
  const workflows = {'LAPTOP-SKILL-CHAT':'LLM → Skills → ReadSession → RCA', 'LAPTOP-NETWORK':'Mạng từ laptop Linux','WF-INTERNET':'Không vào Internet từ thiết bị','WF-018':'Kết nối WAN',
    'WF-023':'Phân giải tên miền (DNS)','WF-024':'Cấp địa chỉ IP (DHCP)',
    'WF-039':'Sức khỏe hệ thống','WF-WRITE':'Yêu cầu thay đổi cấu hình',
    'LIVE-GATEWAY':'Gateway mặc định','LIVE-INTERNET':'Kết nối IPv4 từ laptop',
    'LIVE-QUALITY':'Chất lượng kết nối từ laptop','LIVE-THROUGHPUT':'Tốc độ tải và chất lượng kết nối',
    'LIVE-DNS':'Phân giải DNS từ laptop','WF-001':'Thiết bị đang kết nối','WF-006':'Tín hiệu và kênh Wi-Fi'};
  const target = result.target?.selector || (result.target?.scope === 'gateway' ? 'Router' : 'Chưa xác định');
  if (result.request) understand.appendChild(n('p','',result.request));
  understand.appendChild(n('div','inspector-note',`${workflows[result.workflow] || 'Chưa xác định yêu cầu'} · ${target}`));
  if (result.intake?.source === 'llm') {
    const outcome = result.intake.accepted ? 'đã nhận diện yêu cầu' : 'chưa xác định được luồng phù hợp';
    understand.appendChild(n('small','',`${result.intake.model} ${outcome}.`));
  }

  const decide = processStep(content,2,'🎯 Bộ quyết định kiểm tra','Tôi đã biết gì và cần kiểm tra điều gì tiếp theo?');
  renderReasoning(decide,result);
  renderPolicy(decide,result);
  for (const run of result.skill_runs || []) {
    decide.appendChild(n('p','',`${run.skill_id} · ${run.status} · ${run.calls_this_run} calls · reuse: ${(run.reused_ports || []).join(', ') || 'không'}`));
  }
  if (result.stop_reason) decide.appendChild(n('small','',`Điều kiện dừng: ${result.stop_reason}`));

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
      : item.verified_at_execution ? 'Đã xác minh lúc đo; bằng chứng hiện không còn hiệu lực' : `${item.status} · chưa dùng làm bằng chứng`));
    execute.appendChild(row);
  }

  const assess = processStep(content,5,'🔍 Bộ đánh giá kết quả','Đã đủ bằng chứng kết luận chưa, hay phải kiểm tra tiếp?');
  const verdicts = {RESOLVED:'Đã đủ bằng chứng',PARTIAL:'Mới xác minh được một phần',
    NEEDS_INPUT:result.user_input_required===false?'Chưa hoàn tất xử lý':'Cần người dùng bổ sung',INCONCLUSIVE:'Chưa đủ bằng chứng',BLOCKED:'Yêu cầu bị chặn'};
  assess.appendChild(n('strong','',verdicts[result.case_status] || result.case_status));
  assess.appendChild(n('p','',result.answer));
  for (const row of result.rca_assessments || []) {
    const details=n('details','kv'); details.appendChild(n('summary','kv-header',`${row.workflow}: ${row.decision}`));
    details.appendChild(n('pre','kv-body',fmt(row))); assess.appendChild(details);
  }
  if (result.evidence_ids?.length) {
    assess.appendChild(n('small','',`Bằng chứng dùng để kết luận: ${result.evidence_ids.join(', ')}`));
  }
}
function renderEvidence(content,r){content.appendChild(n('div','trace-section-label','OBSERVED EVIDENCE'));let source=r.evidence||[];if(!source.length){content.appendChild(n('p','inspector-note','Chưa có evidence. Hệ thống chưa thực thi kiểm tra nào.'));return;}for(let e of source){let details=n('details','kv');let summary=n('summary','kv-header');let name=n('span','',e.port);let id=n('span','kv-id',e.id+' · '+e.status);summary.appendChild(name);summary.appendChild(id);details.appendChild(summary);let body=n('div','kv-body');body.textContent=fmt({function:e.function_id,target:e.target,source:e.source,status:e.status,value:e.value,ttl_s:e.ttl_s});details.appendChild(body);content.appendChild(details);}content.appendChild(n('p','inspector-note',['windows_live','linux_live'].includes(r.mode)?`Số đo trực tiếp từ ${r.mode === 'linux_live' ? 'Linux' : 'Windows'}. Xem bước đánh giá để biết bằng chứng nào được dùng.`:'Bằng chứng lấy từ tình huống mô phỏng.'));}
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
// Skill network projects the catalog and the most recent chat trace.
const graphData = new Map();
function loadGraph(mode) {
  const url = mode === 'replay_sim' ? '/api/graph?mode=replay_sim' : '/api/graph';
  if (!graphData.has(url)) {
    graphData.set(url, fetch(url).then(response => {
      if (!response.ok) throw Error('Skill graph unavailable');
      return response.json();
    }).catch(error => {
      graphData.delete(url);
      throw error;
    }));
  }
  return graphData.get(url);
}

function planCalls(plan) {
  const reused = new Set((plan.audit || []).flatMap(event =>
    event.operator === 'GLOBAL_REPLAN' ? event.reused_evidence || [] : []));
  return Object.entries(plan.nodes || {}).flatMap(([key, node]) => {
    if (Object.values(node.output_evidence || {}).some(id => reused.has(id))) return [];
    const history = node.history || [];
    const attempts = history.filter(step => step.from === 'RUNNING').map(step => step.to);
    if (!attempts.length && ['SUCCEEDED', 'FAILED', 'INCONCLUSIVE'].includes(node.state)) {
      // Older exports can include a terminal state without transition history.
      attempts.push(node.state);
    }
    return attempts.map(status => ({key, id: node.function_id, kind: 'function', status}));
  });
}

function orderSkillFunctions(result) {
  if (result.mode === 'replay_sim') {
    const functions = (result.timeline || []).map(row => ({id: row.function_id, kind: 'function',
      status: row.node_state}));
    return {functions, ordered: functions.length === result.calls};
  }
  const attempts = (result.plans || []).flatMap(planCalls);
  const audited = (result.function_retrievals || []).filter(row => row.selected_ready);
  if (!attempts.length && !result.calls) return {functions: [], ordered: true};

  // Selection audit covers the session. The turn's plans and count bound its tail.
  if (attempts.length === result.calls && audited.length >= result.calls) {
    const byNode = new Map();
    for (const attempt of attempts) {
      if (!byNode.has(attempt.key)) byNode.set(attempt.key, []);
      byNode.get(attempt.key).push(attempt);
    }
    const functions = audited.slice(-result.calls).map(row => byNode.get(row.selected_ready)?.shift());
    if (functions.every(Boolean)) return {functions, ordered: true};
  }

  // Replay Skill chat uses ordered selection; one invocation per plan needs no tie-break.
  if (result.mode === 'synthetic_replay' && attempts.length === result.calls
      && (result.plans || []).every(plan => planCalls(plan).length <= 1)) {
    return {functions: attempts, ordered: true};
  }

  if (attempts.length) return {functions: attempts, ordered: attempts.length === 1 && result.calls === 1};
  const functions = (result.timeline || [])
    .filter(row => row.verified_at_execution || ['SUCCEEDED', 'FAILED', 'INCONCLUSIVE'].includes(row.node_state))
    .map(row => ({id: row.function_id, kind: 'function', status: row.node_state}));
  return {functions, ordered: functions.length === 1 && result.calls === 1};
}

function runCalls(result) {
  if (!result) return {sequences: [], ordered: true, linked: true, skills: 0, functions: 0};
  const skillRuns = result.skill_runs || [];
  const skills = skillRuns.map(run => ({id: run.skill_id, kind: 'skill', status: run.status,
    count: run.calls_this_run, reused: (run.reused_ports || []).length > 0}));
  let functions, ordered;
  if (Array.isArray(result.skill_runs)) {
    ({functions, ordered} = orderSkillFunctions(result));
  } else if (result.timeline?.length) {
    // The workflow endpoint builds timeline from executed calls in order.
    functions = [...result.timeline].sort((a, b) => a.index - b.index).map(row => ({
      id: row.function_id, kind: 'function', status: row.status,
    }));
    ordered = true;
  } else {
    functions = (result.plans || []).flatMap(planCalls);
    ordered = functions.length <= 1;
  }
  // Extra RCA calls can be interleaved with Skill runs. Counts only establish
  // the boundaries when all invocations were accounted for by the Skill runs.
  const linked = !skills.length || (ordered && skills.every(skill => Number.isInteger(skill.count) && skill.count >= 0)
    && skills.reduce((sum, skill) => sum + skill.count, 0) === functions.length
    && result.calls === functions.length);
  let sequences;
  if (linked && skills.length) {
    let cursor = 0;
    sequences = [skills.flatMap(skill => {
      const end = cursor + skill.count;
      const steps = [skill, ...functions.slice(cursor, end)];
      cursor = end;
      return steps;
    })];
  } else {
    sequences = [skills, ...(ordered ? [functions] : functions.map(call => [call]))];
  }
  return {sequences: sequences.filter(sequence => sequence.length), ordered, linked,
    skills: skills.length, functions: functions.length};
}

const graphKey = (kind, id) => kind + ':' + id;
const graphDomainColors = ['#71caff', '#c6a5ff', '#75dfbc', '#fa9ac1', '#f5bc73',
  '#8b9bff', '#e0de80', '#63d6e4', '#fc9a87', '#d9a0ed', '#a4d278', '#8eb3d3',
  '#f18eb9', '#b5c9ff', '#e7be9d'];
const compareGraphKeys = (a, b) => (a > b) - (a < b);
const graphClamp = (value, min, max) => Math.min(max, Math.max(min, value));

function layoutGraph(graph, sequences = []) {
  const halfSize = Math.max(240, Math.sqrt(graph.nodes.length) * 30);
  const domainIds = Object.keys(graph.groups).sort(compareGraphKeys);
  const domains = new Map(domainIds.map((id, index) => {
    const angle = index * Math.PI * (3 - Math.sqrt(5));
    const radius = halfSize * .78 * Math.sqrt((index + .5) / domainIds.length);
    return [id, {label: graph.groups[id], color: graphDomainColors[index % graphDomainColors.length],
      x: Math.cos(angle) * radius, y: Math.sin(angle) * radius}];
  }));
  const catalog = new Map(graph.nodes.map(node => [graphKey(node.kind, node.id), node]));
  for (const call of sequences.flat()) {
    const key = graphKey(call.kind, call.id);
    if (!catalog.has(key)) catalog.set(key, {id: call.id, kind: call.kind, label: call.id, extra: true});
  }
  const nodes = new Map([...catalog.keys()].sort(compareGraphKeys).map(key => [
    key, {...catalog.get(key), neighbors: new Set(), vx: 0, vy: 0},
  ]));
  const edges = [...graph.edges].sort((a, b) => compareGraphKeys(a.source, b.source)
    || compareGraphKeys(a.target, b.target)).map(edge => {
    const from = nodes.get(graphKey('skill', edge.source));
    const to = nodes.get(graphKey('function', edge.target));
    from.neighbors.add(to);
    to.neighbors.add(from);
    return {from, to};
  });
  function seededPoint(key) {
    let seed = 0x811c9dc5;
    for (const char of key) seed = Math.imul(seed ^ char.codePointAt(0), 0x01000193);
    const angle = (seed >>> 0) / 0x100000000 * 2 * Math.PI;
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    return {angle, radius: Math.sqrt((seed >>> 0) / 0x100000000)};
  }
  for (const [key, node] of nodes) {
    const groups = new Map();
    if (domains.has(node.group)) groups.set(node.group, 1);
    for (const neighbor of node.neighbors) {
      if (domains.has(neighbor.group)) groups.set(neighbor.group, (groups.get(neighbor.group) || 0) + 1);
    }
    // A shared Function sits between its linked domains and uses the most frequent color.
    node.domains = [...groups.keys()].sort((a, b) => groups.get(b) - groups.get(a) || compareGraphKeys(a, b));
    const anchor = {x: 0, y: 0};
    for (const id of node.domains) {
      anchor.x += domains.get(id).x / node.domains.length;
      anchor.y += domains.get(id).y / node.domains.length;
    }
    const {angle, radius} = seededPoint(key);
    const distance = radius * (node.domains.length ? 45 : halfSize * .52);
    Object.assign(node, {anchor, x: anchor.x + distance * Math.cos(angle),
      y: anchor.y + distance * Math.sin(angle), radius: 5.5 + Math.min(8, 2.4 * Math.sqrt(node.neighbors.size))});
  }
  const hub = {x: 0, y: 0, vx: 0, vy: 0, pinned: true, radius: 10, label: 'Router / LLM'};
  return {halfSize, hub, nodes, domains, edges};
}

function graphSimulation({nodes, hub, edges, halfSize}) {
  const points = [...nodes.values(), hub];
  let heat = 1;
  let stepsLeft = 120;
  function step() {
    if (!stepsLeft || heat < .0025) return false;
    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i];
      for (let j = i + 1; j < points.length; j++) {
        const b = points[j];
        let dx = b.x - a.x;
        const dy = b.y - a.y;
        if (!dx && !dy) dx = .01;
        const square = dx * dx + dy * dy;
        const distance = Math.sqrt(square);
        const overlap = Math.max(0, a.radius + b.radius + 4 - distance);
        const force = heat * (2200 / (square + 100) + .6 * overlap) / distance;
        a.vx -= dx * force;
        a.vy -= dy * force;
        b.vx += dx * force;
        b.vy += dy * force;
      }
    }
    for (const {from, to} of edges) {
      const dx = to.x - from.x;
      const dy = to.y - from.y;
      const distance = Math.hypot(dx, dy) || 1;
      const force = heat * .035 * (distance - 36) / distance;
      from.vx += dx * force;
      from.vy += dy * force;
      to.vx -= dx * force;
      to.vy -= dy * force;
    }
    for (const node of points) {
      if (node.pinned) {
        node.vx = 0;
        node.vy = 0;
        continue;
      }
      const pull = heat * (node.domains.length ? .012 : .004);
      node.vx = (node.vx + (node.anchor.x - node.x) * pull) * .78;
      node.vy = (node.vy + (node.anchor.y - node.y) * pull) * .78;
      const limit = halfSize - node.radius - 4;
      node.x = graphClamp(node.x + node.vx, -limit, limit);
      node.y = graphClamp(node.y + node.vy, -limit, limit);
    }
    heat *= .94;
    stepsLeft--;
    return stepsLeft > 0 && heat >= .0025;
  }
  function reheat() {
    if (heat > .20) return;
    heat = .20;
    stepsLeft = 48;
  }
  return {step, reheat};
}

let graphPanel;
function createGraphPanel(content) {
  const holder = n('div', 'graph-view');
  const overlay = n('dialog', 'graph-overlay');
  overlay.setAttribute('aria-label', 'Mạng Skill toàn màn hình');
  const expand = n('button', 'light-btn', 'Toàn màn hình');
  expand.type = 'button';
  expand.setAttribute('aria-haspopup', 'dialog');
  const close = n('button', 'light-btn', 'Đóng toàn màn hình');
  close.type = 'button';
  overlay.appendChild(close);
  expand.addEventListener('click', () => {
    overlay.showModal();
    overlay.appendChild(holder);
    close.focus();
  });
  close.addEventListener('click', () => overlay.close());
  overlay.addEventListener('close', () => {
    if (!overlay.isConnected) return;
    content.insertBefore(holder, overlay);
    expand.focus();
  });
  overlay.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    event.preventDefault();
    event.stopPropagation();
    overlay.close();
  });
  holder.appendChild(n('p', 'inspector-note', 'Đang tải mạng Skill…'));
  content.replaceChildren(holder, overlay);
  return {holder, expand, overlay};
}

function removeGraphPanel() {
  graphPanel?.dispose?.();
  graphPanel = undefined;
}

function renderGraph(content, result, mode) {
  const panel = graphPanel ??= createGraphPanel(content);
  if (panel.result === result && panel.mode === mode) return;
  panel.result = result;
  panel.mode = mode;
  loadGraph(mode).then(graph => {
    if (panel !== graphPanel || panel.result !== result || panel.mode !== mode) return;
    panel.dispose?.();
    panel.dispose = drawGraph(panel, graph, result);
  }).catch(() => {
    if (panel !== graphPanel || panel.result !== result || panel.mode !== mode) return;
    panel.holder.replaceChildren(n('p', 'inspector-note', 'Không tải được mạng Skill. Mở lại tab để thử lại.'));
  });
}

function drawGraph({holder, expand}, graph, result) {
  const calls = runCalls(result);
  const layout = layoutGraph(graph, calls.sequences);
  const {hub, domains, nodes, edges} = layout;
  const viewport = n('div', 'graph-canvas');
  const tooltip = n('div', 'graph-tooltip');
  const detail = n('section', 'graph-node-detail');
  tooltip.hidden = true;
  detail.hidden = true;
  detail.setAttribute('aria-label', 'Chi tiết nút');
  const svg = svgElement('svg', {'aria-label': 'Mạng Skill theo domain'});
  viewport.append(svg, tooltip, detail);

  function svgElement(tag, attrs, parent, label) {
    const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
    if (label !== undefined) element.textContent = label;
    parent?.appendChild(element);
    return element;
  }
  const links = [];
  function line(from, to, cls, parent = svg) {
    const layer = svgElement('g', {class: 'g-link'}, parent);
    const element = svgElement('line', {class: cls, 'vector-effect': 'non-scaling-stroke'}, layer);
    links.push({from, to, layer, element});
    return element;
  }
  for (const {from, to} of edges) line(from, to, 'g-edge');
  const traceLayer = svgElement('g', {class: 'g-trace'}, svg);
  const nodeLayers = new Map();
  const neighborsOnScreen = new Map();
  for (const node of [...nodes.values(), hub]) {
    const name = node.id && node.id !== node.label ? `${node.id} · ${node.label}` : node.label;
    const layer = svgElement('g', {class: 'g-node', 'aria-label': name}, svg);
    nodeLayers.set(node, layer);
    neighborsOnScreen.set(node, new Set(node.neighbors));
    layer.style.setProperty('--node-color', domains.get(node.domains?.[0])?.color || '#9eb0c4');
  }
  function circle(node, radius, cls) {
    return svgElement('circle', {r: radius, class: cls, 'vector-effect': 'non-scaling-stroke'}, nodeLayers.get(node));
  }
  let index = 0;
  for (const sequence of calls.sequences) {
    let previous = hub;
    for (const call of sequence) {
      const node = nodes.get(graphKey(call.kind, call.id));
      const tone = ['OK', 'SUCCEEDED', 'MEASURED'].includes(call.status) ? '' : ' g-fail';
      const delay = `${index++ * Math.min(250, 3200 / (calls.skills + calls.functions))}ms`;
      if (previous !== node) {
        line(previous, node, 'g-path' + tone, traceLayer).style.animationDelay = delay;
        neighborsOnScreen.get(previous).add(node);
        neighborsOnScreen.get(node).add(previous);
      }
      circle(node, node.radius + 3, 'g-lit' + tone).style.animationDelay = delay;
      previous = node;
    }
  }
  const hitTargets = new Map();
  for (const [node, layer] of nodeLayers) {
    const classes = node === hub ? (calls.sequences.length ? 'g-hub g-hub-active' : 'g-hub') :
      [node.kind === 'skill' ? 'g-skill' : 'g-fn', node.verified ? 'g-verified' : '',
        node.extra ? 'g-extra' : ''].filter(Boolean).join(' ');
    circle(node, node.radius, classes);
    if (node.chat_callable) circle(node, node.radius + 2.5, 'g-callable');
    if (node === hub) svgElement('text', {y: -17, 'text-anchor': 'middle', class: 'g-label'}, layer, node.label);
    hitTargets.set(circle(node, Math.max(node.radius + 3, 13), 'g-hit'), node);
  }

  const search = n('form', 'graph-toolbar');
  const input = n('input', 'graph-search');
  input.type = 'search';
  input.placeholder = 'ID hoặc tên Skill';
  input.setAttribute('aria-label', 'Tìm Skill theo ID hoặc tên');
  input.setAttribute('list', 'graph-skill-names');
  const suggestions = n('datalist');
  suggestions.id = 'graph-skill-names';
  const searchable = [...nodes.values()].filter(node => node.kind === 'skill');
  for (const node of searchable) {
    const option = n('option');
    option.value = node.id;
    option.label = node.label;
    suggestions.appendChild(option);
  }
  const find = n('button', 'light-btn', 'Tìm');
  find.type = 'submit';
  const fit = n('button', 'light-btn', 'Vừa khung');
  fit.type = 'button';
  search.append(input, suggestions, find, fit, expand);
  const searchStatus = n('p', 'graph-search-status');
  searchStatus.setAttribute('role', 'status');

  function showDetail(node) {
    const close = n('button', 'light-btn graph-detail-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Đóng chi tiết nút');
    close.addEventListener('click', () => {
      detail.hidden = true;
      input.focus();
    });
    const domainNames = (node.domains || []).map(id => domains.get(id).label).join(', ');
    const metadata = n('dl');
    const yesNo = value => value === undefined ? 'Không có dữ liệu' : value ? 'Có' : 'Không';
    for (const [label, value] of [
      ['ID', node.id || '—'],
      ['Domain', domainNames || '—'],
      ['Loại', node === hub ? 'Router / LLM' : node.type || (node.kind === 'skill' ? 'Skill' : 'Function')],
      ['Nghiệm thu mô phỏng', yesNo(node.verified)],
      ['Gọi được từ chat', yesNo(node.chat_callable)],
    ]) metadata.append(n('dt', '', label), n('dd', '', value));
    detail.replaceChildren(close, n('h3', '', node.label), metadata);
    if (node.extra) detail.appendChild(n('p', '', 'Ngoài đồ thị catalog'));
    function addNeighbors(label, neighbors) {
      if (!neighbors.length) return;
      const list = n('ul');
      for (const neighbor of neighbors) {
        const item = n('li');
        const button = n('button', 'graph-neighbor', `${neighbor.id} · ${neighbor.kind === 'skill' ? 'Skill' : 'Function'}`);
        button.type = 'button';
        button.addEventListener('click', () => centerOn(neighbor));
        item.appendChild(button);
        list.appendChild(item);
      }
      detail.append(n('h4', '', label), list);
    }
    addNeighbors('Liên kết catalog', [...(node.neighbors || [])]);
    addNeighbors('Kề trong dấu vết lượt hỏi', [...neighborsOnScreen.get(node)]
      .filter(neighbor => neighbor !== hub && !node.neighbors?.has(neighbor)));
    detail.hidden = false;
  }

  function searchText(value) {
    return value.trim().toLowerCase().normalize('NFD').replace(/\p{M}/gu, '').replaceAll('đ', 'd');
  }
  search.addEventListener('submit', event => {
    event.preventDefault();
    const query = searchText(input.value);
    if (!query) return;
    const target = searchable.find(node => searchText(node.id) === query)
      || searchable.find(node => searchText(node.label) === query)
      || searchable.find(node => searchText(node.id + ' ' + node.label).includes(query));
    searchStatus.textContent = target ? '' : 'Không tìm thấy Skill.';
    if (target) centerOn(target);
  });
  input.addEventListener('input', () => { searchStatus.textContent = ''; });

  const summary = calls.sequences.length
    ? `Lượt gần nhất có ${calls.skills} lượt gọi Skill và ${calls.functions} lượt gọi Function được ghi nhận.`
    : result ? 'Lượt gần nhất chưa ghi nhận cuộc gọi Skill hoặc Function.' : 'Gửi câu hỏi để xem những nút được gọi.';
  const verified = graph.nodes.filter(node => node.verified).length;
  const callable = graph.nodes.filter(node => node.chat_callable).length;
  const legend = n('ul', 'graph-legend');
  for (const [symbol, label] of [
    ['verified', `Chấm đặc · ${verified} Skill đã nghiệm thu mô phỏng (chấm rỗng nếu chưa)`],
    ['callable', `Viền đôi · ${callable} Skill có cấu hình gọi từ chat live hoặc replay`],
    ['function', 'Function theo màu domain liên kết · Xám nếu thiếu domain'],
    ['extra', 'Chấm vàng · Skill hoặc Function ngoài đồ thị catalog'],
    ['edge', 'Đường mảnh · Liên kết khai báo trong catalog'],
    ['path', 'Đường sáng · Dấu vết lượt hỏi (đỏ khi lỗi hoặc chưa xác minh)'],
  ]) {
    const item = n('li');
    item.append(n('span', 'graph-key key-' + symbol), n('span', '', label));
    legend.appendChild(item);
  }
  const domainLegend = n('details', 'graph-details');
  domainLegend.appendChild(n('summary', '', 'Màu theo domain'));
  const names = n('ul');
  for (const [id, {label, color}] of domains) {
    const item = n('li');
    const key = n('span', 'graph-key graph-domain-key');
    key.style.backgroundColor = color;
    item.append(key, n('span', '', `${id} · ${label}`));
    names.appendChild(item);
  }
  domainLegend.appendChild(names);
  const info = n('div', 'graph-info');
  holder.replaceChildren(n('p', 'graph-summary', summary), search, searchStatus, viewport, info);
  if (calls.sequences.length) {
    const trace = n('details', 'graph-details');
    trace.appendChild(n('summary', '', 'Chi tiết dấu vết'));
    for (const sequence of calls.sequences) {
      const list = n(calls.ordered ? 'ol' : 'ul');
      for (const call of sequence) {
        const name = nodes.get(graphKey(call.kind, call.id)).label;
        list.appendChild(n('li', '', `${call.kind === 'skill' ? 'Skill' : 'Function'} · ${name} · ${call.status || 'UNKNOWN'}${call.reused ? ' · Dùng lại evidence' : ''}`));
      }
      trace.appendChild(list);
    }
    info.appendChild(trace);
    if (!calls.linked || !calls.ordered) info.appendChild(n('p', 'inspector-note',
      'Bản ghi chỉ xác định một phần thứ tự. Các nhóm được tô riêng khi thiếu thông tin liên kết.'));
  }
  info.append(legend, domainLegend);

  const camera = {x: 0, y: 0, zoom: 1, width: 0, height: 0, scale: 1};
  const {halfSize} = layout;
  let followed = null;
  let hovered = null;
  let drag = null;
  function paintTooltip() {
    if (!hovered) return;
    const x = camera.width / 2 + (hovered.x - camera.x) * camera.scale;
    const y = camera.height / 2 + (hovered.y - camera.y) * camera.scale;
    tooltip.style.left = `${graphClamp(x + 8, 4, Math.max(4, camera.width - tooltip.offsetWidth - 4))}px`;
    tooltip.style.top = `${graphClamp(y + 10, 4, Math.max(4, camera.height - tooltip.offsetHeight - 4))}px`;
  }
  function setHover(node) {
    hovered = node;
    const adjacent = neighborsOnScreen.get(node);
    for (const [point, layer] of nodeLayers) {
      layer.classList.toggle('g-dim', !!node && point !== node && !adjacent.has(point));
      layer.classList.toggle('g-focus', point === node || !!adjacent?.has(point));
    }
    for (const {from, to, layer} of links) layer.classList.toggle('g-dim', !!node && from !== node && to !== node);
    tooltip.hidden = !node;
    if (node) {
      tooltip.textContent = node.label;
      paintTooltip();
    }
  }
  function scaleFor(zoom) {
    return Math.min(camera.width, camera.height) * zoom / (2 * halfSize);
  }
  function paintCamera() {
    if (followed) {
      camera.x = followed.x;
      camera.y = followed.y;
    }
    if (!camera.width || !camera.height) return;
    camera.scale = scaleFor(camera.zoom);
    const w = camera.width / camera.scale;
    const h = camera.height / camera.scale;
    svg.setAttribute('viewBox', `${camera.x - w / 2} ${camera.y - h / 2} ${w} ${h}`);
    paintTooltip();
  }
  function centerOn(node) {
    followed = node;
    camera.zoom = Math.max(camera.zoom, 2.3);
    paintCamera();
    showDetail(node);
  }
  fit.addEventListener('click', () => {
    followed = null;
    camera.x = 0;
    camera.y = 0;
    camera.zoom = 1;
    paintCamera();
  });
  function resize() {
    ({width: camera.width, height: camera.height} = svg.getBoundingClientRect());
    paintCamera();
  }
  function paintGraph() {
    for (const [node, layer] of nodeLayers) layer.setAttribute('transform', `translate(${node.x} ${node.y})`);
    for (const {from, to, element} of links) {
      element.setAttribute('x1', from.x);
      element.setAttribute('y1', from.y);
      element.setAttribute('x2', to.x);
      element.setAttribute('y2', to.y);
    }
    if (followed) paintCamera();
    else paintTooltip();
  }

  for (const [hit, node] of hitTargets) {
    hit.addEventListener('pointerenter', event => {
      if (!drag && event.pointerType !== 'touch') setHover(node);
    });
    hit.addEventListener('pointerleave', () => {
      if (hovered === node) setHover(null);
    });
  }
  function pointerOffset(event) {
    const {left, top} = svg.getBoundingClientRect();
    return {x: event.clientX - left - camera.width / 2, y: event.clientY - top - camera.height / 2};
  }
  svg.addEventListener('wheel', event => {
    if (drag || !camera.width || !camera.height) return;
    event.preventDefault();
    followed = null;
    const offset = pointerOffset(event);
    const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? camera.height : 1);
    camera.zoom = graphClamp(camera.zoom * Math.exp(-delta * .002), .55, 8);
    const newScale = scaleFor(camera.zoom);
    camera.x += offset.x * (1 / camera.scale - 1 / newScale);
    camera.y += offset.y * (1 / camera.scale - 1 / newScale);
    paintCamera();
  }, {passive: false});
  svg.addEventListener('pointerdown', event => {
    if (drag || event.button !== 0) return;
    const offset = pointerOffset(event);
    const node = hitTargets.get(event.target);
    drag = {node, id: event.pointerId, offset, x: camera.x, y: camera.y, moved: false,
      grabX: node ? node.x - camera.x - offset.x / camera.scale : 0,
      grabY: node ? node.y - camera.y - offset.y / camera.scale : 0};
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener('pointermove', event => {
    if (!drag || event.pointerId !== drag.id) return;
    const offset = pointerOffset(event);
    const dx = offset.x - drag.offset.x;
    const dy = offset.y - drag.offset.y;
    if (!drag.moved && Math.hypot(dx, dy) < 4) return;
    if (!drag.moved) {
      drag.moved = true;
      followed = null;
      setHover(null);
      svg.classList.add('g-dragging');
    }
    if (!drag.node) {
      camera.x = drag.x - dx / camera.scale;
      camera.y = drag.y - dy / camera.scale;
      paintCamera();
    } else if (drag.node !== hub) {
      const node = drag.node;
      node.pinned = true;
      const limit = halfSize - node.radius - 4;
      node.x = graphClamp(camera.x + offset.x / camera.scale + drag.grabX, -limit, limit);
      node.y = graphClamp(camera.y + offset.y / camera.scale + drag.grabY, -limit, limit);
      if (!reducedMotion.matches) {
        simulation.reheat();
        animate();
      }
      paintGraph();
    }
  });
  function endDrag(event) {
    if (!drag || event.pointerId !== drag.id) return;
    const {node, moved} = drag;
    drag = null;
    svg.classList.remove('g-dragging');
    if (node?.pinned && node !== hub) {
      node.pinned = false;
      simulation.reheat();
      animate();
    }
    if (!moved && node && event.type === 'pointerup') showDetail(node);
  }
  for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) svg.addEventListener(event, endDrag);

  const simulation = graphSimulation(layout);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let frame = null;
  function animate() {
    if (reducedMotion.matches) {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
      while (simulation.step()) { /* Settle before painting. */ }
      paintGraph();
    } else if (frame === null) {
      frame = requestAnimationFrame(tick);
    }
  }
  function tick() {
    frame = null;
    if (reducedMotion.matches) {
      animate();
      return;
    }
    let active = true;
    for (let i = 0; i < 4 && active; i++) active = simulation.step();
    paintGraph();
    if (active) animate();
  }
  const observer = new ResizeObserver(resize);
  observer.observe(svg);
  resize();
  if (!reducedMotion.matches) paintGraph();
  animate();
  return () => {
    observer.disconnect();
    if (frame !== null) cancelAnimationFrame(frame);
  };
}
function updateInput(){let ta=$('userInput');$('charCount').textContent=ta.value.length+'/2000';ta.style.height='auto';ta.style.height=Math.min(135,Math.max(34,ta.scrollHeight))+'px';$('sendBtn').disabled=state.busy||!ta.value.trim();}
$('sendBtn').addEventListener('click',()=>send());$('userInput').addEventListener('input',updateInput);$('userInput').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});$('clearBtn').addEventListener('click',clearChat);
$('sourceSelect').addEventListener('change',updateSource);
$('scenarioSelect').addEventListener('change',clearChat);
$('fixtureSelect').addEventListener('change',()=>{releaseChatSession();fixtureNote();});$('llmToggle').addEventListener('change',e=>{ $('modelField').hidden=!e.target.checked; });document.querySelectorAll('.seg').forEach(b=>b.addEventListener('click',()=>setMethod(b.dataset.method)));
document.querySelectorAll('.trace-tab').forEach(b=>b.addEventListener('click',()=>setTab(b.dataset.tab)));
document.querySelectorAll('.suggestion').forEach(b=>b.addEventListener('click',()=>{releaseChatSession();setFixture(b.dataset.fixture);send(b.dataset.query);}));
$('menuBtn').addEventListener('click', () => { $('sidebar').classList.toggle('open'); setInspector(false); });
$('traceBtn').addEventListener('click', () => setInspector($('inspector').hidden));
$('traceClose').addEventListener('click', () => { setInspector(false); $('traceBtn').focus(); });
$('inspector').addEventListener('keydown', event => {
  if (event.key === 'Escape') { setInspector(false); $('traceBtn').focus(); }
});
$('chatScroll').addEventListener('click', () => {
  $('sidebar').classList.remove('open');
  if (window.matchMedia('(max-width:1040px)').matches) setInspector(false);
});
loadConfig();updateInput();

// The launcher owns its mode, session and evidence independently of diagnostic chat.
(() => {
  const ui = id => document.getElementById(id);
  const launcher = {mode:'live', rows:[], selected:null, session:null, busy:false,
    generation:0, resultDeadline:null, sessionDeadline:null, timer:null, history:[]};
  const runnable = row => ['READY','DEGRADED'].includes(row?.availability);
  const describe = value => typeof value === 'string' ? value : JSON.stringify(value ?? null, null, 2);
  const scope = row => describe(row.runtime_scope ?? 'chưa xác minh');
  function status(message) { ui('skillSessionState').textContent = message; }
  function controls() {
    ui('skillInitialize').disabled = launcher.busy;
    const row = launcher.rows.find(item => item.skill_id === launcher.selected);
    ui('skillRun').disabled = launcher.busy || !launcher.session || !runnable(row);
    ui('skillSelection').textContent = row
      ? `${row.skill_id} · ${row.kind === 'laptop' ? 'Action laptop riêng' : 'Skill thiết kế'} · ${row.availability} · Scope: ${scope(row)} · ${row.reason || 'Không có lý do bổ sung.'}`
      : 'Chọn một Skill để xem phạm vi và lý do hỗ trợ.';
  }
  function renderCatalog() {
    const query = ui('skillSearch').value.trim().toLocaleLowerCase();
    const domain = ui('skillDomain').value;
    const supported = ui('skillSupported').value === 'supported';
    const rows = launcher.rows.filter(row => (!domain || row.domain === domain) &&
      (!supported || runnable(row)) && [row.skill_id,row.name,row.reason].some(value => normalize(value).toLocaleLowerCase().includes(query)));
    const box = ui('skillCatalog'); box.replaceChildren();
    for (const kind of ['design','igate_simulated','laptop']) {
      const group = rows.filter(row => row.kind === kind);
      if (!group.length) continue;
      const title = {laptop:'Action laptop',igate_simulated:'Skill iGate mô phỏng',design:'Skill thiết kế'}[kind];
      box.appendChild(n('h3','skill-group-title',title));
      for (const row of group) {
        const button = n('button', 'skill-row'); button.type = 'button';
        button.setAttribute('aria-pressed',String(launcher.selected === row.skill_id));
        button.appendChild(n('strong','',`${row.skill_id} · ${row.name}`));
        button.appendChild(n('span',runnable(row) ? 'skill-ready' : 'network-warning',`${row.availability} · ${row.domain}`));
        button.appendChild(n('small','',`${row.reason || 'Chưa có lý do bổ sung.'} · Scope: ${scope(row)}`));
        button.addEventListener('click',() => { launcher.selected = row.skill_id; renderCatalog(); });
        box.appendChild(button);
      }
    }
    if (!rows.length) box.appendChild(n('p','network-note','Không có Skill phù hợp bộ lọc.'));
    controls();
  }
  function acceptCatalog(catalog) {
    if (catalog.mode !== launcher.mode || !Array.isArray(catalog.rows)) throw new Error('Danh mục trả về sai nguồn hoặc sai định dạng.');
    launcher.rows = [...catalog.rows, ...(catalog.igate_rows || [])];
    const currentDomain = ui('skillDomain').value;
    ui('skillDomain').replaceChildren();
    const all = n('option','','Tất cả domain'); all.value = ''; ui('skillDomain').appendChild(all);
    for (const domain of [...new Set(launcher.rows.map(row => row.domain))].sort()) {
      const option = n('option','',domain); option.value = domain; ui('skillDomain').appendChild(option);
    }
    if (launcher.rows.some(row => row.domain === currentDomain)) ui('skillDomain').value = currentDomain;
    const counts = Object.entries(catalog.counts || {}).map(([key,value]) => `${key}: ${describe(value)}`).join(' · ');
    const igate = catalog.igate_rows?.length ? ` + ${catalog.igate_rows.length} Skill iGate mô phỏng` : '';
    ui('skillCatalogCounts').textContent = `${catalog.design_total} Skill thiết kế + ${catalog.native_total} action laptop${igate}. ${counts}`;
    renderCatalog();
  }
  async function request(path, body) {
    const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    let data;
    try { data = await response.json(); } catch (_) { throw new Error(`HTTP ${response.status}: phản hồi không phải JSON.`); }
    if (!response.ok) {
      const error = new Error(describe(data.reason || data.error || data.detail || `HTTP ${response.status}`));
      error.sessionExpired = [404,409,410].includes(response.status) || /session.*(expir|invalid|unknown)|reinit/i.test(describe(data));
      throw error;
    }
    return data;
  }
  function closeSession(sessionId) {
    if (!sessionId) return;
    // Best-effort resource cleanup; never re-adopt a session if its close fails.
    request('/api/skills/close',{session_id:sessionId}).catch(() => {});
  }
  // Cap a monotonic countdown by both the supplied TTL and the absolute expiry.
  function deadline(ttl, absolute) {
    let remaining = typeof ttl === 'number' && Number.isFinite(ttl) ? Math.max(0, ttl * 1000) : 0;
    if (absolute !== undefined && absolute !== null) {
      const date = new Date(absolute).getTime();
      remaining = Number.isFinite(date) ? Math.min(remaining, Math.max(0,date - Date.now())) : 0;
    }
    return performance.now() + remaining;
  }
  function clearResult(message) {
    launcher.resultDeadline = null;
    ui('skillResult').replaceChildren();
    if (message) ui('skillResult').appendChild(n('p','network-warning',message));
  }
  function expire() {
    if (launcher.session && performance.now() >= launcher.sessionDeadline) {
      launcher.session = null; launcher.sessionDeadline = null;
      clearResult('Phiên hết hạn · đã xóa số đo. Khởi tạo phiên để chạy tiếp.');
      status('SESSION EXPIRED · Cần khởi tạo lại.'); controls();
    }
    if (launcher.resultDeadline !== null && performance.now() >= launcher.resultDeadline) {
      clearResult('STALE · Đã xóa các fact hết TTL. Chạy Skill để đo lại; lịch sử chỉ lưu tham chiếu lượt chạy.');
    }
  }
  function renderHistory() {
    ui('skillHistoryCount').textContent = launcher.history.length;
    ui('skillHistory').replaceChildren();
    for (const item of launcher.history) ui('skillHistory').appendChild(n('li','',item));
  }
  function renderResult(result) {
    const box = ui('skillResult'); box.replaceChildren();
    box.appendChild(n('h3','',`${result.skill_id} · ${result.status}`));
    box.appendChild(n('p','network-warning',result.synthetic_only ? 'REPLAY · CHỈ DỮ LIỆU MÔ PHỎNG · không phải số đo laptop/router thật.' : 'LIVE · phép đo Linux laptop thật, theo scope của từng fact.'));
    box.appendChild(n('p','',result.summary || result.reason || 'Chưa có kết luận.'));
    if (result.reason && result.reason !== result.summary) box.appendChild(n('p','network-note',result.reason));
    box.appendChild(n('p','network-note',`Nguồn: ${result.mode} · Calls lượt này / tổng: ${result.calls_this_run} / ${result.calls_total} · Tái sử dụng: ${(result.reused_ports || []).join(', ') || 'không'} · Evidence: ${(result.evidence_ids || []).join(', ') || 'không'}`));
    const snapshot = result.snapshot || {};
    launcher.resultDeadline = Object.keys(snapshot.facts || {}).length ? deadline(snapshot.expires_in_s,snapshot.expires_at) : null;
    for (const [port,fact] of Object.entries(snapshot.facts || {})) {
      launcher.resultDeadline = Math.min(launcher.resultDeadline,deadline(fact.expires_in_s));
      const detail = n('details','network-fact'); detail.appendChild(n('summary','',port));
      detail.appendChild(n('pre','skill-fact',describe({value:fact.value,source:fact.source,target:fact.target,scope:fact.scope,
        observed_at:fact.observed_at,evidence_id:fact.evidence_id,expires_in_s:fact.expires_in_s})));
      box.appendChild(detail);
    }
    box.appendChild(n('p','network-note',`Snapshot TTL: ${snapshot.expires_in_s ?? 0}s · Hết hạn: ${snapshot.expires_at || 'chưa xác minh'}`));
    const missing = [...new Set([...(result.missing_ports || []),...(snapshot.missing_ports || [])])];
    if (missing.length) box.appendChild(n('p','network-warning',`Chưa có port: ${missing.join(', ')}`));
    for (const limitation of result.limitations || []) box.appendChild(n('p','network-warning',describe(limitation)));
    if (result.steps?.length) {
      const steps = n('details','network-fact'); steps.appendChild(n('summary','','Các bước thực thi'));
      steps.appendChild(n('pre','skill-fact',describe(result.steps))); box.appendChild(steps);
    }
    launcher.history.unshift(`${new Date().toLocaleTimeString('vi-VN')} · ${result.mode} · ${result.skill_id} · ${result.status} · Calls ${result.calls_this_run}/${result.calls_total} · Evidence ${(result.evidence_ids || []).join(', ') || 'không'} · tham chiếu lịch sử, không khẳng định số đo còn mới`);
    launcher.history = launcher.history.slice(0,30); renderHistory(); expire();
  }
  async function loadCatalog() {
    const generation = launcher.generation;
    try {
      const catalog = await request(`/api/skills?mode=${encodeURIComponent(launcher.mode)}`);
      if (generation !== launcher.generation) return;
      acceptCatalog(catalog); status('Chưa khởi tạo phiên. Danh mục không chạy phép đo.');
    } catch (error) { if (generation === launcher.generation) status(`Không tải được danh mục: ${error.message}`); }
  }
  function resetMode() {
    closeSession(launcher.session);
    launcher.generation++; launcher.mode = ui('skillSource').value;
    launcher.session = null; launcher.sessionDeadline = null; launcher.rows = []; launcher.selected = null; launcher.busy = false;
    launcher.history = []; clearResult(); renderHistory(); renderCatalog();
    ui('skillCatalogCounts').textContent = '';
    ui('skillSourceNotice').textContent = launcher.mode === 'replay'
      ? 'REPLAY FIRST BATCH · chỉ mô phỏng B02/B03/B05; không chứng minh laptop hoặc router thật.'
      : 'LIVE · phép đo thật trên Linux laptop. SK01/A08 chỉ có scope local; action laptop riêng không hoàn thành 120 Skill thiết kế.';
    status('Đang tải danh mục; chưa có phiên, chưa đo.'); loadCatalog();
  }
  ui('skillInitialize').addEventListener('click',async () => {
    const generation = ++launcher.generation;
    closeSession(launcher.session);
    let createdSession = null;
    launcher.busy = true; launcher.session = null; launcher.sessionDeadline = null;
    launcher.history = []; clearResult(); renderHistory(); controls(); status('Đang khởi tạo phiên READ; chưa chạy Skill.');
    try {
      const result = await request('/api/skills/session',{mode:launcher.mode});
      createdSession = result.session_id;
      if (generation !== launcher.generation) { closeSession(createdSession); return; }
      if (result.mode !== launcher.mode || !result.session_id) throw new Error('Phiên trả về sai nguồn hoặc thiếu ID.');
      acceptCatalog(result.catalog);
      launcher.session = result.session_id; launcher.sessionDeadline = deadline(result.expires_in_s);
      status(`Phiên ${result.mode} đã khởi tạo · TTL ${result.expires_in_s}s. Chọn Skill rồi bấm Chạy.`); expire();
    } catch (error) {
      closeSession(createdSession);
      if (generation === launcher.generation) status(`Không khởi tạo được phiên: ${error.message}`);
    }
    finally { if (generation === launcher.generation) { launcher.busy = false; controls(); } }
  });
  ui('skillRun').addEventListener('click',async () => {
    expire();
    const row = launcher.rows.find(item => item.skill_id === launcher.selected);
    if (launcher.busy || !launcher.session || !runnable(row)) return;
    const generation = launcher.generation, session = launcher.session, skillId = row.skill_id;
    launcher.busy = true; controls(); clearResult(); status(`Đang chạy ${skillId} · ${launcher.mode} · Scope: ${scope(row)}`);
    try {
      const result = await request('/api/skills/run',{session_id:session,skill_id:skillId});
      if (generation !== launcher.generation || session !== launcher.session) return;
      if (result.mode !== launcher.mode || result.session_id !== session || result.skill_id !== skillId || result.synthetic_only !== (launcher.mode === 'replay')) throw new Error('Kết quả sai phiên, Skill hoặc nguồn; không hiển thị evidence.');
      status(`${skillId} · ${result.status} · ${launcher.mode}.`); renderResult(result);
    } catch (error) {
      if (generation !== launcher.generation) return;
      clearResult();
      if (error.sessionExpired) { launcher.session = null; launcher.sessionDeadline = null; }
      status(`Lỗi: ${error.message}${error.sessionExpired ? ' · Cần khởi tạo lại phiên.' : ''}`);
    } finally { if (generation === launcher.generation) { launcher.busy = false; expire(); controls(); } }
  });
  ui('skillSource').addEventListener('change',resetMode);
  for (const id of ['skillSearch','skillDomain','skillSupported']) ui(id).addEventListener(id === 'skillSearch' ? 'input' : 'change',renderCatalog);
  document.addEventListener('visibilitychange',expire);
  window.addEventListener('focus',expire);
  launcher.timer = setInterval(expire,1000);
  loadCatalog();
})();

$('historyBtn').addEventListener('click',async()=>{try{const r=await fetch('/api/skills/history');if(!r.ok)throw Error('Không đọc được lịch sử phiên');const data=await r.json();const bubble=message('assistant','Lịch sử phiên READ cục bộ; không lưu nguyên văn hội thoại.','LỊCH SỬ');for(const item of data.sessions||[]){bubble.appendChild(n('div','',new Date(item.saved_at*1000).toLocaleString()+' · '+item.status+' · '+item.calls+' phép đo · '+item.facts+' facts'));}if(!data.sessions?.length)bubble.appendChild(n('div','','Chưa có phiên đã lưu.'));}catch(e){toast(e.message);}});
