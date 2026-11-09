"""G_S, G_SF and H_F are distinct executable structures."""
from __future__ import annotations
import copy
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from jsonschema import Draft202012Validator

from ..core import PlanError, terms
from .contracts import from_legacy
from .upstream import rank


@dataclass(frozen=True)
class Relation:
    source: str  # consumer -> prerequisite for depends_on
    target: str
    kind: str
    weight: float = 1.0


class SkillGraph:
    KINDS = {"depends_on", "produces_for", "composes_with", "workflow", "similar_to",
             "specializes", "alternative_to", "conflicts_with"}

    def __init__(self, skills, relations):
        self.skills = copy.deepcopy(skills)
        self.edges = tuple(relations)
        self.version = 1
        self.validate()
        self.history = {1: self.edges}
        self.edits = []

    def validate(self):
        for e in self.edges:
            if (e.kind not in self.KINDS or e.source not in self.skills or e.target not in self.skills
                    or not math.isfinite(e.weight) or e.weight <= 0):
                raise PlanError("invalid_skill_relation")
        for sid in self.skills:
            deps = self.dependencies(sid)
            if self.conflicts({sid}, deps):
                raise PlanError('dependency_conflict_in_skill_graph')

    def propose_edge(self, edge):
        edges = tuple(e for e in self.edges if (e.source,e.target,e.kind)!=(edge.source,edge.target,edge.kind)) + (edge,)
        SkillGraph(self.skills, edges)  # independent dry-run validates constraints
        from dataclasses import asdict
        return {'base_version': self.version, 'edges': [asdict(e) for e in edges], 'operator': 'EDIT_EDGE'}

    def apply(self, proposal, *, permissions=(), actor='unknown'):
        if 'graph.edit' not in permissions:
            raise PlanError('graph_edit_permission')
        if proposal.get('base_version') != self.version:
            raise PlanError('graph_version_conflict')
        candidate = SkillGraph(self.skills, [Relation(**e) for e in proposal['edges']])
        self.edges = candidate.edges
        self.version += 1
        self.history[self.version] = self.edges
        self.edits.append({'version': self.version, 'actor': actor, 'operator': proposal.get('operator','EDIT_EDGE')})

    def rollback(self, version, *, permissions=(), actor='unknown'):
        if version not in self.history:
            raise PlanError('unknown_graph_history_version')
        from dataclasses import asdict
        self.apply({'base_version': self.version, 'edges': [asdict(e) for e in self.history[version]],
                    'operator': 'ROLLBACK'}, permissions=permissions, actor=actor)

    def dependencies(self, skill, stack=()):
        if skill in stack:
            raise PlanError("skill_dependency_cycle")
        result = set()
        for e in self.edges:
            if e.kind == "depends_on" and e.source == skill:
                result.add(e.target)
                result.update(self.dependencies(e.target, stack + (skill,)))
        return result

    def conflicts(self, left, right):
        return any(e.kind == "conflicts_with" and
                   ((e.source in left and e.target in right) or (e.target in left and e.source in right))
                   for e in self.edges)


class MembershipGraph:
    def __init__(self, functions):
        self.by_skill, self.by_function = defaultdict(set), {}
        for fid, f in functions.items():
            self.by_function[fid] = set(f.skills)
            for sid in f.skills:
                self.by_skill[sid].add(fid)


class SchemaHypergraph:
    def __init__(self, functions):
        self.functions = functions
        self.outputs = defaultdict(list)
        for fid, f in functions.items():
            for name in f.outputs:
                self.outputs[name].append(fid)

    def producers(self, required):
        return [fid for fid in self.outputs.get(required.name, [])
                if required.accepts(self.functions[fid].outputs[required.name])]


