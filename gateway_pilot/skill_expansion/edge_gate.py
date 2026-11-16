"""Deterministic non-authoritative graph edge precheck.

This is a *review aid*, not graph.edit approval. No proposal can be promoted to
EXISTING or imported to runtime based only on this gate.
"""
from __future__ import annotations
from collections import defaultdict
from .catalog import SkillCatalog

def analyze(catalog: SkillCatalog) -> dict:
    rows=[]; tally=defaultdict(int)
    for edge in catalog.relations:
        reasons=[]
        source=catalog.skills[edge.source];target=catalog.skills[edge.target]
        if edge.type=='depends_on':
            reasons.append('REVIEW_TYPED_PORT_DEPENDENCY')
        elif edge.type=='produces_for':
            reasons.append('REVIEW_PRODUCER_CONSUMER_PORT_CONTRACT')
        elif edge.type=='workflow':
            reasons.append('REVIEW_WORKFLOW_ORDER_NOT_HARD_DEPENDENCY')
        elif edge.type=='composes_with' and source.domain==target.domain:
            reasons.append('SOFT_DOMAIN_AFFINITY_ONLY')
        else:
            reasons.append('REVIEW_SEMANTIC_RELATION')
        if edge.status=='EXISTING_V01':
            classification='EXISTING_REFERENCE'
        elif edge.type=='composes_with' and source.domain==target.domain:
            classification='STRUCTURALLY_VALID_NEEDS_SEMANTIC_REVIEW'
        else:
            classification='NEEDS_TYPED_CONTRACT_OR_OPERATOR_REVIEW'
        tally[classification]+=1
        rows.append({'source':edge.source,'target':edge.target,'kind':edge.type,
                     'source_status':edge.status,'classification':classification,
                     'notes':reasons,'runtime_approved':False})
    return {'total_edges':len(rows),'classifications':dict(sorted(tally.items())),
            'reviewed_by_operator':False,'can_import_into_runtime':False,'edges':rows}
