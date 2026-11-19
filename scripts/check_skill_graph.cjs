// Exercise the production graph projection and SVG renderer without a browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag, className = '', textContent = '') {
    Object.assign(this, {tag, className, textContent, children: [], attrs: {}, style: {}});
  }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(key, value) { this.attrs[key] = value; }
}

const sandbox = vm.createContext({
  n: (...args) => new Element(...args),
  document: {createElementNS: (namespaceURI, tag) => Object.assign(new Element(tag), {namespaceURI})},
});
const source = fs.readFileSync(path.join(__dirname, '../web_gateway/static/app.js'), 'utf8');
const start = source.indexOf('function planCalls(');
const end = source.indexOf('function updateInput()', start);
assert.ok(start >= 0 && end > start);
vm.runInContext(source.slice(start, end), sandbox);
const {runCalls, layoutGraph, drawGraph} = sandbox;
const plain = value => JSON.parse(JSON.stringify(value));
const ids = trace => plain(trace.sequences.map(sequence => sequence.map(call => call.id)));
const terminal = (function_id, state = 'SUCCEEDED') => ({
  function_id, state, history: [{from: 'READY', to: 'RUNNING'}, {from: 'RUNNING', to: state}],
});

if (process.argv[2] === '--chat') {
  const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
  const trace = runCalls(payload);
  assert.equal(trace.functions, payload.calls);
  assert.equal(trace.skills, payload.skill_runs?.length || 0);
  assert.ok(trace.ordered && trace.linked && trace.functions > 0);
  console.log(JSON.stringify({
    mode: payload.mode, status: payload.case_status, calls: payload.calls, steps: ids(trace),
  }));
  process.exit(0);
}

const live = {
  mode: 'linux_live',
  calls: 3,
  calls_total: 4,
  skill_runs: [
    {skill_id: 'laptop.route.inspect', status: 'MEASURED', calls_this_run: 2, reused_ports: []},
    {skill_id: 'A08', status: 'PARTIAL', calls_this_run: 1, reused_ports: []},
  ],
  // Plan export insertion order can differ from the READY selection order.
  plans: [
    {nodes: {'laptop.route': terminal('laptop.route'), 'clients.resolve': terminal('clients.resolve')}},
    {nodes: {'expansion.client_association': terminal('expansion.client_association', 'FAILED'),
      'laptop.wifi': {function_id: 'laptop.wifi', state: 'BLOCKED'}}},
  ],
  timeline: [
    {index: 1, function_id: 'laptop.route', node_state: 'SUCCEEDED', status: 'OK'},
    {index: 2, function_id: 'clients.resolve', node_state: 'SUCCEEDED', status: 'NO_LONGER_VALID'},
    {index: 3, function_id: 'expansion.client_association', node_state: 'FAILED', status: 'UNVERIFIED'},
    {index: 4, function_id: 'laptop.wifi', node_state: 'BLOCKED', status: 'UNVERIFIED'},
  ],
  function_retrievals: [
    {selected_ready: 'old.call'}, {selected_ready: 'clients.resolve'},
    {selected_ready: 'laptop.route'}, {selected_ready: 'expansion.client_association'},
  ],
};
const liveTrace = runCalls(live);
assert.deepEqual(ids(liveTrace), [['laptop.route.inspect', 'clients.resolve', 'laptop.route', 'A08',
  'expansion.client_association']]);
assert.equal(liveTrace.sequences[0][1].status, 'SUCCEEDED');
assert.equal(liveTrace.sequences[0][4].status, 'FAILED');
assert.ok(liveTrace.ordered && liveTrace.linked);

const replay = {
  mode: 'synthetic_replay', calls: 3,
  timeline: [{index: 3, function_id: 'dns.probe', status: 'TIMEOUT'},
    {index: 1, function_id: 'wan.routes', status: 'OK'},
    {index: 2, function_id: 'dns.config', status: 'OK'}],
  plans: [{nodes: {pending: {function_id: 'client.probe', state: 'READY'}}}],
};
assert.deepEqual(ids(runCalls(replay)), [['wan.routes', 'dns.config', 'dns.probe']]);
assert.deepEqual(ids(runCalls({...replay, timeline: [], calls: 0})), []);

const replaySkill = {
  mode: 'synthetic_replay', calls: 1,
  skill_runs: [{skill_id: 'B02', status: 'MEASURED', calls_this_run: 1},
    {skill_id: 'B03', status: 'MEASURED', calls_this_run: 0, reused_ports: ['expansion.ssid_config']}],
  plans: [{nodes: {'expansion.radio_health': terminal('expansion.radio_health')}}],
};
assert.deepEqual(ids(runCalls(replaySkill)), [['B02', 'expansion.radio_health', 'B03']]);
assert.equal(runCalls(replaySkill).sequences[0][2].reused, true);
const separate = runCalls({...live, skill_runs: live.skill_runs.slice(0, 1)});
assert.equal(separate.linked, false);
assert.deepEqual(ids(separate), [['laptop.route.inspect'],
  ['clients.resolve', 'laptop.route', 'expansion.client_association']]);
