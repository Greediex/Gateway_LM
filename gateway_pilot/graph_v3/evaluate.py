"""Fresh v3 structural evaluation plus optional local sub-3B analyst run.

Methods vary graph ranking, not the semantic validator. Never overwrite a run.
"""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from ..core import ROOT, PlanError, read_json, validate_decision
from ..run import http_json, prompt
from ..native_run import native_decision
from .contracts import Function, Port
from .graphs import GraphRegistry
from .state import CaseState
from .orchestrator import acquire
from .upstream import COMMIT, KERNEL_SHA256


def structural_fixture(size):
    """Analytic prerequisite-recovery fixture, not real-world retrieval accuracy."""
    r=GraphRegistry()
    shape={'type':'object','properties':{'value':{'type':'string'}},'required':['value']}
    p,q=Port('input','gateway',shape),Port('output','gateway',shape)
    r.ports={'input':p,'output':q}
    r.functions={
        'target':Function('target',('SK04',),{'input':p},{'output':q},'lookupneedle','gateway'),
        'zzz_prerequisite':Function('zzz_prerequisite',('SK04',),{}, {'input':p},'inventory producer','gateway')}
    for i in range(size-2):
        x=Port('noise'+str(i),'gateway',shape)
        r.ports[x.name]=x
        fid=f'aaa_noise_{i:04d}'
        r.functions[fid]=Function(fid,('SK04',),{}, {x.name:x},'unrelated telemetry counter','gateway')
    for fid,f in r.functions.items():
        r.legacy.functions[fid]={'id':fid,'produces':list(f.outputs),'requires':list(f.inputs),'risk':'READ','scope':'gateway','ttl_s':30}
    r.rebuild()
    case={'target':{'scope':'gateway','id':'gateway_01'},'capabilities':list(r.functions)}
    return r,CaseState(case,r)


def microbench():
    rows=[]
    for size in (4,16,64,128):
        r,s=structural_fixture(size)
        for method in ('bm25','gos'):
            result=r.retrieve('lookupneedle',['output'],s,k=2,method=method)
            rows.append({'library_size':size,'method':method,'selected':result['functions'],
                         'bundle_complete':{'target','zzz_prerequisite'}.issubset(result['functions']),
                         'upstream_kernel_used':result['upstream_kernel_used']})
    return rows


def evaluate_case(case,args):
    registry=GraphRegistry()
    state=CaseState(case,registry)
    started=time.perf_counter()
    graph=acquire(case,registry,state,method=args.method,max_calls=12)
    decisions,errors=[],[]
    terminal=None
    if args.model:
        for _ in range(3):
            messages=prompt(case,state,registry.legacy,[],3-len(decisions))
            messages[0]['content']='You are Gateway LM diagnostic analyst. All permitted measurements are collected. Use a terminal tool with supported evidence.'
            messages[1]['content']+='\nMEASUREMENT PHASE COMPLETE. No more tools are available. Return your diagnostic verdict now.'
            decision,meta=native_decision(args,messages)
            decisions.append({'decision':decision,**meta})
            try:
                validate_decision(decision,state,case,registry.legacy,[])
                terminal=decision
                break
            except PlanError as exc:
                errors.append(str(exc));state.errors.append(str(exc))
    gold=case['gold'] if args.model else None  # scoring only, after acquisition/model
    correct=bool(terminal and gold and terminal.get('action')==gold['action'] and terminal.get('diagnosis')==gold['diagnosis']) if args.model else None
    return {'case_id':case['id'],'workflow':case['workflow'],'graph':graph,'evidence':state.evidence,
            'executed':state.executed,'decisions':decisions,'rejections':errors,'terminal':terminal,
            'gold':gold,'autonomous_success':correct,'forced_stop':bool(args.model and terminal is None),
            'wall_s':time.perf_counter()-started}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--method',choices=['gos','bm25'],default='gos')
    p.add_argument('--model',default=None)
    p.add_argument('--split',choices=['test','dev'],default='test')
    p.add_argument('--limit',type=int)
    p.add_argument('--endpoint',default='http://127.0.0.1:11434')
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--timeout',type=int,default=120)
    args=p.parse_args()
    if args.output.exists():p.error('Fresh output directory required')
    if urlparse(args.endpoint).hostname not in ('localhost','127.0.0.1','::1'):p.error('Local model endpoint required')
    model_meta={}
    if args.model:
        show=http_json(args.endpoint,'show',{'model':args.model})
        count=show.get('model_info',{}).get('general.parameter_count',3_000_000_000)
        if type(count) is not int or not 0<count<3_000_000_000:p.error('Verified model parameter_count must be <3B')
        model_meta={'parameter_count':count,'details':show['details'],'tags':http_json(args.endpoint,'tags')}
    cases=[c for c in read_json(ROOT/'data/cases.json') if c['split']==args.split]
    if args.limit:cases=cases[:args.limit]
    args.output.mkdir(parents=True)
    legacy_manifest=read_json(ROOT/'data/frozen_manifest.json')
    for name,expected in legacy_manifest['sha256'].items():
        if hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Frozen data changed')
    source_paths=[*sorted((ROOT/'gateway_pilot/graph_v3').glob('*.py')), ROOT/'gateway_pilot/core.py',ROOT/'gateway_pilot/run.py',ROOT/'gateway_pilot/native_run.py']
    hashes={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in source_paths}
    metadata={'started_at':datetime.now(timezone.utc).isoformat(),'args':{**vars(args),'output':str(args.output)},
              'model':model_meta,'kernel':{'commit':COMMIT,'sha256':KERNEL_SHA256},'source_sha256':hashes,
              'dataset_manifest':legacy_manifest,'packages':{name:importlib.metadata.version(name) for name in ('numpy','jsonschema')},
              'limit':'Existing template suite; v3 is an engineering follow-up after prior results, not new blind holdout.'}
    (args.output/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    for path in source_paths:
        dest=args.output/'source_snapshot'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
    (args.output/'registry_v3.json').write_text(json.dumps(GraphRegistry().export(),indent=2),encoding='utf-8')
    micros=microbench()
    (args.output/'retrieval_microbench.json').write_text(json.dumps(micros,indent=2),encoding='utf-8')
    rows=[]
    for i,case in enumerate(cases):
        row=evaluate_case(case,args)
        rows.append(row)
        with (args.output/'episodes.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(f"[{i+1}/{len(cases)}] {case['id']} calls={row['graph']['calls']} repairs={row['graph']['repairs']} model_success={row['autonomous_success']} t={row['wall_s']:.1f}s",flush=True)
    summary={'cases':len(rows),'model_scored':bool(args.model),'autonomous_success':sum(r['autonomous_success'] for r in rows) if args.model else None,
             'forced_stops':sum(r['forced_stop'] for r in rows),'mean_calls':sum(r['graph']['calls'] for r in rows)/len(rows),
             'upstream_kernel_calls':sum(r['graph']['upstream_kernel_calls'] for r in rows),
             'repairs':sum(r['graph']['repairs'] for r in rows),
             'diagnosis_rejections':dict(Counter(e for r in rows for e in r['rejections'])),
             'microbench_bundle_completeness':{m:sum(x['bundle_complete'] for x in micros if x['method']==m) for m in ('bm25','gos')}}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    metadata['finished_at']=datetime.now(timezone.utc).isoformat()
    if args.model:metadata['runtime_after']=http_json(args.endpoint,'ps')
    (args.output/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print('GRAPH_V3_RUN_COMPLETE',json.dumps(summary),flush=True)


if __name__=='__main__':main()
