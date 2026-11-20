// Exercise the production force layout, SVG interaction and trace projection without a browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag, className = '', textContent = '') {
    Object.assign(this, {tag, className, textContent, children: [], attrs: {}, events: {},
      style: {setProperty(key, value) { this[key] = value; }}, isConnected: true,
      width: 308, height: 400, offsetWidth: 95, offsetHeight: 25});
    const classes = () => new Set((this.attrs.class ?? this.className).split(' ').filter(Boolean));
    const toggle = (key, on) => {
      const names = classes();
      if (on) names.add(key);
      else names.delete(key);
      this.attrs.class = [...names].join(' ');
    };
    this.classList = {toggle, add: key => toggle(key, true), remove: key => toggle(key, false),
      contains: key => classes().has(key)};
  }
  insertBefore(child, next) {
    if (child.parentNode) {
      const siblings = child.parentNode.children;
      siblings.splice(siblings.indexOf(child), 1);
    }
    this.children.splice(next ? this.children.indexOf(next) : this.children.length, 0, child);
    child.parentNode = this;
    return child;
  }
  appendChild(child) { return this.insertBefore(child, null); }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  replaceChildren(...children) {
    this.children.forEach(child => { child.parentNode = null; });
    this.children = [];
    this.append(...children);
  }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(type, callback) { (this.events[type] ??= []).push(callback); }
  dispatch(type, init = {}) {
    const event = {type, target: this, ...init,
      preventDefault() { this.defaultPrevented = true; },
      stopPropagation() { this.stopped = true; }};
    for (const callback of this.events[type] || []) callback(event);
    return event;
  }
  focus() { this.focused = true; }
  getBoundingClientRect() { return {width: this.width, height: this.height, left: 0, top: 0}; }
  setPointerCapture(id) { this.captured = id; }
  showModal() { this.open = true; }
  close() { this.open = false; this.dispatch('close'); }
}

const frames = new Map();
const observers = new Map();
const motion = {matches: false};
let nextFrame = 0;
const sandbox = vm.createContext({
  n: (...args) => new Element(...args),
  document: {createElementNS: (namespaceURI, tag) => Object.assign(new Element(tag), {namespaceURI})},
  window: {matchMedia: query => {
    assert.equal(query, '(prefers-reduced-motion: reduce)');
    return motion;
  }},
  ResizeObserver: class {
    constructor(callback) { this.callback = callback; }
    observe(svg) { this.svg = svg; observers.set(svg, this.callback); }
    disconnect() { observers.delete(this.svg); }
  },
  requestAnimationFrame: cb => { frames.set(++nextFrame, cb); return nextFrame; },
  cancelAnimationFrame: id => frames.delete(id),
});
const source = fs.readFileSync(path.join(__dirname, '../web_gateway/static/app.js'), 'utf8');
const start = source.indexOf('function planCalls(');
const end = source.indexOf('function updateInput()', start);
assert.ok(start >= 0 && end > start);
vm.runInContext(source.slice(start, end), sandbox);
const {runCalls, layoutGraph, graphSimulation, createGraphPanel, drawGraph} = sandbox;
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
  id: group + '0' + (i + 1), kind: 'skill', label: group === 'A' && i === 7 ? 'Đường truyền A tám' : group + ' skill ' + (i + 1),
  group, type: 'direct', verified: i === 0, chat_callable: i === 7,
})));
const functions = Array.from({length: 72}, (_, i) => {
  const id = i ? 'expansion.function_' + i : 'expansion.client_association';
  return {id, kind: 'function', label: id};
});
const graph = {
  groups, nodes: [...skills, ...functions],
  edges: [
    {source: 'A08', target: functions[0].id},
    ...skills.filter((_, i) => i % 8 !== 7).map((node, i) => ({
      source: node.id, target: functions[1 + i % 71].id,
    })),
    ...skills.slice(8, 31).map((node, i) => ({source: node.id, target: functions[32 + i].id})),
  ],
};
const coords = node => [node.x, node.y];
const positions = layout => Array.from(layout.nodes.values(), coords);
const finite = layout => {
  for (const node of [...layout.nodes.values(), layout.hub]) {
    assert.ok([node.x, node.y, node.vx, node.vy].every(Number.isFinite));
  }
};
function settle(simulation, layout, limit) {
  let steps = 0;
  let next;
  do {
    steps++;
    next = simulation.step();
    finite(layout);
    assert.ok(steps <= limit, 'force simulation must stop');
  } while (next);
  const final = positions(layout);
  assert.equal(simulation.step(), false);
  assert.deepEqual(positions(layout), final);
  return steps;
}
const layout = layoutGraph(graph, liveTrace.sequences);
assert.equal(layout.domains.size, 15);
assert.equal(layout.nodes.size, 195);
assert.equal(layout.edges.length, 129);
assert.equal(new Set(Array.from(layout.domains.values(), domain => domain.color)).size, 15);
const seeded = positions(layout);
const simulation = graphSimulation(layout);
const steps = settle(simulation, layout, 120);
assert.notDeepEqual(positions(layout), seeded);
assert.equal(new Set(positions(layout).map(point => point.join(':'))).size, 195);
for (const node of layout.nodes.values()) {
  assert.ok(Math.max(Math.abs(node.x), Math.abs(node.y)) + node.radius + 4 <= layout.halfSize);
  assert.ok(Math.hypot(node.vx, node.vy) < .1, 'node must be nearly at rest');
}
const shuffled = layoutGraph({...graph, nodes: [...graph.nodes].reverse(), edges: [...graph.edges].reverse(),
  groups: Object.fromEntries(Object.entries(groups).reverse())}, liveTrace.sequences);
