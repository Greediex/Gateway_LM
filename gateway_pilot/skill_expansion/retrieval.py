"""Offline retrieval preview for a 120-Skill design graph.

This is NOT the repo's production GoS / SkillDAG / Planner. It creates no
Function invocations. Rank uses BM25 lexical seeds + a small weighted
PageRank-style diffusion on permitted graph edges for human review.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass
from math import log
import re
import unicodedata
from .catalog import SkillCatalog

STOP = frozenset("la cua va cho trong tren mot nhung cac duoc can kiem tra kiemtra he thong mang network system check "
                 "do the a an of or in on to for is are be why tai sao do dau nao hien tai khong vao muon can biet co the".split())

def tokens(value: str) -> list[str]:
    value = re.sub(r'(?i)\bwi[\s-]?fi\b', 'wifi', value)
    value = value.replace('đ','d').replace('Đ','D')
    norm = unicodedata.normalize('NFKD', value)
    stripped = ''.join(c for c in norm if not unicodedata.combining(c)).lower()
    return [x for x in re.findall(r'[a-z0-9]+', stripped) if x not in STOP and len(x)>1]

@dataclass(frozen=True)
class SearchHit:
    skill_id: str
    name: str
    score: float
    lexical: float
    graph: float
    status: str
    priority: str
    runtime_status: str

class SkillRetriever:
    def __init__(self, catalog: SkillCatalog):
        self.catalog = catalog
        self.documents = {}
        for s in catalog.skills.values():
            # Descriptive metadata is allowed to seed retrieval; never an executable command.
            self.documents[s.id] = tokens(' '.join([s.name_vi]*3 + [s.domain_name, s.kind]))

    def lexical_scores(self, query: str, *, include_proposed: bool = False) -> dict[str,float]:
        allowed = {sid for sid,s in self.catalog.skills.items()
                   if include_proposed or s.catalog_status=="EXISTING_V01"}
        docs={sid: self.documents[sid] for sid in allowed}
        if not docs: return {}
        avg_length=sum(len(d) for d in docs.values())/len(docs)
        df=Counter(term for doc in docs.values() for term in set(doc))
        query_terms=tokens(query)
        scores={}
        for sid,doc in docs.items():
            counts=Counter(doc)
            score=0.0
            for term in query_terms:
                tf=counts[term]
                if tf:
                    idf=log(1 + (len(docs)-df[term]+.5)/(df[term]+.5))
                    score += idf * tf * 2.2/(tf + 1.2*(.25+.75*len(doc)/max(avg_length,1)))
            scores[sid]=score
        return scores

    def graph_scores(self, seeds: dict[str,float], *, include_proposed: bool = False,
                     damping: float = .80, iterations: int = 32) -> dict[str,float]:
        """Personalized PageRank over soft relevance graph for retrieval only.

        Direction is ignored for retrieval similarity, NEVER for dependencies.
        Proposed edges are excluded by default. No edges can authorize a tool.
        """
        available = {sid for sid,s in self.catalog.skills.items()
                     if include_proposed or s.catalog_status=="EXISTING_V01"}
        if not available: return {}
        active={sid: max(0.0, score) for sid,score in seeds.items() if sid in available and score>0}
        total=sum(active.values())
        if total <= 0: return {sid:0.0 for sid in available}
        teleport={sid:value/total for sid,value in active.items()}
        weights: dict[str,dict[str,float]]=defaultdict(lambda: defaultdict(float))
        factors={"depends_on": .9, "composes_with":.40, "produces_for":.65,
                 "workflow": .50, "similar_to":.85, "specializes":.65,
                 "alternative_to":.40, "conflicts_with":0.0}
        for relation in self.catalog.relations:
            if not include_proposed and relation.status != "EXISTING_V01": continue
            if relation.source not in available or relation.target not in available: continue
            factor=factors.get(relation.type,0.0)
            if factor <= 0: continue
            w=relation.weight*factor
            # A reversible link in a retrieval projection is NOT a dependency.
            weights[relation.source][relation.target]+=w
            weights[relation.target][relation.source]+=w
        probs=dict(teleport)
        for _ in range(iterations):
            next_probs={sid:(1-damping)*teleport.get(sid,0.0) for sid in available}
            stray=0.0
            for sid,val in probs.items():
                neighbors=weights[sid]
                if not neighbors:
                    stray+=val
                else:
                    denom=sum(neighbors.values())
                    for target,w in neighbors.items():
                        next_probs[target]+=damping*val*w/denom
            for sid,t in teleport.items():
                next_probs[sid]+=damping*stray*t
            probs=next_probs
        return probs

    def search(self, query: str, *, limit: int=10,
               include_proposed: bool=False, graph_weight: float=.30) -> list[SearchHit]:
        if not 0<=graph_weight<=1: raise ValueError('graph_weight must be between 0 and 1')
        if limit<1: raise ValueError('limit must be >= 1')
        lexical=self.lexical_scores(query,include_proposed=include_proposed)
        if not any(lexical.values()): return []
        seeds={sid:score for sid,score in lexical.items() if score>0}
        graph=self.graph_scores(seeds,include_proposed=include_proposed)
        best_lex=max(lexical.values(),default=0.0)
        best_graph=max(graph.values(),default=0.0)
        hits=[]
        for sid,s in self.catalog.skills.items():
            if not include_proposed and s.catalog_status != 'EXISTING_V01': continue
            l=lexical.get(sid,0)/best_lex if best_lex else 0
            g=graph.get(sid,0)/best_graph if best_graph else 0
            score=(1-graph_weight)*l+graph_weight*g
            if score <= 0.00001: continue
            hits.append(SearchHit(sid,s.name_vi,round(score,6),round(l,6),round(g,6),
                                  s.catalog_status,s.priority,s.runtime_status))
        return sorted(hits,key=lambda h:(-h.score,h.skill_id))[:limit]
