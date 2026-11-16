"""Audit existing Registry v0.1 vs 120-Skill proposal without mutating repo."""
from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict
from .catalog import SkillCatalog

class AuditError(ValueError): pass

def audit(repo: Path|str, catalog: SkillCatalog|None=None) -> dict:
    repo=Path(repo)
    file=repo/'data/registry_v01.json'
    if not file.is_file() or not (repo/'gateway_pilot/graph_v3/graphs.py').is_file():
        raise AuditError('not a Gateway LM v2-style checkout')
    original=json.loads(file.read_text(encoding='utf-8'))
    if not isinstance(original.get('skills'),list) or not isinstance(original.get('functions'),list):
        raise AuditError('registry format invalid')
    catalog=catalog or SkillCatalog.load()
    old_skills={row['skill_id']:row for row in original['skills']}
    old_functions={row['function_id']:row for row in original['functions']}
    skill_to_functions=defaultdict(list)
    for fid,row in old_functions.items():
        for sid in row.get('skill_ids',[]):
            if sid not in old_skills:
                raise AuditError('legacy function points to unknown skill')
            skill_to_functions[sid].append(fid)
    plan=json.loads((Path(__file__).resolve().parents[2]/'data/skill_expansion_v1/skill_function_mapping_120.json').read_text(encoding='utf-8'))
    present=[]
    for s in sorted(catalog.skills.values(),key=lambda r:r.id):
        p=next(x for x in plan if x['skill_id']==s.id)
        present.append({'id':s.id,'name_vi':s.name_vi,'existing_registry':s.id in old_skills,
            'existing_v01_functions':sorted(skill_to_functions[s.id]),
            'proposed_v02_function_refs':p['declared_v02_function_refs'],
            'status':'V01_DECLARED' if s.id in old_skills else 'PROPOSED_NOT_LIVE'})
    original_edges={(r['source'],r['target'],r['type']) for r in original.get('relations',[])}
    missing_old={(r.source,r.target,r.type) for r in catalog.relations if r.status=='EXISTING_V01'}-original_edges
    if missing_old:raise AuditError('reference relations drift; review required:'+str(sorted(missing_old)))
    return {'registry_v01_skills':len(old_skills),'registry_v01_functions':len(old_functions),
        'proposal_skills':len(catalog.skills),'proposed_function_contracts':sum(bool(x['proposed_v02_function_refs']) for x in present),
        'proposed_edges':sum(r.status=='PROPOSED' for r in catalog.relations),
        'skill_rows':present,'does_not_change_runtime':True}