assert.deepEqual(positions(shuffled), seeded);
assert.equal(settle(graphSimulation(shuffled), shuffled, 120), steps);
assert.deepEqual(positions(shuffled), positions(layout));
assert.ok(layout.nodes.get('skill:laptop.route.inspect').extra);
assert.ok(layout.nodes.get('function:clients.resolve').extra);
assert.ok(!layout.nodes.has('function:laptop.wifi'));
const mainSkill = layout.nodes.get('skill:A08');
const mainFunction = layout.nodes.get('function:expansion.client_association');
assert.ok(mainSkill.radius > layout.nodes.get('skill:F08').radius);
assert.deepEqual(plain(mainFunction.domains), ['A']);
assert.ok(mainSkill.neighbors.has(mainFunction) && mainFunction.neighbors.has(mainSkill));
const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
assert.ok(distance(mainSkill, mainFunction) < distance(mainSkill, layout.nodes.get('skill:O08')));
const original = coords(mainFunction);
mainSkill.x += 100;
mainSkill.pinned = true;
const pinned = coords(mainSkill);
simulation.reheat();
const dragSteps = settle(simulation, layout, 48);
assert.deepEqual(coords(mainSkill), pinned);
assert.notDeepEqual(coords(mainFunction), original);
mainSkill.pinned = false;
simulation.reheat();
assert.equal(settle(simulation, layout, 48), dragSteps);
assert.notDeepEqual(coords(mainSkill), pinned);