class GraphRegistry:
    def __init__(self, legacy=None):
        self.legacy, self.ports, self.functions = from_legacy(legacy)
        self.skills = copy.deepcopy(self.legacy.skills)
        self.goal_ports = copy.deepcopy(self.legacy.data["workflow_evidence"])
        # Skill completion contracts are explicit, not guessed from similarity.
        for sid, skill in self.skills.items():
            skill["completion_ports"] = ["client.identity"] if sid == "SK01" else []
        self.relations = [Relation(sid, dep, "depends_on") for sid, skill in self.skills.items()
                          for dep in skill.get("depends_on", [])]
        self.relations += [Relation(e["from"], e["to"], e["type"], e.get("weight", 1.0))
                           for e in self.legacy.data.get("relations", [])]
        self.function_conflicts = {frozenset(pair) for pair in self.legacy.data.get("conflicts", [])}
        self.rebuild()

    def rebuild(self):
        for f in self.functions.values():
            for name, port in [*f.inputs.items(), *f.outputs.items()]:
                if name != port.name or port.scope not in ("gateway", "client"):
                    raise PlanError("invalid_typed_port")
                Draft202012Validator.check_schema(port.schema)
            Draft202012Validator.check_schema(f.arguments_schema)
            if not math.isfinite(f.cost + f.latency_ms) or min(f.cost, f.latency_ms) < 0:
                raise PlanError("invalid_function_cost")
            if not f.outputs or not f.verifier or f.timeout_ms <= 0 or not math.isfinite(f.timeout_ms):
                raise PlanError("invalid_function_verifier_or_deadline")
            if any(sid not in self.skills for sid in f.skills):
                raise PlanError("unknown_skill_membership")
        self.gs = SkillGraph(self.skills, self.relations)
        self.gsf = MembershipGraph(self.functions)
        self.hf = SchemaHypergraph(self.functions)

    def objective(self, fid):
        f = self.functions[fid]
        return f.cost + f.latency_ms / 1000

    def export(self):
        from dataclasses import asdict
        return {"version": "3.0.0", "skill_graph_revision": self.gs.version, "skills": self.skills,
                "G_S": [asdict(e) for e in self.gs.edges],
                "G_SF": {k: sorted(v) for k,v in self.gsf.by_skill.items()},
                "H_F": {fid: asdict(f) for fid,f in self.functions.items()},
                "workflow_goals": self.goal_ports,
                "cost_note": "Declared policy cost/latency estimates, not board measurements"}

    def eligible(self, state, excluded=()):
        return {fid for fid, f in self.functions.items() if fid not in excluded and state.allowed(f)}

    def state_query(self, request, goals, state):
        missing = [p for p in goals if state.fact(p) is None]
        # Only verified facts contribute values. Untrusted logs remain data for model,
        # not instructions or graph-edit proposals.
        facts = []
        for port in self.ports:
            e = state.fact(port)
            if e and port != "system.logs":
                facts.append(port + " " + str(e["value"]))
        return request + " missing " + " ".join(missing) + " facts " + " ".join(facts) + " errors " + " ".join(state.errors[-2:])

    def retrieve(self, request, goals, state, k=4, *, method="gos", excluded=()):
        if method not in ("gos", "bm25") or not isinstance(k, int) or k <= 0:
            raise ValueError("unsupported retrieval method or nonpositive k")
        allowed = self.eligible(state, excluded)
        # Filter capability/permission and already-satisfied outputs BEFORE top-k.
        allowed = {fid for fid in allowed if not state.completed(self.functions[fid])}
        active_skills = {sid for fid in allowed for sid in self.gsf.by_function[fid]}
        active_skills |= {dep for sid in list(active_skills) for dep in self.gs.dependencies(sid)}
        names = sorted(["f:" + fid for fid in allowed] + ["s:" + s for s in active_skills])
        query = self.state_query(request, goals, state)
        docs = {}
        for name in names:
            text = (self.functions[name[2:]].description + " " + name[2:] if name.startswith("f:")
                    else self.skills[name[2:]]["name"])
            docs[name] = Counter(terms(text))
        q = sorted(set(terms(query)))
        df = {term: sum(term in d for d in docs.values()) for term in q}
        avg = sum(sum(d.values()) for d in docs.values()) / max(1, len(docs))
        lexical = {}
        for name, d in docs.items():
            lexical[name] = sum(math.log(1 + (len(docs) - df[t] + .5) / (df[t] + .5)) * d[t] * 2.2 /
                                (d[t] + 1.2 * (.25 + .75 * sum(d.values()) / max(1, avg))) for t in q)
        seeds = dict(sorted(lexical.items(), key=lambda x: (-x[1], x[0]))[:max(1, k)])
        lexical_match = any(seeds.values())
        if not lexical_match and names:
            seeds = {name: 1 for name in names[:k]}
        edges = []
        for fid in allowed:
            for sid in self.gsf.by_function[fid]:
                edges.append(("s:" + sid, "f:" + fid, "semantic", 1.0))
                edges.append(("f:" + fid, "s:" + sid, "semantic", 1.0))
            for required in self.functions[fid].inputs.values():
                for producer in self.hf.producers(required):
                    if producer in allowed and producer != fid:
                        edges.append(("f:" + producer, "f:" + fid, "dependency", 1.0))
        for e in self.gs.edges:
            a, b = "s:" + e.source, "s:" + e.target
            if a not in names or b not in names or e.kind == "conflicts_with":
                continue
            # Convert consumer->prereq to GoS's producer->consumer.
            if e.kind == "depends_on":
                edges.append((b, a, "dependency", e.weight))
            elif e.kind == "produces_for":
                edges.append((a, b, "dependency", e.weight))
            elif e.kind in {"composes_with", "workflow"}:
                edges.append((a, b, "workflow", e.weight))
            elif e.kind in {"similar_to", "specializes"}:
                edges.append((a, b, "semantic", e.weight))
            else:
                edges.append((a, b, "alternative", e.weight))
        scores = rank(names, edges, seeds) if method == "gos" and names else lexical
        candidates = sorted(allowed, key=lambda fid: (-scores.get("f:" + fid, 0), self.objective(fid), fid))[:k]
        return {"functions": candidates, "query": query, "seeds": seeds, "scores": scores,
                "eligible": sorted(allowed), "edges": edges, "method": method,
                "lexical_match": lexical_match,
                "upstream_kernel_used": method == "gos" and bool(names)}
