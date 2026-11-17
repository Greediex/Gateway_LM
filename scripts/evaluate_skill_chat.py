"""Frozen semantic benchmark for SkillChat; synthetic providers by default.

Run: python3 -m scripts.evaluate_skill_chat --split dev --model scripted
Real local inference (still synthetic telemetry): --model ollama --limit 2
No labels or case metadata are passed to choose_skills. Scripted results measure
integration contracts, not language-model quality. Test output is aggregate only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
import unicodedata
from typing import Callable

from gateway_pilot.adapters.laptop_skills import LaptopSkillBackend
from gateway_pilot.adapters.read_backends import observations
from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher, SkillSessionError
from gateway_pilot.command_catalog.loader import digest
from gateway_pilot.graph_v3.ollama_goal_model import OllamaGoalModel
from gateway_pilot.skill_expansion.deployment import composition

DATA = Path(__file__).resolve().parents[1] / 'benchmarks' / 'skill_chat_v1'
MANIFEST_SHA256 = '7f6bfa9b3b65737ba20d1cb0bf7f96ef6c582255358107f3abf393101e7c9072'


def load_cases(split: str, *, folder: Path = DATA) -> tuple[dict, list[dict]]:
    """Validate immutable manifest, hashes and disjoint group assignments."""
    if split not in {'dev', 'test'}:
        raise ValueError('invalid_benchmark_split')
    raw = (folder / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError('benchmark_manifest_hash_mismatch')
    manifest = json.loads(raw)
    splits = {}
    for name, meta in manifest['files'].items():
        raw = (folder / meta['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta['sha256']:
            raise ValueError('benchmark_split_hash_mismatch')
        rows = [json.loads(line) for line in raw.splitlines()]
        if len(rows) != meta['cases'] or sum(len(r['turns']) for r in rows) != meta['turns']:
            raise ValueError('benchmark_count_mismatch')
        splits[name] = rows
    for field in ('id', 'scenario_group', 'paraphrase_group'):
        if {r[field] for r in splits['dev']} & {r[field] for r in splits['test']}:
            raise ValueError('benchmark_group_overlap')
    return manifest, splits[split]


class SyntheticLaptopBackend(LaptopSkillBackend):
    """Pinned laptop contract, deterministic observations, zero OS commands."""
    def __init__(self, options: dict | None = None):
        self.options = options or {}
        self.client_id, self.interface = 'local-laptop', 'wifi0'
        self._tools = {'ping': 'synthetic', 'resolvectl': 'synthetic'}
        self.calls = 0

    @property
    def environment_id(self):
        return digest({'synthetic_skill_chat_v1': True, 'interface': self.interface})

    def _command(self, *args, **kwargs):
        raise AssertionError('benchmark_must_not_execute_os_commands')

    def wifi(self):
        return dict(interface=self.interface, radio_enabled=True, associated=True,
                    ssid='Synthetic AP', bssid='02:00:00:00:00:01', signal_pct=70,
                    channel=36, frequency_mhz=5180, ap_rate_mbps=1201)

    def route(self):
        return dict(has_route=True, interface=self.interface, source_ipv4='192.0.2.10',
                    gateway='192.0.2.1', resolver_fingerprint='synthetic-resolver')

    def _ipv4(self):
        return dict(configured=True, address='192.0.2.10')

    def sample(self, function, arguments, context):
        self.calls += 1
        fid = function['function_id']
        if self.options.get('error_function') == fid:
            raise TimeoutError('synthetic_tool_timeout')
        if fid.endswith('_probe'):
            value = dict(destination='192.0.2.1' if fid.endswith('gateway_probe') else '1.1.1.1',
                         interface=self.interface, sent=4, received=4, loss_pct=0, latency_ms=2)
            return observations(function, {fid: value}, self.source, context)
        if fid == 'laptop.dns':
            return observations(function, {fid: dict(query='example.com', resolved=True,
                                                    interface=self.interface)}, self.source, context)
        return super().sample(function, arguments, context)


def _normalize(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower().replace('đ', 'd'))
                   if unicodedata.category(c) != 'Mn')


class ScriptedModel:
    """Simple request-only lexical double; deliberately not an intent oracle."""
    local_only = True
    model = 'scripted-lexical-double-v1'

    def choose_skills(self, request, catalog, context):
        text = _normalize(request)
        desired = []
        if 'dns' in text:
            desired.append(('laptop.dns.inspect', 'laptop.dns'))
        if 'wi-fi' in text or 'wifi' in text:
            desired.append(('laptop.wifi.inspect', 'laptop.wifi'))
        if 'ipv4' in text and any(s in text for s in ('address', 'dia chi', 'ipv4 laptop')):
            desired.append(('laptop.ipv4.inspect', 'client.ipv4'))
        if 'gateway' in text and ('icmp' in text or 'kiem tra gateway' in text):
            desired.append(('laptop.gateway.inspect', 'laptop.gateway_probe'))
        elif 'route' in text or 'tuyen' in text or 'gateway' in text:
            desired.append(('laptop.route.inspect', 'laptop.route'))
        unavailable = [sid for sid, words in [('B04', ('snr', 'rssi')), ('B07', ('roaming',))]
                       if any(w in text for w in words)]
        available = {row[0] for row in catalog if row[2] in {'READY', 'DEGRADED'}}
        facts = {f['id'] for f in context['findings']}
        pending = [sid for sid, port in desired if port not in facts and sid in available
                   and sid not in context['attempted']]
        selected = [port for _, port in desired if port in facts]
        return {'decision': 'measure' if pending else 'answer' if selected else 'clarify',
                'skill_ids': pending[:3], 'finding_ids': [] if pending else selected[:4],
                'unavailable_ids': unavailable}


def _counts(actual: set, expected: set) -> dict:
    return {'tp': len(actual & expected), 'fp': len(actual - expected), 'fn': len(expected - actual)}


def _selection(rows: list[dict], key: str) -> dict:
    counts = {k: sum(r[key][k] for r in rows) for k in ('tp', 'fp', 'fn')}
    return {**counts, 'precision': counts['tp'] / (counts['tp'] + counts['fp'])
            if counts['tp'] + counts['fp'] else None,
            'recall': counts['tp'] / (counts['tp'] + counts['fn'])
            if counts['tp'] + counts['fn'] else None}


def _percentile(values: list[float], percentile: float) -> float | None:
    return sorted(values)[max(0, math.ceil(percentile * len(values)) - 1)] if values else None


def score_response(response: dict, expected: dict, elapsed_ms: float) -> dict:
    """Score public output against semantic labels; model never sees expected."""
    skills = {r['skill_id'] for r in response.get('skill_runs', [])}
    functions = {r['function_id'] for r in response.get('timeline', [])}
    selected_ids = set(response.get('evidence_ids', []))
    ports = {row['port'] for row in response.get('evidence', []) if row['id'] in selected_ids}
    required = set(expected['answer_ports'])
    unavailable = set(response.get('unavailable_skills', []))
    coverage = len(required & ports) + len(set(expected['unavailable']) & unavailable)
    obligations = len(required) + len(expected['unavailable'])
    abstained = response.get('case_status') != 'MEASURED'
    claims = [claim for a in response.get('rca_assessments', []) for claim in a.get('claim_results', [])]
    # True claims need current selected-or-unselected verified facts; observation
    # predicates are permitted, but a top-level causal diagnosis is not justified.
    current_ids = {r['id'] for r in response.get('evidence', [])}
    true_claims = [c for c in claims if c.get('truth') == 'TRUE']
    invalid_true_claims = sum(not c.get('evidence_ids') or not set(c['evidence_ids']) <= current_ids
                              for c in true_claims)
    proof_valid = not invalid_true_claims
    calls = response.get('calls', 0)
    runtime_ok = response.get('case_status') != 'ERROR'
    rejections = response.get('proposal_rejections',
                              int(response.get('stop_reason') == 'invalid_model_proposal'))
    runtime_coverage = response.get('coverage', {})
    return {'skill_selection': _counts(skills, set(expected['skills'])),
            'function_selection': _counts(functions, set(expected['functions'])),
            'covered': coverage, 'obligations': obligations,
            'rca_true_claims': len(true_claims), 'rca_invalid_true_claims': invalid_true_claims,
            'answer_complete': runtime_ok and coverage == obligations,
            'request_success': runtime_ok,
            'abstention_correct': runtime_ok and abstained == expected['abstain'],
            'root_cause_abstention_correct': runtime_ok and response.get('diagnosis') is None,
            'rca_proof_valid': runtime_ok and proof_valid,
            'invalid_proposals': rejections,
            'proposals': response.get('model_calls', len(response.get('advice', []))),
            'proposal_rejections': rejections,
            'advice_count': len(response.get('advice', [])),
            'advice_accepted': sum(a.get('accepted') is True for a in response.get('advice', [])),
            'coverage_feedback_rejections': sum(a.get('accepted') is False and a.get('reason') == 'incomplete_coverage'
                                                for a in response.get('advice', [])),
            'reported_goals': len(runtime_coverage.get('requested_ports', [])),
            'reported_satisfied_goals': len(runtime_coverage.get('satisfied_ports', [])),
            'reported_coverage_complete': runtime_coverage.get('complete', False),
            'calls': calls, 'calls_in_bounds': expected['call_bounds'][0] <= calls <= expected['call_bounds'][1],
            'runner_repairs': response.get('repairs', 0),
            'ttl_recovery_attempts': response.get('recovery_attempts', 0),
            'ttl_recovery_runs': len(response.get('recovery_runs', [])),
            'stage_timings_ms': response.get('timings_ms', {}), 'latency_ms': elapsed_ms,
            'stop_reason': response.get('stop_reason'), 'case_status': response.get('case_status')}


def evaluate(split: str = 'dev', *, model: str = 'scripted', limit: int | None = None,
             model_name: str = 'qwen3:1.7b', model_factory: Callable | None = None) -> dict:
    """Reusable API. Telemetry always synthetic; model_factory is a test seam.

    Real Ollama is opt-in. limit counts scenarios (including their followup turns).
    Heldout returns aggregates only, deliberately excluding per-case failures.
    """
    manifest, cases = load_cases(split)
    if model not in {'scripted', 'ollama'} or (limit is not None and (type(limit) is not int or limit < 1)):
        raise ValueError('invalid_evaluation_options')
    if model_factory is not None and model != 'scripted':
        raise ValueError('model_factory_only_for_double_mode')
    rows = []
    for case in cases[:limit]:
        now = [100.0]
        clock_start = time.monotonic()
        clock = lambda: now[0] + time.monotonic() - clock_start
        entries = []
        def factory(mode):
            entry = composition(mode, backend=SyntheticLaptopBackend(case['provider']), clock=clock)
            entries.append(entry)
            return entry
        launcher = SkillLauncher(factory=factory, clock=clock)
        model_instance = None
        def get_model():
            nonlocal model_instance
            if model_instance is None:
                model_instance = (model_factory() if model_factory else ScriptedModel() if model == 'scripted'
                                  else OllamaGoalModel(model_name, timeout=60))
            return model_instance
        chat = SkillChat(launcher, model_factory=get_model)
        session_id = None
        previous_repairs = 0
        for index, turn in enumerate(case['turns']):
            if index == len(case['turns']) - 1 and index:
                now[0] += case['advance_before_final_turn_s']
            runner = entries[-1]['session'].runner if entries else None
            calls_before = runner.calls if runner else 0
            plans_before = len(runner.plans) if runner else 0
            started = time.perf_counter()
            try:
                response = chat.chat(turn['request'], session_id=session_id)
            except Exception as exc:
                # Count runtime failures as failures; never drop a test window.
                runner = entries[-1]['session'].runner if entries else None
                response = {'case_status': 'ERROR', 'stop_reason': type(exc).__name__,
                            'calls': runner.calls - calls_before if runner else 0,
                            'repairs': runner.repairs if runner else 0,
                            'timeline': [{'function_id': node.function_id}
                                         for plan in runner.plans[plans_before:] for node in plan.nodes.values()]
                                         if runner else []}
            elapsed = (time.perf_counter() - started) * 1000
            session_id = response.get('session_id', session_id)
            row = score_response(response, turn['expected'], elapsed)
            row['runner_repairs'] = max(0, row['runner_repairs'] - previous_repairs)
            previous_repairs += row['runner_repairs']
            row.update(case_id=case['id'], turn=index, category=case['category'])
            rows.append(row)
        if session_id:
            try:
                launcher.close(session_id)
            except SkillSessionError:
                pass  # Expired sessions have already been revoked by the launcher.
    n = len(rows)
    obligations = sum(r['obligations'] for r in rows)
    def rate(key):
        return sum(bool(r[key]) for r in rows) / n if n else None
    try:
        revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=DATA.parents[1],
                                  capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = 'unknown'
    stages = sorted({key for row in rows for key in row['stage_timings_ms']})
    stage_timings = {}
    for key in stages:
        values = [row['stage_timings_ms'][key] for row in rows if key in row['stage_timings_ms']]
        stage_timings[key] = {'observed_turns': len(values), 'sum': sum(values),
                              'p50': _percentile(values, .5), 'p95': _percentile(values, .95)}
    ttl_recoveries = sum(r['ttl_recovery_attempts'] for r in rows)
    runner_repairs = sum(r['runner_repairs'] for r in rows)
    result = {'benchmark': manifest['version'], 'manifest_sha256': MANIFEST_SHA256,
              'split_sha256': manifest['files'][split]['sha256'], 'split': split,
              'runtime_commit': revision,
              'runtime_skill_chat_sha256': hashlib.sha256((DATA.parents[1] / 'gateway_pilot/application/skill_chat.py').read_bytes()).hexdigest(),
              'model_mode': 'test_double' if model == 'scripted' else 'real_local_ollama',
              'model': getattr(model_instance, 'model', model_name) if cases else model_name,
              'provider_mode': 'synthetic_replay', 'runtime_profile': 'live_laptop_contracts',
              'os_measurement': False, 'router_measurement': False,
              'label_provenance': manifest['label_provenance'], 'cases': min(limit or len(cases), len(cases)),
              'turns': n, 'request_success_rate': rate('request_success'),
              'reported_runtime_goals': sum(r['reported_goals'] for r in rows),
              'reported_runtime_satisfied_goals': sum(r['reported_satisfied_goals'] for r in rows),
              'reported_runtime_complete_rate': rate('reported_coverage_complete'),
              'skill_selection': _selection(rows, 'skill_selection'),
              'function_selection': _selection(rows, 'function_selection'),
              'semantic_answer_obligations': obligations,
              'semantic_answer_covered': sum(r['covered'] for r in rows),
              'answer_coverage': sum(r['covered'] for r in rows) / obligations if obligations else None,
              'answer_complete_rate': rate('answer_complete'), 'abstention_accuracy': rate('abstention_correct'),
              'root_cause_abstention_accuracy': rate('root_cause_abstention_correct'),
              'rca_proof_valid_rate': rate('rca_proof_valid'),
              'rca_true_claims': sum(r['rca_true_claims'] for r in rows),
              'rca_invalid_true_claims': sum(r['rca_invalid_true_claims'] for r in rows),
              'rca_turns_with_true_claims': sum(bool(r['rca_true_claims']) for r in rows),
              'invalid_proposals': sum(r['invalid_proposals'] for r in rows),
              'proposals': sum(r['proposals'] for r in rows),
              'proposal_rejections': sum(r['proposal_rejections'] for r in rows),
              'advice_count': sum(r['advice_count'] for r in rows),
              'advice_accepted': sum(r['advice_accepted'] for r in rows),
              'coverage_feedback_rejections': sum(r['coverage_feedback_rejections'] for r in rows),
              'tool_calls': sum(r['calls'] for r in rows), 'call_bounds_pass_rate': rate('calls_in_bounds'),
              'ttl_recovery_attempts': ttl_recoveries, 'runner_repairs': runner_repairs,
              'ttl_recovery_runs': sum(r['ttl_recovery_runs'] for r in rows),
              'total_recovery_attempts': ttl_recoveries + runner_repairs,
              'stage_timings_ms': stage_timings,
              'latency_ms': {'p50': _percentile([r['latency_ms'] for r in rows], .5),
                             'p95': _percentile([r['latency_ms'] for r in rows], .95)},
              'runtime_errors': sum(r['case_status'] == 'ERROR' for r in rows),
              'limits': ['Generated semantic fixture, no external human validation.',
                         'Scripted selection is integration evidence only.',
                         'Selection metrics score executed skill_runs and attempted timeline function IDs.',
                         'Real inference time counts against TTL; stale scenarios also advance the clock 31 seconds.',
                         'Coverage checks selected verified ports, not prose semantics.',
                         'Synthetic latency is not live-device latency.',
                         'TTL recovery attempts and runner repairs are separate; their sum is not verified incident recovery.',
                         'Reported runtime goals are telemetry, separate from frozen semantic answer obligations.',
                         'Stage timings use runtime instrumentation; execution includes Core/Verifier costs.',
                         'Frozen exact call bounds may overestimate retries; failures are retained, never relabeled.']}
    if split == 'dev':
        result['details'] = rows
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['dev', 'test'], default='dev')
    parser.add_argument('--model', choices=['scripted', 'ollama'], default='scripted')
    parser.add_argument('--model-name', default='qwen3:1.7b')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = evaluate(args.split, model=args.model, model_name=args.model_name, limit=args.limit)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end='')


if __name__ == '__main__':
    main()