function flushFrames(limit = 30) {
  let count = 0;
  while (frames.size) {
    assert.equal(frames.size, 1, 'at most one scheduled simulation frame');
    assert.ok(++count <= limit, 'animations must stop scheduling frames');
    const [[id, callback]] = frames;
    frames.delete(id);
    callback();
  }
  return count;
}
const all = (root, predicate) => [
  ...(predicate(root) ? [root] : []), ...root.children.flatMap(child => all(child, predicate)),
];
const cls = (root, name) => all(root, element => element.classList.contains(name));
const tag = (root, name) => all(root, element => element.tag === name);
const trans = layer => layer.attrs.transform.match(/^translate\(([^ ]+) ([^)]+)\)$/).slice(1).map(Number);
const box = svg => svg.attrs.viewBox.split(' ').map(Number);
const center = ([x, y, w, h]) => [x + w / 2, y + h / 2];
const approx = (a, b) => assert.ok(a.every((value, i) => Math.abs(value - b[i]) < 1e-8));
const content = new Element('div');
const panel = createGraphPanel(content);
const {holder, expand, overlay} = panel;
const disposeLive = drawGraph(panel, graph, live);
const frameCount = flushFrames();
assert.equal(frameCount, Math.ceil(steps / 4));
const svg = tag(holder, 'svg')[0];
assert.equal(cls(svg, 'g-node').length, 196);
assert.equal(tag(svg, 'rect').length, 0);
assert.equal(cls(svg, 'g-edge').length, 129);
assert.ok(!all(holder, element => 'style' in element.attrs).length);
const lines = cls(svg, 'g-path');
const rings = cls(svg, 'g-lit').sort((a, b) => parseFloat(a.style.animationDelay) - parseFloat(b.style.animationDelay));
assert.equal(lines.length, 5);
assert.equal(rings.length, 5);
assert.deepEqual(rings.map(ring => ring.style.animationDelay), ['0ms', '250ms', '500ms', '750ms', '1000ms']);
const nodeLayer = id => cls(svg, 'g-node').find(layer => layer.attrs['aria-label'].split(' · ')[0] === id);
const calledIds = ids(liveTrace)[0];
for (const [i, line] of lines.entries()) {
  assert.equal(line.style.animationDelay, rings[i].style.animationDelay);
  assert.equal(rings[i].parentNode, nodeLayer(calledIds[i]));
  assert.deepEqual([line.attrs.x2, line.attrs.y2], trans(rings[i].parentNode));
  const previous = i ? rings[i - 1].parentNode : nodeLayer('Router / LLM');
  assert.deepEqual([line.attrs.x1, line.attrs.y1], trans(previous));
}
assert.ok(lines.at(-1).classList.contains('g-fail'));
assert.ok(rings.at(-1).classList.contains('g-fail'));
assert.ok(all(holder, element => element.textContent === 'A · Domain A').length);
assert.ok(nodeLayer('laptop.route.inspect'));
assert.equal(cls(svg, 'g-extra').length, 3);
assert.equal(cls(svg, 'g-callable').length, 15);
assert.equal(cls(svg, 'g-verified').length, 15);

const skillLayer = nodeLayer('A08');
const fnLayer = nodeLayer('expansion.client_association');
assert.equal(skillLayer.style['--node-color'], fnLayer.style['--node-color']);
const hit = cls(skillLayer, 'g-hit')[0];
const unrelated = nodeLayer('O08');
const tooltip = cls(holder, 'graph-tooltip')[0];
hit.dispatch('pointerenter', {pointerType: 'mouse'});
assert.equal(tooltip.textContent, 'Đường truyền A tám');
assert.equal(tooltip.hidden, false);
assert.ok(skillLayer.classList.contains('g-focus'));
assert.ok(fnLayer.classList.contains('g-focus'));
assert.ok(unrelated.classList.contains('g-dim'));
hit.dispatch('pointerleave');
assert.equal(tooltip.hidden, true);
assert.equal(cls(svg, 'g-dim').length, 0);

const detail = cls(holder, 'graph-node-detail')[0];
const pointer = {pointerId: 7, button: 0, clientX: 150, clientY: 100};
svg.dispatch('pointerdown', {...pointer, target: hit});
assert.equal(svg.captured, 7);
svg.dispatch('pointerup', pointer);
assert.equal(detail.hidden, false);
assert.deepEqual(tag(detail, 'dd').map(dd => dd.textContent), ['A08', 'Domain A', 'direct', 'Không', 'Có']);
assert.equal(tag(detail, 'h3')[0].textContent, 'Đường truyền A tám');
assert.equal(cls(detail, 'graph-neighbor')[0].textContent, 'expansion.client_association · Function');
const extraHit = cls(nodeLayer('laptop.route.inspect'), 'g-hit')[0];
svg.dispatch('pointerdown', {...pointer, target: extraHit});
svg.dispatch('pointerup', pointer);
assert.deepEqual(tag(detail, 'dd').map(dd => dd.textContent),
  ['laptop.route.inspect', '—', 'Skill', 'Không có dữ liệu', 'Không có dữ liệu']);
assert.equal(tag(detail, 'h4')[0].textContent, 'Kề trong dấu vết lượt hỏi');
assert.equal(cls(detail, 'graph-neighbor')[0].textContent, 'clients.resolve · Function');

