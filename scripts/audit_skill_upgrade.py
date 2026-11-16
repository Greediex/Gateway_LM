"""Review all 120 skills against an existing v2 checkout. No writes in repo."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from gateway_pilot.skill_expansion.repo_audit import audit
from gateway_pilot.skill_expansion.edge_gate import analyze
from gateway_pilot.skill_expansion.catalog import SkillCatalog

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--repo',type=Path,required=True)
    a.add_argument('--output',type=Path)
    args=a.parse_args()
    report={'repo_audit':audit(args.repo),'edges':analyze(SkillCatalog.load())}
    payload=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(payload+'\n',encoding='utf-8')
        print('Saved',args.output)
    else:print(payload)
