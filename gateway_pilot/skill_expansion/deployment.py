"""Pinned, operator-reviewed deployment sources for the Skill launcher."""
from __future__ import annotations

import copy
import functools
import time

from ..core import ROOT
from ..adapters.bindings import BindingSelection, TargetContext, binding_digest, declare_binding, require
from ..adapters.laptop_skills import LaptopSkillBackend
from ..command_catalog.builder import build_registry
from ..command_catalog.loader import load_catalog,read_json,digest
from ..command_catalog.runtime import ReadRuntime
from .catalog import SkillCatalog,Skill
from .profiles import load_bundle,validate_profile
from .replay_backend import StrictSkillReplayBackend
from .runtime_bridge import RuntimeSkillBridge


def deployment(mode: str):
    if mode == 'replay_sim':
        from .replay_sim import approved_profile

        approvals = read_json(ROOT / 'config/skill_launcher/approvals.json')
        require(approvals['format'] == 'gateway-lm.skill-launcher-approval/v1', 'skill_approval_format')
        require(mode in approvals, 'skill_deployment_not_approved')
        return approved_profile(approvals[mode])
    return _legacy_deployment(mode)


@functools.lru_cache(maxsize=3)
def _legacy_deployment(mode: str):
    folders = {'live': 'laptop_v1', 'replay': 'wifi_replay_v1', 'replay_client': 'client_replay_v1'}
    require(mode in folders, 'skill_mode')
    folder = folders[mode]
    config=ROOT/'config/skill_launcher'
    approvals=read_json(config/'approvals.json')
    require(approvals['format']=='gateway-lm.skill-launcher-approval/v1','skill_approval_format')
    require(mode in approvals, 'skill_deployment_not_approved')
    approved=approvals[mode]
    catalog=load_catalog(ROOT/'examples/skill_deployments'/folder)
    policy=read_json(config/(mode+'.policy.json'))
    selection=read_json(config/(mode+'.selection.json'))
    actions_doc=read_json(config/(mode+'.actions.json'))
    require(actions_doc['format']=='gateway-lm.skill-actions/v1' and actions_doc['mode']==mode
            and digest(actions_doc)==approved['actions_digest'],'skill_actions_pin')
    artifact=build_registry(catalog,selection,policy,ROOT/'runs/skill-launcher'/(mode+'.registry.json'))
    require(artifact['content_digest']==approved['registry_digest'],'skill_deployment_pin')
    skills={s['skill_id']:s for s in artifact['skills']}
    ports={p['port_id']:p for p in artifact['ports']}
    actions={}
    fields={'skill_id','runtime_skill_id','version','name','domain','kind','scope','required_ports','optional_ports','limitations'}
    for action in actions_doc['actions']:
        require(type(action) is dict and set(action)==fields and action['kind'] in {'design','laptop'},'skill_action_fields')
        sid=action['skill_id'];rid=action['runtime_skill_id']
        require(sid not in actions and rid in skills and action['version']==skills[rid]['version']
                and action['required_ports']==skills[rid]['completion_ports'],'skill_action_contract')
        require(not set(action['required_ports']) & set(action['optional_ports']),'skill_port_roles')
        for pid,version in {**action['required_ports'],**action['optional_ports']}.items():
            require(pid in ports and ports[pid]['version']==version and ports[pid]['scope']==action['scope'],'skill_port_scope')
        actions[sid]=copy.deepcopy(action)
    if mode=='replay':
        profile=read_json(ROOT/'config/skill_profiles/wifi_gateway_replay_v1.json')
        validate_profile(profile,load_bundle())
        require(digest(profile)==approved['cat01_profile_digest'],'skill_cat01_drift')
    return artifact,policy,approved,actions


deployment.cache_clear = _legacy_deployment.cache_clear


