"""Run with: python -m gateway_pilot.skill_expansion.cli <command>."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .catalog import SkillCatalog
from .retrieval import SkillRetriever
from .review import candidate_edges_for_review, existing_v01_edges

def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description='Gateway_LM 120-Skill proposal: offline only, no tools executed')
    p.add_argument('--data-dir',type=Path, help='Override catalog data directory for offline review')
    commands=p.add_subparsers(dest='cmd',required=True)
    commands.add_parser('validate',help='Validate catalog + dependency acyclicity')
    commands.add_parser('stats',help='Summarize design catalog')
    cv=commands.add_parser('coverage',help='COV-01 inventory derived from data/deployments')
    cv.add_argument('--output',type=Path,help='Save full per-Skill JSON report')
    s=commands.add_parser('search',help='BM25 + weighted graph retrieval preview')
    s.add_argument('query');s.add_argument('--top',type=int,default=10)
    s.add_argument('--include-proposed',action='store_true',help='Design preview only; NOT runtime')
    s.add_argument('--graph-weight',type=float,default=.30)
    d=commands.add_parser('deps',help='Inspect hard prerequisite closure')
    d.add_argument('skill_ids',nargs='+');d.add_argument('--preview-proposed',action='store_true')
    n=commands.add_parser('neighbors',help='Typed graph edges touching one Skill')
    n.add_argument('skill_id');n.add_argument('--include-proposed',action='store_true')
    e=commands.add_parser('export-dot',help='Export design graph for Graphviz')
    e.add_argument('--output',type=Path,required=True);e.add_argument('--include-proposed',action='store_true')
    e.add_argument('--ids',nargs='*')
    r=commands.add_parser('review-diff',help='Show existing/proposed edges for operator review')
    r.add_argument('--output',type=Path,help='Save JSON diff')
    args=p.parse_args(argv)
    try:
        catalog=SkillCatalog.load(args.data_dir) if args.data_dir else SkillCatalog.load()
        if args.cmd == 'validate':
            output={'valid':True, **catalog.summary()}
        elif args.cmd == 'stats':
            output=catalog.summary()
        elif args.cmd == 'coverage':
            from .coverage import coverage_report
            report=coverage_report(data_dir=args.data_dir) if args.data_dir else coverage_report()
            if args.output:
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            output=report['summary']
        elif args.cmd == 'search':
            hits=SkillRetriever(catalog).search(args.query,limit=args.top,
                include_proposed=args.include_proposed,graph_weight=args.graph_weight)
            output={'query':args.query, 'proposal_preview':args.include_proposed,
                    'can_execute':False,'hits':[vars(h) for h in hits]}
        elif args.cmd == 'deps':
            output={'chosen':args.skill_ids,'proposed_dependencies_preview':args.preview_proposed,
                    'hard_dependencies':sorted(catalog.hard_dependencies(args.skill_ids,
                                              preview_proposed=args.preview_proposed)),
                    'can_execute':False}
        elif args.cmd == 'neighbors':
            output={'id':args.skill_id,'edges':[vars(x) for x in catalog.neighbors(args.skill_id,
                                            include_proposed=args.include_proposed)]}
        elif args.cmd == 'export-dot':
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(catalog.export_graphviz_dot(skill_ids=args.ids or None,
                                               include_proposed=args.include_proposed),encoding='utf-8')
            output={'saved':str(args.output),'proposal_preview':args.include_proposed}
        elif args.cmd == 'review-diff':
            output={'existing_v01':existing_v01_edges(catalog),'proposed':candidate_edges_for_review(catalog),
                    'warning':'Unapproved: do not auto-merge into runtime.'}
            if args.output:
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                output={'saved':str(args.output),'existing':len(existing_v01_edges(catalog)),
                        'proposed':len(candidate_edges_for_review(catalog))}
        print(json.dumps(output,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,KeyError,FileNotFoundError,json.JSONDecodeError) as exc:
        p.exit(2, f'ERROR: {exc}\n')

if __name__ == '__main__': raise SystemExit(main())