const search = tag(holder, 'form')[0];
const input = tag(search, 'input')[0];
for (const query of ['a08', 'Duong truyen A tam']) {
  input.value = query;
  assert.equal(search.dispatch('submit').defaultPrevented, true);
  approx(center(box(svg)), trans(skillLayer));
}
input.value = 'missing graph skill';
search.dispatch('submit');
assert.equal(cls(holder, 'graph-search-status')[0].textContent, 'Không tìm thấy Skill.');
const beforeZoom = box(svg);
const cursorWorld = ([x, y, w, h]) => [x + w * pointer.clientX / svg.width, y + h * pointer.clientY / svg.height];
assert.equal(svg.dispatch('wheel', {...pointer, deltaY: -100, deltaMode: 0}).defaultPrevented, true);
assert.ok(box(svg)[2] < beforeZoom[2]);
approx(cursorWorld(box(svg)), cursorWorld(beforeZoom));
const beforePan = center(box(svg));
svg.dispatch('pointerdown', pointer);
svg.dispatch('pointermove', {...pointer, clientX: 165});
svg.dispatch('pointerup', pointer);
assert.ok(center(box(svg))[0] < beforePan[0]);
approx([center(box(svg))[1]], [beforePan[1]]);

const beforeDrag = trans(skillLayer);
svg.dispatch('pointerdown', {...pointer, target: hit});
svg.dispatch('pointermove', {...pointer, clientX: 170});
assert.ok(trans(skillLayer)[0] > beforeDrag[0]);
const duringDrag = trans(skillLayer);
assert.ok(flushFrames(12) > 0);
assert.deepEqual(trans(skillLayer), duringDrag);
svg.dispatch('pointercancel', pointer);
assert.ok(flushFrames(12) > 0);
assert.notDeepEqual(trans(skillLayer), duringDrag);
assert.deepEqual([lines[3].attrs.x2, lines[3].attrs.y2], trans(skillLayer));

expand.dispatch('click');
assert.ok(overlay.open);
assert.equal(holder.parentNode, overlay);
const beforeResize = center(box(svg));
svg.width = 1280;
svg.height = 820;
observers.get(svg)();
approx(center(box(svg)), beforeResize);
assert.ok(box(svg)[2] > box(svg)[3]);
const escape = overlay.dispatch('keydown', {key: 'Escape'});
assert.ok(escape.stopped && escape.defaultPrevented && !overlay.open, 'Escape must close only the graph overlay');
assert.equal(holder.parentNode, content);
assert.ok(expand.focused);
assert.equal(frames.size, 0);
disposeLive();
assert.equal(observers.size, 0);

const replayLayout = layoutGraph(graph, runCalls(replay).sequences);
assert.ok(replayLayout.nodes.get('function:dns.probe').extra);
assert.ok(!replayLayout.nodes.has('skill:laptop.route.inspect'));
motion.matches = true;
const disposeReplay = drawGraph(panel, graph, replay);
const replaySvg = tag(holder, 'svg')[0];
assert.equal(frames.size, 0, 'reduced motion must settle before first paint');
settle(graphSimulation(replayLayout), replayLayout, 120);
assert.deepEqual(trans(cls(replaySvg, 'g-node').find(layer => layer.attrs['aria-label'] === 'dns.probe')),
  coords(replayLayout.nodes.get('function:dns.probe')));
assert.equal(cls(replaySvg, 'g-lit').length, 3);
assert.equal(cls(replaySvg, 'g-path').length, 3);
assert.ok(cls(replaySvg, 'g-path').at(-1).classList.contains('g-fail'));
assert.ok(!cls(replaySvg, 'g-extra').some(node => node.classList.contains('g-skill')));
assert.equal(cls(replaySvg, 'g-extra').length, 3);
disposeReplay();

motion.matches = false;
const disposePending = drawGraph(panel, graph, null);
assert.equal(frames.size, 1);
disposePending();
assert.equal(frames.size, 0);
assert.equal(observers.size, 0);

const css = fs.readFileSync(path.join(__dirname, '../web_gateway/static/app.css'), 'utf8');
assert.match(css, /@media\(prefers-reduced-motion:reduce\)\s*{[^@]+\.g-path,\.g-lit\s*{\s*animation:none;\s*opacity:1;/);
console.log(`Skill graph: PASS (${steps} force steps, ${frameCount} frames, ${dragSteps} reheated steps, live/replay highlights and interactions)`);