const unordered = runCalls({...live, function_retrievals: []});
assert.equal(unordered.ordered, false);
assert.deepEqual(ids(unordered).slice(1), [['laptop.route'], ['clients.resolve'], ['expansion.client_association']]);

const retried = terminal('laptop.route');
retried.history.unshift(...terminal('laptop.route', 'FAILED').history);
retried.output_evidence = {'laptop.route': 'e2'};
const replan = runCalls({
  mode: 'linux_live', calls: 2, skill_runs: [],
  plans: [{nodes: {'laptop.route': retried}}, {nodes: {'laptop.route': retried},
    audit: [{operator: 'GLOBAL_REPLAN', reused_evidence: ['e2']}]}],
  function_retrievals: [{selected_ready: 'laptop.route'}, {selected_ready: 'laptop.route'}],
});
assert.ok(replan.ordered);
assert.deepEqual(ids(replan), [['laptop.route', 'laptop.route']]);
assert.deepEqual(plain(replan.sequences[0].map(call => call.status)), ['FAILED', 'SUCCEEDED']);

const groups = Object.fromEntries(Array.from('ABCDEFGHIJKLMNO', id => [id, 'Domain ' + id]));
const skills = Object.keys(groups).flatMap(group => Array.from({length: 8}, (_, i) => ({
  id: group + '0' + (i + 1), kind: 'skill', label: group + ' skill ' + (i + 1), group,
  verified: i === 0, chat_callable: i === 7,
})));
const functions = Array.from({length: 72}, (_, i) => {
  const id = i ? 'expansion.function_' + i : 'expansion.client_association';
  return {id, kind: 'function', label: id};
});
const graph = {groups, nodes: [...skills, ...functions], edges: [{source: 'A08', target: functions[0].id}]};
const layout = layoutGraph(graph, liveTrace.sequences);
assert.equal(layout.panels.length, 15);
assert.equal(layout.nodes.size, 195);
assert.equal(new Set(Array.from(layout.nodes.values(), node => node.x + ':' + node.y)).size, 195);
for (const node of layout.nodes.values()) {
  assert.ok(node.x >= 7 && node.x < layout.width - 7 && node.y >= 7 && node.y < layout.height - 7);
}
assert.ok(layout.nodes.get('skill:laptop.route.inspect').extra);
assert.ok(layout.nodes.get('function:clients.resolve').extra);
assert.ok(!layout.nodes.has('function:laptop.wifi'));

const holder = new Element('div');
drawGraph(holder, graph, live);
const svg = holder.children.find(child => child.className === 'graph-canvas').children[0];
const lines = svg.children.filter(child => child.tag === 'line' && child.attrs.class.startsWith('g-path'));
const rings = svg.children.filter(child => child.tag === 'circle' && child.attrs.class.startsWith('g-lit'));
assert.equal(lines.length, 5);
assert.equal(rings.length, 5);
assert.deepEqual(rings.map(ring => ring.style.animationDelay), ['0ms', '250ms', '500ms', '750ms', '1000ms']);
for (const [i, line] of lines.entries()) {
  assert.equal(line.style.animationDelay, rings[i].style.animationDelay);
  assert.deepEqual([line.attrs.x2, line.attrs.y2], [rings[i].attrs.cx, rings[i].attrs.cy]);
  if (i) assert.deepEqual([line.attrs.x1, line.attrs.y1], [rings[i - 1].attrs.cx, rings[i - 1].attrs.cy]);
}
assert.ok(lines.at(-1).attrs.class.includes('g-fail'));
assert.ok(svg.children.some(child => child.children.some(title => title.textContent === 'Domain A')));
assert.ok(svg.children.some(child => child.children.some(title => title.textContent.includes('laptop.route.inspect'))));

const replayLayout = layoutGraph(graph, runCalls(replay).sequences);
assert.ok(replayLayout.nodes.get('function:dns.probe').extra);
assert.ok(!replayLayout.nodes.has('skill:laptop.route.inspect'));
drawGraph(holder, graph, replay);
const replaySvg = holder.children.find(child => child.className === 'graph-canvas').children[0];
assert.equal(replaySvg.children.filter(child => child.attrs.class?.startsWith('g-lit')).length, 3);
assert.ok(!replaySvg.children.some(child => child.attrs.class?.includes('g-skill')
  && child.attrs.class.includes('g-extra')));

const css = fs.readFileSync(path.join(__dirname, '../web_gateway/static/app.css'), 'utf8');
assert.match(css, /@media\(prefers-reduced-motion:reduce\)\s*{[^@]+\.g-path,\.g-lit\s*{\s*animation:none;\s*opacity:1;/);
console.log('Skill graph: PASS (live/replay order, omitted calls, node layout, SVG highlights)');
