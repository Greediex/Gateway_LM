"""Run one isolated synthetic READ end-to-end through the existing v0.2 Core.

Test-only temporary sandbox. NEVER install the transient IMPLEMENTED catalog,
test binding approval or synthetic evidence into a production registry.
Requires --synthetic-only acknowledgement. Does not modify source checkout.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, tempfile
from pathlib import Path
from typing import Callable

from gateway_pilot.graph_v3.state import CaseState

ROOT=Path(__file__).resolve().parents[1]

def smoke(fid: str, *, values: dict | None = None, omit: bool = False,
          assess: Callable[[CaseState], dict] | None = None):
    """``values`` replaces the default fixture; ``omit`` drops it (missing data)."""
    from gateway_pilot.command_catalog.loader import load_catalog
    from gateway_pilot.command_catalog.validator import validate_catalog
    from gateway_pilot.command_catalog.builder import build_registry
    from gateway_pilot.adapters.bindings import TargetContext, BindingSelection, declare_binding, binding_digest
    from gateway_pilot.command_catalog.runtime import ReadRuntime
    from gateway_pilot.skill_expansion.replay_backend import StrictSkillReplayBackend
    from gateway_pilot.skill_expansion.runtime_bridge import RuntimeSkillBridge
    from gateway_pilot.skill_expansion.catalog import SkillCatalog

    functions=json.loads((ROOT/'data/skill_expansion_v1/function_proposals.json').read_text(encoding='utf-8'))
    fixture=json.loads((ROOT/'data/skill_expansion_v1/replay_fixtures_v2.json').read_text(encoding='utf-8'))
    function=next((f for f in functions if f['function_id']==fid),None)
    if function is None:raise ValueError('unknown/synthetic-only Function ID')
    assert function['risk']=='READ_ONLY' and function['lifecycle']=='PROPOSED'
    original=ROOT/'proposed_catalog_v02'
    port_id=next(iter(function['outputs']))
    sid=function['skill_refs'][0]['skill_id']; slug=sid.split('.')[-1].upper()
    if not sid.startswith('gateway.') or slug.startswith('SK'):
        raise ValueError('synthetic smoke only for proposed skills')
    with tempfile.TemporaryDirectory(prefix='gateway-replay-v2-') as tmp:
        catalog_root=Path(tmp)/'catalog'
        temporary_f=copy.deepcopy(function)
        temporary_f['lifecycle']='IMPLEMENTED'  # only inside disposable synthetic test catalog
        docs=[(catalog_root/'functions'/function['domain']/(fid+'.json'),temporary_f),
              (catalog_root/'ports'/(port_id+'.json'),
               json.loads((original/'ports'/(port_id+'.json')).read_text(encoding='utf-8'))),
              (catalog_root/'skills'/(sid+'.json'),
               json.loads((original/'skills'/(sid+'.json')).read_text(encoding='utf-8')))]
        fixtures = {} if omit else {fid: {port_id: copy.deepcopy(values)} if values is not None else fixture[fid]}
        if function['scope'] == 'client':
            # Client evidence requires a Core-verified identity. Supply a
            # dependency only in this disposable synthetic catalog, never by
            # injecting an unverified initial_evidence record or weakening Core.
            identity_id = 'expansion.synthetic_client_identity'
            identity = copy.deepcopy(temporary_f)
            identity.update(function_id=identity_id, inputs={}, outputs={'client.identity':'1.0.0'},
                            description='Synthetic test identity only, not device discovery.',
                            capability_probe='probe.expansion.synthetic_client_identity')
            temporary_f['inputs']['client.identity'] = '1.0.0'
            docs[2][1]['function_refs'][identity_id] = identity['version']
            docs[2][1]['produces']['client.identity'] = '1.0.0'
            docs += [(catalog_root/'functions'/function['domain']/(identity_id+'.json'), identity),
                     (catalog_root/'ports'/'client.identity.json',
                      dict(schema_version='0.2.0',kind='port',port_id='client.identity',version='1.0.0',
                           scope='client',provenance='synthetic_replay/',untrusted_text=False,
                           schema={'type':'object','properties':{'client_id':{'type':'string','minLength':1,'maxLength':128}},
                                   'required':['client_id'],'additionalProperties':False}))]
            fixtures[identity_id] = {'client.identity':{'client_id':'synthetic-test-target'}}
        for path,row in docs:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(row,ensure_ascii=False)+'\n',encoding='utf-8')
        catalog=load_catalog(catalog_root)
        policy={'schema_version':'0.2.0','allowed_probe_ids':[f['capability_probe'] for f in catalog['functions']]}
        validate_catalog(catalog,policy)
        selection={'schema_version':'0.2.0','kind':'selection',
                   'functions':{f['function_id']:f['version'] for f in catalog['functions']},
                   'ports':{p['port_id']:p['version'] for p in catalog['ports']}}
        artifact=build_registry(catalog,selection,policy,Path(tmp)/'artifact.json')
        env=hashlib.sha256(b'gateway-v2-synthetic-replay-only').hexdigest()
        target=TargetContext(function['scope'],'synthetic-test-target',env)
        backend=StrictSkillReplayBackend(catalog['functions'],catalog['ports'],fixtures)
        bindings=[declare_binding(artifact,f['function_id'],'test.replay_'+f['function_id'].replace('.','_'),
                                  'test.fixture_replay',backend,target) for f in catalog['functions']]
        # Ephemeral TEST approval only (synthetic target/context + fixture source).
        # This is NOT a production approved digest / binding review.
        bind=BindingSelection(artifact,policy,bindings,
             approved_digests=frozenset(binding_digest(b) for b in bindings),
             backends={'test.fixture_replay':backend},context=target)
        permissions=frozenset({function['permission']})
        runtime=ReadRuntime(artifact,policy,approved_digest=artifact['content_digest'],
                            selection=bind,context=target,permissions=permissions,
                            policy_context_id=hashlib.sha256(b'test-only-acl').hexdigest())
        capabilities=runtime.probe()
        bridge=RuntimeSkillBridge(runtime,SkillCatalog.load())
        runner,plan=bridge.execute(slug,snapshot=capabilities)
        fact=runner.state.fact(port_id)
        if fact is None:
            raise AssertionError('shared Core did not admit verified synthetic fact')
        assessment = assess(runner.state) if assess is not None else None
        return {**({'assessment': assessment} if assess is not None else {}), 'synthetic_only':True,'function':fid,'skill':slug,
                'ports':list(function['outputs']),'verified_fact_present':True,
                'fact_value':copy.deepcopy(fact['value']),'evidence_id':fact['id'],
                'used_existing_graph_runner':True,'test_target':target.target_id,
                'core_calls':runner.calls,
                'verified_identity_present':runner.state.fact('client.identity') is not None,
                'operator_approved_for_real_network':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--function',default='expansion.radio_health')
    parser.add_argument('--all',action='store_true',help='Try all 72 synthetic functions through the same Core')
    parser.add_argument('--synthetic-only',action='store_true',required=True)
    options=parser.parse_args()
    if options.all:
        functions=json.loads((ROOT/'data/skill_expansion_v1/function_proposals.json').read_text(encoding='utf-8'))
        rows=[]; failed=0
        for function in functions:
            try:rows.append(smoke(function['function_id']))
            except Exception as e:
                failed+=1; rows.append({'function':function['function_id'],'error':type(e).__name__})
        print(json.dumps({'total':len(rows),'passed':len(rows)-failed,'failed':failed,'rows':rows},ensure_ascii=False,indent=2))
        raise SystemExit(1 if failed else 0)
    print(json.dumps(smoke(options.function),ensure_ascii=False,indent=2))
