"""Descriptive SkillChat development profiler. Never contacts router hardware.

Run with Python from the repository root. Provider is always frozen synthetic;
--model qwen measures real local Ollama inference, --model fake uses a double.
Cold = fresh launcher/session and (Qwen only) explicitly unloaded Ollama model;
warm = same launcher/session follow-up, retaining only legitimately fresh facts.
Stage spans are inclusive and overlap (RCA includes capability refresh).
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gateway_pilot.adapters.laptop_skills import LaptopSkillBackend
from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.command_catalog.loader import digest
from gateway_pilot.command_catalog.runtime import ReadRuntime
from gateway_pilot.graph_v3 import ollama_goal_model
from gateway_pilot.graph_v3.rca_agent import RCAAgent
from gateway_pilot.graph_v3.verification import EvidenceVerifier
from gateway_pilot.skill_expansion.deployment import composition
from gateway_pilot.skill_expansion.retrieval import SkillRetriever

CASES = (
    ('gateway', 'Gateway của laptop là gì?', ['laptop.route.inspect'], ['laptop.route']),
    ('dns', 'Kiểm tra DNS trên laptop', ['laptop.dns.inspect'], ['laptop.dns']),
    ('wifi_gateway', 'Wi-Fi và gateway laptop thế nào?', ['laptop.wifi.inspect', 'laptop.route.inspect'], ['laptop.wifi', 'laptop.route']),
    ('internet', 'Kiểm tra kết nối Internet laptop', ['laptop.network.inspect'], ['laptop.route', 'laptop.internet_probe', 'laptop.dns']),
)
ALLOWED_FINDINGS = {
    'gateway': {'laptop.route', 'laptop.gateway_probe'},
    'dns': {'laptop.dns'},
    'wifi_gateway': {'laptop.wifi', 'laptop.route', 'laptop.gateway_probe'},
    'internet': {'laptop.route', 'laptop.gateway_probe', 'laptop.internet_probe', 'laptop.dns', 'laptop.wifi', 'client.ipv4'},
}
for _allowed in ALLOWED_FINDINGS.values():
    _allowed.add('client.identity')  # Contextual identification of this same laptop is permitted.
FIXTURE = {'associated': True, 'signal_pct': 70, 'gateway': '192.0.2.1', 'source_ipv4': '192.0.2.10', 'dns': True, 'loss_pct': 0, 'latency_ms': 2}


class FrozenBackend(LaptopSkillBackend):
    """Pinned synthetic provider; no subprocess, sockets, OS telemetry, or router I/O."""
    def __init__(self):
        self.client_id, self.interface = 'local-laptop', 'wifi0'
        self._tools = {'ping': 'synthetic', 'resolvectl': 'synthetic'}
    @property
    def environment_id(self):
        return digest(FIXTURE)
    def wifi(self):
        return dict(interface=self.interface, radio_enabled=True, associated=True,
                    ssid='Synthetic profiling AP', bssid='02:00:00:00:00:01', signal_pct=70,
                    channel=36, frequency_mhz=5180, ap_rate_mbps=1201)
    def route(self):
        return dict(has_route=True, interface=self.interface, source_ipv4='192.0.2.10',
                    gateway='192.0.2.1', resolver_fingerprint=digest({'synthetic': 'dns'}))
    def _ipv4(self):
        return dict(configured=True, address='192.0.2.10')
    def _command(self, tool, *args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=(
            '4 packets transmitted, 4 received, 0% packet loss\nrtt min/avg/max/mdev = 1/2/3/1 ms\n'
            if tool == 'ping' else 'example.com: 192.0.2.80\n'))


class FakeModel:
    local_only = True
    model = 'deterministic-profile-double'
    def __init__(self, skills, ports): self.skills, self.ports = skills, ports
    def choose_skills(self, request, catalog, context):
        present = {r['id'] for r in context['findings']}
        complete = set(self.ports) <= present
        return dict(decision='answer' if complete else 'measure',
                    skill_ids=[] if complete else self.skills,
                    finding_ids=self.ports if complete else [], unavailable_ids=[])


def process_stats(pid: int) -> tuple[float, int]:
    try:
        values = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return ((int(values[11]) + int(values[12])) / os.sysconf('SC_CLK_TCK'),
                int(values[21]) * os.sysconf('SC_PAGE_SIZE'))
    except (OSError, ValueError, IndexError): return (0.0, 0)


_OLLAMA_SERVICES = None


def ollama_pids() -> list[int]:
    # Discover the service once, then traverse its tiny process tree. Repeated
    # full /proc scans materially contaminate the Python CPU measurement.
    global _OLLAMA_SERVICES
    if _OLLAMA_SERVICES is None:
        _OLLAMA_SERVICES = []
        for path in Path('/proc').iterdir():
            if path.name.isdigit():
                try:
                    if (path / 'comm').read_text().strip() == 'ollama':
                        _OLLAMA_SERVICES.append(int(path.name))
                except OSError: pass
    result, pending = [], list(_OLLAMA_SERVICES)
    while pending:
        pid = pending.pop()
        if pid in result: continue
        result.append(pid)
        try:
            for child_file in Path(f'/proc/{pid}/task').glob('*/children'):
                pending.extend(int(p) for p in child_file.read_text().split())
        except OSError: pass
    return result


class Resources:
    def __enter__(self):
        self.before = {p: process_stats(p)[0] for p in [os.getpid(), *ollama_pids()]}
        self.peak = {'python': 0, 'ollama': 0}; self.done = threading.Event()
        def sample():
            while not self.done.is_set():
                self.peak['python'] = max(self.peak['python'], process_stats(os.getpid())[1])
                self.peak['ollama'] = max(self.peak['ollama'], sum(process_stats(p)[1] for p in ollama_pids()))
                self.done.wait(.25)
        self.thread = threading.Thread(target=sample, daemon=True); self.thread.start()
        return self
    def __exit__(self, *exc):
        self.done.set(); self.thread.join()
        self.cpu = {label: sum(max(0, process_stats(p)[0] - self.before.get(p, 0)) for p in pids)
                    for label, pids in [('python', [os.getpid()]), ('ollama', ollama_pids())]}


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values); position = (len(ordered)-1)*q
    lo = math.floor(position); hi = math.ceil(position)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(position-lo)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=('fake', 'qwen'), default='fake')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--label', default='unlabeled')
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20: parser.error('repeats must be 1..20')
    active = None
    def span(stage, original):
        @wraps(original)
        def wrapped(*a, **kw):
            start = time.perf_counter()
            try:
                result = original(*a, **kw)
                if stage == 'ollama_http' and active is not None and isinstance(result, dict):
                    active['ollama'].append({k: result[k] for k in ('total_duration', 'load_duration', 'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration') if k in result})
                return result
            finally:
                if active is not None:
                    active['stages'][stage].append((time.perf_counter()-start)*1000)
        return wrapped
    rows = []
    with ExitStack() as stack:
        for cls, method, label in [(SkillLauncher, 'catalog', 'catalog'), (ReadRuntime, 'probe', 'probe'),
                (ReadRuntime, 'call', 'function'), (EvidenceVerifier, 'verify', 'verifier'),
                (RCAAgent, 'assess_session', 'rca'), (ollama_goal_model.OllamaGoalModel, 'choose_skills', 'inference'),
                (FakeModel, 'choose_skills', 'inference'), (SkillRetriever, 'search', 'catalog_retrieval')]:
            stack.enter_context(patch.object(cls, method, span(label, getattr(cls, method))))
        stack.enter_context(patch.object(ollama_goal_model, 'http_json', span('ollama_http', ollama_goal_model.http_json)))
        for repeat in range(args.repeats):
            for case_id, request, skills, ports in CASES:
                if args.model == 'qwen':
                    payload = json.dumps({'model': 'qwen3:1.7b', 'keep_alive': 0}).encode()
                    with urlopen(Request('http://127.0.0.1:11434/api/generate', payload, {'Content-Type': 'application/json'}), timeout=60) as reply: reply.read()
                launcher = SkillLauncher(factory=lambda mode: composition(mode, backend=FrozenBackend()))
                model_factory = (lambda: ollama_goal_model.OllamaGoalModel('qwen3:1.7b', timeout=60)) if args.model == 'qwen' else (lambda: FakeModel(skills, ports))
                chat = SkillChat(launcher, model_factory=model_factory)
                sid = None
                for temperature in ('cold', 'warm'):
                    active = {'stages': defaultdict(list), 'ollama': []}
                    start = time.perf_counter()
                    with Resources() as resources:
                        result = chat.chat(request, session_id=sid)
                    wall = (time.perf_counter()-start)*1000
                    sid = result['session_id']
                    row = dict(repeat=repeat, case=case_id, temperature=temperature,
                        wall_ms=wall, stage_ms={k: sum(v) for k, v in active['stages'].items()},
                        stage_calls={k:len(v) for k,v in active['stages'].items()}, ollama=active['ollama'],
                        tool_calls=result['calls'], status=result['case_status'], stop_reason=result['stop_reason'],
                        llm_advisor_used=result['llm_advisor_used'], llm_advisor_ready=result['llm_advisor_ready'],
                        accepted_model_proposals=sum(a.get('accepted') is True for a in result['advice']),
                        advice_entries=len(result['advice']), runtime_timings_ms=result.get('timings_ms', {}),
                        runtime_model_calls=result.get('model_calls'), coverage=result.get('coverage'),
                        quality_valid=(result['case_status']=='MEASURED' and set(ports) <= {p for p,f in result['snapshot']['facts'].items() if f['evidence_id'] in result['evidence_ids']}
                            and {p for p,f in result['snapshot']['facts'].items() if f['evidence_id'] in result['evidence_ids']} <= ALLOWED_FINDINGS[case_id]),
                        skills=[s['skill_id'] for s in result['skill_runs']], finding_ports=[p for p,f in result['snapshot']['facts'].items() if f['evidence_id'] in result['evidence_ids']],
                        cpu_s=resources.cpu, peak_rss_bytes=resources.peak, loadavg=os.getloadavg())
                    rows.append(row); active = None
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    with args.output.with_suffix('.jsonl').open('a') as stream:
                        stream.write(json.dumps(row, ensure_ascii=False)+'\n')
                    print(json.dumps({k:row[k] for k in ('repeat','case','temperature','wall_ms','tool_calls','status','stop_reason')}), flush=True)
                launcher.close(sid)
                if launcher._sessions: raise RuntimeError('session_not_released')
    aggregates = []
    for case_id, *_ in CASES:
        for temp in ('cold', 'warm'):
            subset = [r for r in rows if r['case']==case_id and r['temperature']==temp]
            stages = set().union(*(r['stage_ms'] for r in subset))
            aggregates.append(dict(case=case_id, temperature=temp, n=len(subset),
                wall_ms={name:percentile([r['wall_ms'] for r in subset],q) for name,q in [('p50',.5),('p95',.95)]},
                stage_ms={s:{name:percentile([r['stage_ms'].get(s,0) for r in subset],q) for name,q in [('p50',.5),('p95',.95)]} for s in sorted(stages)},
                tool_calls=[r['tool_calls'] for r in subset],
                cpu_s={process:{name:percentile([r['cpu_s'][process] for r in subset],q) for name,q in [('p50',.5),('p95',.95)]} for process in ('python','ollama')},
                peak_rss_bytes={process:{name:percentile([r['peak_rss_bytes'][process] for r in subset],q) for name,q in [('p50',.5),('p95',.95)]} for process in ('python','ollama')},
                quality_valid_count=sum(r['quality_valid'] for r in subset), quality_valid_ratio=sum(r['quality_valid'] for r in subset)/len(subset)))
    try: revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError: revision=args.label
    report=dict(schema='skill-chat-dev-profile-v1',label=args.label,revision=revision,
        model='qwen3:1.7b' if args.model=='qwen' else 'deterministic-double',provider='frozen-synthetic-linux; not real laptop network/router telemetry',
        fixture=FIXTURE,cases=CASES,allowed_findings={key:sorted(value) for key,value in ALLOWED_FINDINGS.items()},fixture_sha256=hashlib.sha256(json.dumps([CASES,FIXTURE],sort_keys=True).encode()).hexdigest(),
        definitions={'cold':'new launcher/session; Qwen unloaded before case', 'warm':'same session repeated request; fact reuse still obeys TTL',
                     'stages':'inclusive wall spans; do not sum overlapping RCA/probe spans',
                     'resources':'sampled process RSS, Linux /proc CPU deltas; Ollama service + runner; shared-process and 250ms sampling limits',
                     'quality_valid':'MEASURED plus frozen expected finding ports included and no unrelated finding ports; strict port coverage, not an independent semantic-quality benchmark',
                     'p95':'linear interpolation of n=3 descriptive repeats, not a statistically strong tail estimate'},
        source_sha256={relative:hashlib.sha256((Path(__file__).resolve().parents[1]/relative).read_bytes()).hexdigest() for relative in (
            'gateway_pilot/application/skill_chat.py','gateway_pilot/application/skill_launcher.py',
            'gateway_pilot/graph_v3/ollama_goal_model.py','gateway_pilot/command_catalog/runtime.py',
            'gateway_pilot/graph_v3/runner.py','gateway_pilot/graph_v3/verification.py')},
        host={'cpu_count':os.cpu_count(),'loadavg':os.getloadavg()},rows=rows,aggregates=aggregates)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__': main()