def composition(mode: str, *, backend=None, clock=time.monotonic, scenario='normal'):
    if mode == 'replay_sim':
        from .replay_sim import ReplaySession

        require(type(scenario) is str, 'skill_sim_scenario')
        require(backend is None, 'skill_sim_backend_is_fixed')
        profile = deployment(mode)
        return {'session': ReplaySession(profile, scenario, clock), 'actions': profile.actions}
    artifact,policy,approved,actions=deployment(mode)
    if mode=='live':
        backend=LaptopSkillBackend() if backend is None else backend
        require(getattr(backend,'revision',None)==approved['backend_revision'] and getattr(backend,'source',None)==approved['source'],'skill_provider_pin')
        context=TargetContext('client',backend.client_id,backend.environment_id)
        context_valid=lambda: backend.environment_id==context.environment_id
    else:
        if mode == 'replay_client':
            from .client_replay import normal_fixtures
            fixture = normal_fixtures()
            require(digest(fixture) == approved.get('fixtures_digest'), 'skill_fixture_pin')
        else:
            fixture=read_json(ROOT/'data/skill_expansion_v1/replay_fixtures_v2.json',max_bytes=1048576)
        values={f['function_id']:fixture[f['function_id']] for f in artifact['functions']}
        backend=StrictSkillReplayBackend(artifact['functions'],artifact['ports'],values) if backend is None else backend
        require(getattr(backend,'revision',None)==approved['backend_revision'] and getattr(backend,'source',None)==approved['source'],'skill_provider_pin')
        environment=digest({'registry':artifact['content_digest'],'fixtures':backend._fixture})
        if mode == 'replay_client':
            require(digest(backend._fixture) == approved['fixtures_digest'], 'skill_fixture_pin')
            context=TargetContext('client','synthetic-test-target',environment)
        else:
            context=TargetContext('gateway','synthetic-skill-gateway',environment)
        context_valid=lambda: digest({'registry':artifact['content_digest'],'fixtures':backend._fixture})==environment
    require(backend.revision==approved['backend_revision'] and backend.source==approved['source'],'skill_provider_pin')
    rows=[declare_binding(artifact,f['function_id'],'launcher.'+f['function_id'],approved['backend_id'],backend,context)
          for f in artifact['functions']]
    # Only this reviewed local composition root creates context-bound READ bindings.
    # No request supplies a backend, target, permissions, schema or approval value.
    selection=BindingSelection(artifact,policy,rows,approved_digests=frozenset(binding_digest(b) for b in rows),
                               backends={approved['backend_id']:backend},context=context)
    runtime=ReadRuntime(artifact,policy,approved_digest=approved['registry_digest'],selection=selection,context=context,
                        permissions=frozenset({'network.read'}),
                        policy_context_id=digest({'principal':'localhost-skill-operator','mode':mode,'revision':1}),clock=clock)
    # Live always requires reviewed diagnostics. Replay chat is enabled only
    # after an operator pins replay.diagnostics.json in approvals.json.
    if mode == 'live' or 'diagnostics_digest' in approved:
        from ..graph_v3.claims import ClaimBook
        diagnostics = read_json(ROOT/'config/skill_launcher'/(mode+'.diagnostics.json'))
        require(diagnostics.get('format') == 'gateway-lm.laptop-diagnostics/v1'
                and digest(diagnostics) == approved['diagnostics_digest'], 'skill_diagnostics_pin')
        require(set(diagnostics['skill_workflows']) == set(actions)
                and all(set(ids) <= set(diagnostics['workflows']) for ids in diagnostics['skill_workflows'].values()),
                'skill_diagnostic_membership')
        require(all(set(v['ports']) <= set(runtime.registry.ports) and v['phrases']
                    for v in diagnostics['question_intents'].values()), 'skill_question_intents')
        runtime.registry.nonlocal_scope_phrases = diagnostics['nonlocal_scope_phrases']
        runtime.registry.question_intents = diagnostics['question_intents']
        runtime.registry.required_skill_phrases = diagnostics['required_skill_phrases']
        runtime.registry.skill_workflows = diagnostics['skill_workflows']
        runtime.registry.workflows = diagnostics['workflows']
        runtime.registry.claim_book = ClaimBook(diagnostics['claims'], runtime.registry.ports,
                                                diagnostics['workflows'])
    design=SkillCatalog.load()
    native=[Skill(id=a['skill_id'],name_vi=a['name'],domain=a['domain'],domain_name='Local laptop actions',priority='P0',
                  catalog_status='PROPOSED',kind='Local READ',scope='client',planned_backend='Local Linux',
                  notes='Separate laptop action, not a fulfilled router Skill.',source=None,runtime_status='NOT_BOUND')
            for a in actions.values() if a['kind']=='laptop']
    bridge=RuntimeSkillBridge(runtime,SkillCatalog([*design.skills.values(),*native],design.relations))
    session=runtime.open_session(max_calls=24,ttl_s=300,max_plans=64,context_valid=context_valid,
                                 max_repairs=2 if mode=="live" else 0,method="gos" if mode=="live" else "ordered")
    return {'runtime':runtime,'session':session,'bridge':bridge,'actions':actions,'context_valid':context_valid,'backend':backend}
