"""GoS lexical-seed mode, not full GoS with embeddings/LLM query rewrite.

UPSTREAM_CALLED: G_S and pinned PPR kernel. PORTED_WITH_PARITY_TEST: reduced
GoS field rerank and lexical seed fusion. GATEWAY_DESIGN: hard gates, BM25
index and Workflow/Skill/Function diffusion projection.
"""
from __future__ import annotations
import copy
import math
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from jsonschema import Draft202012Validator

from ..core import PlanError, terms
from .contracts import from_legacy
from .upstream import rank
from .skilldag import call, in_memory_graph


_TOKEN_STOPWORDS = set("a an and any arg args array bool boolean data dataframe dict file float for from "
                       "in input int json list object of on or output path record result set str string "
                       "text the that this to value which with without".split())


def fold(text):
    """GATEWAY_DESIGN: strip Vietnamese diacritics so accented, unaccented and
    English text share one token space. ASCII input is returned unchanged, so
    the upstream parity of the ported formulas is unaffected."""
    text = unicodedata.normalize("NFKD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _signature_tokens(values):
    """PORTED_WITH_PARITY_TEST: GoS engine.py:845-859 signature tokens.

    Upstream keeps only [a-z0-9], which shreds accented Vietnamese words;
    inputs are folded first (see fold)."""
    tokens = set()
    for value in values:
        lowered = fold(value).lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
        if normalized:
            tokens.add(normalized)
        for token in re.findall(r"[a-z0-9]+", lowered):
            token = token.rstrip("s") if len(token) > 3 else token
            if len(token) >= 3 and token not in _TOKEN_STOPWORDS:
                tokens.add(token)
    return tokens


def rerank_score(query, *, name, description="", tags=(), ports=(), graph_score=0.0,
                 seed_rank=None, lexical_rank=None):
    """PORTED_WITH_PARITY_TEST: reduced GoS engine.py:1096-1145,1918-1921.

    Lexical-seed mode only: pilot fields are name, description, tags and I/O
    port names; task/domain/tooling/artifact fields are absent. Seed fusion
    uses graph_score=0 (no semantic retrieval), plus .15/lexical_rank. After
    PPR use its graph_score and .2/seed_rank, without the seed-fusion bonus.
    Hard gates are never scoring terms.
    """
    query_tokens = _signature_tokens([query])
    score = graph_score
    for values, weight in (([name], 1.25), ([description], .9), (tags, 1.15), (ports, .75)):
        score += weight * len(query_tokens & _signature_tokens(values)) / max(len(query_tokens), 1)
    normalized_name = re.sub(r"[^a-z0-9]+", " ", fold(name).lower()).strip()
    if normalized_name and normalized_name in fold(query).lower():
        score += 1.2
    if seed_rank is not None:
        score += .2 / seed_rank
    if lexical_rank is not None:
        score += .15 / lexical_rank
    return score


@dataclass(frozen=True)
class Relation:
    source: str  # consumer -> prerequisite for depends_on
    target: str
    kind: str
    weight: float = 1.0


class SkillGraph:
    UPSTREAM_KINDS = {"depends_on", "composes_with", "similar_to", "specializes", "conflicts_with"}
    EXTENSION_KINDS = {"produces_for", "workflow", "alternative_to"}
    KINDS = UPSTREAM_KINDS | EXTENSION_KINDS

    def __init__(self, skills, relations):
        self.skills = copy.deepcopy(skills)
        relations = tuple(relations)
        for edge in relations:
            self._validate_relation(edge)
        self.extension_relations = tuple(e for e in relations if e.kind in self.EXTENSION_KINDS)
        self._reader = in_memory_graph(self.skills, relations)
        self.version = 1
        self.validate()
        self.history = {1: self.edges}
        self.edits = []

    @property
    def edges(self):
        return tuple(Relation(e["source"], e["target"], e["type"], e.get("weight", 1.0))
                     for e in self._reader.data["edges"]) + self.extension_relations

    def _validate_relation(self, e):
        if (e.kind not in self.KINDS or e.source not in self.skills or e.target not in self.skills
                or not math.isfinite(e.weight) or e.weight <= 0):
            raise PlanError("invalid_skill_relation")

    def validate(self):
        call(self._reader, "validate")
        for e in self.edges:
            self._validate_relation(e)
        for sid in self.skills:
            deps = self.dependencies(sid)
            if self.conflicts({sid}, deps):
                raise PlanError('dependency_conflict_in_skill_graph')

    def propose_edge(self, edge, *, reason=None):
        self._validate_relation(edge)
        if edge.kind in self.EXTENSION_KINDS:
            reason = call(self._reader, "_validate_reason", reason)
            if any((e.source, e.target, e.kind) == (edge.source, edge.target, edge.kind) for e in self.edges):
                raise PlanError("EDGE_ALREADY_EXISTS")
            proposal = {"would": {"action": "add", "source": edge.source, "target": edge.target,
                                   "type": edge.kind, "reason": reason}, "related": []}
        else:
            proposal = call(self._reader, "propose_edge", edge.source, edge.target, edge.kind, reason)
        return {**proposal, "base_version": self.version, "weight": edge.weight, "operator": "EDIT_EDGE"}

    def propose_remove_edge(self, source, target, edge_type, *, reason=None):
        return {**call(self._reader, "propose_remove_edge", source, target, edge_type, reason),
                "base_version": self.version, "operator": "EDIT_EDGE"}

    def propose_retype_edge(self, source, target, from_type, to_type, *, reason=None):
        return {**call(self._reader, "propose_retype_edge", source, target, from_type, to_type, reason),
                "base_version": self.version, "operator": "EDIT_EDGE",
                # Upstream's preview uses the OLD edge's normalized endpoints.
                # edit_edge must receive the original endpoints when the NEW
                # kind is directed (e.g. similar_to -> depends_on).
                "request": {"source": source, "target": target}}

    def _guard(self, permissions, base_version):
        if 'graph.edit' not in permissions:
            raise PlanError('graph_edit_permission')
        if base_version != self.version:
            raise PlanError('graph_version_conflict')

    def _record(self, result, actor):
        self.version += 1
        self.history[self.version] = self.edges
        self.edits.append({**copy.deepcopy(result["history_entry"]), "version": self.version,
                           "actor": actor, "operator": "ROLLBACK" if result["action"] == "rollback" else "EDIT_EDGE"})
        return result

    def apply(self, proposal, *, permissions=(), actor='unknown'):
        self._guard(permissions, proposal.get("base_version"))
        would = proposal["would"]
        endpoints = proposal.get("request", would)
        return self.edit_edge(would["action"], source=endpoints["source"], target=endpoints["target"],
                              edge_type=would.get("type"), from_type=would.get("from_type"),
                              to_type=would.get("to_type"), reason=would.get("reason"),
                              weight=proposal.get("weight"), base_version=proposal["base_version"],
                              permissions=permissions, actor=actor)

    def edit_edge(self, action, *, source, target, reason=None, edge_type=None, from_type=None,
                  to_type=None, task_id="", base_version=None, permissions=(), actor="unknown", weight=None):
        self._guard(permissions, base_version)
        reason = call(self._reader, "_validate_reason", reason)
        if edge_type in self.EXTENSION_KINDS and action == "add":
            edge = Relation(source, target, edge_type, 1.0 if weight is None else weight)
            self.propose_edge(edge, reason=reason)
            self.extension_relations += (edge,)
            return self._record({"applied": True, "action": action,
                                 "history_entry": {"action": "add_extension", "reason": reason}}, actor)
        candidate = copy.deepcopy(self._reader)
        result = call(candidate, "edit_edge", action, source=source, target=target, reason=reason,
                      task_id=task_id, edge_type=edge_type, from_type=from_type, to_type=to_type)
        # Weight is pilot projection metadata, not part of upstream edge identity.
        if action in {"add", "retype"}:
            applied = result["edge" if action == "add" else "to_edge"]
            old_weight = result.get("from_edge", {}).get("weight", 1.0)
            applied["weight"] = old_weight if weight is None else weight
            self._validate_relation(Relation(applied["source"], applied["target"], applied["type"], applied["weight"]))
            result["history_entry"]["edge" if action == "add" else "to_edge"]["weight"] = applied["weight"]
        self._reader = candidate
        return self._record(result, actor)

    def rollback(self, version=None, *, permissions=(), actor='unknown', reason=None,
                 base_version=None, steps=1, task_id=""):
        self._guard(permissions, self.version if base_version is None else base_version)
        reason = call(self._reader, "_validate_reason", reason)
        candidate = copy.deepcopy(self._reader)
        extensions = self.extension_relations
        if version is not None:
            if version not in self.history:
                raise PlanError('unknown_graph_history_version')
            if task_id or steps != 1:
                raise PlanError('ambiguous_graph_rollback_arguments')
            extensions = tuple(e for e in self.history[version] if e.kind in self.EXTENSION_KINDS)
            # Legacy rollback(version) also reverses intervening rollbacks.
            # Translate that revision journal to upstream's reversible edit
            # events; all edge inversions are still performed by rollback().
            # The temporary journal never replaces the append-only audit log.
            audit = candidate.data["history"]
            journal = []
            for entry in self.edits[version - 1:]:
                if entry["action"] in {"add_edge", "remove_edge", "retype_edge"}:
                    journal.append(copy.deepcopy(entry))
                elif entry["action"] == "rollback_edge":
                    for undo in entry["reverted"]:
                        if undo["undid"] == "add_edge":
                            journal.append({"action": "remove_edge", "edge": undo["removed"]})
                        elif undo["undid"] == "remove_edge":
                            journal.append({"action": "add_edge", "edge": undo["restored"]})
                        else:
                            journal.append({"action": "retype_edge", "from_edge": undo["from"],
                                            "to_edge": undo["back_to"]})
            candidate.data["history"] = journal
            steps = len(journal)
        if steps or version is None:
            result = call(candidate, "rollback", steps=steps, task_id=task_id, reason=reason)
        else:
            result = {"applied": True, "action": "rollback", "history_entry": {"action": "rollback_extension", "reason": reason}}
        if version is not None:
            candidate.data["history"] = audit + ([result["history_entry"]] if steps else [])
        call(candidate, "validate")
        self._reader, self.extension_relations = candidate, extensions
        return self._record(result, actor)

    def get_dependencies(self, skill, transitive=True):
        return call(self._reader, "get_dependencies", skill, transitive=transitive)

    def dependencies(self, skill, stack=()):
        # Hard prerequisites only. Upstream get_dependencies also walks the soft
        # composes_with relation; expand_set follows depends_on alone.
        return set(self.expand_set([skill])["added"])

    def get_conflicts(self, skill):
        return call(self._reader, "get_conflicts", skill)

    def conflicts(self, left, right):
        return any(e["target"] in right for skill in left for e in self.get_conflicts(skill)["conflicts"])

    def expand_set(self, selected):
        return call(self._reader, "expand_set", list(selected))

    def check_set(self, selected):
        return call(self._reader, "check_set", list(selected))

    def repair_set(self, selected):
        return call(self._reader, "repair_set", list(selected))

    def search(self, query, top_k=10, depth=2):
        return call(self._reader, "search", query, top_k, depth=depth)


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
    @classmethod
    def from_v01(cls, path=None, **kwargs):
        """Opt in to JSON-Schema validated data contracts (GATEWAY_DESIGN)."""
        from .registry_v01 import REGISTRY_PATH, load_registry
        return load_registry(REGISTRY_PATH if path is None else path, registry_class=cls, **kwargs)

    def __init__(self, legacy=None, *, provenance="synthetic_replay/"):
        self.legacy, self.ports, self.functions = from_legacy(legacy, provenance=provenance)
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
        # Contract/membership mutations go through rebuild(); G_S has its own
        # version. Identity and revision prevent cache collisions after reset.
        if not hasattr(self, "_retrieval_identity"):
            self._retrieval_identity = uuid.uuid4().hex
        self._registry_revision = getattr(self, "_registry_revision", 0) + 1
        self._retrieval_graph = None

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

    def contract_allowed(self, function):
        """v0.1 status/risk gate; legacy policy remains in CaseState.allowed."""
        if getattr(self, "contract_format", None) != "v0.1":
            return True
        return (function.risk in {"READ_ONLY", "PROBE"} and
                (function.status == "PROBED_OK" or
                 (function.status == "REPLAY_ONLY" and
                  function.adapter in {"synthetic_replay", "synthetic_replay/v1"})))

    def eligible(self, state, excluded=()):
        return {fid for fid, f in self.functions.items()
                if fid not in excluded and self.contract_allowed(f) and state.allowed(f)}

    def state_query(self, request, goals, state):
        missing = [p for p in goals if state.fact(p) is None]
        # Only verified facts contribute values. Untrusted logs remain data for model,
        # not instructions or graph-edit proposals.
        facts = []
        for port in self.ports:
            e = state.fact(port)
            if e and not self.ports[port].untrusted_text:
                facts.append(port + " " + str(e["value"]))
        return (request + (" missing " + " ".join(missing) if missing else "")
                + (" facts " + " ".join(facts) if facts else "")
                + (" errors " + " ".join(state.errors[-2:]) if state.errors else ""))

    def _static_retrieval_graph(self):
        """GATEWAY_DESIGN: one full projection per registry/G_S revision.

        Membership emits exactly one Skill->Function workflow edge per pair;
        only the upstream kernel supplies reverse mass. Typed dependency
        weight is the fraction of consumer inputs satisfied by the producer.
        """
        key = (self._retrieval_identity, getattr(self, "registry_version", self.legacy.data.get("version")),
               self._registry_revision, self.gs.version)
        if self._retrieval_graph is not None and self._retrieval_graph[0] == key:
            return self._retrieval_graph
        workflows = getattr(self, "workflows", {})
        names = tuple(sorted(["f:" + fid for fid in self.functions] + ["s:" + sid for sid in self.skills]
                             + ["w:" + wid for wid in workflows]))
        fields, docs = {}, {}
        for name in names:
            if name.startswith("f:"):
                f = self.functions[name[2:]]
                fields[name] = dict(name=f.id, description=f.description, tags=list(getattr(f, "tags", ())),
                                    ports=list(f.inputs) + list(f.outputs))
            elif name.startswith("w:"):
                workflow = workflows[name[2:]]
                fields[name] = dict(name=workflow["title"], description=" ".join(workflow["symptoms"]),
                                    tags=[workflow["kind"], workflow["target_scope"], *workflow.get("tags", ())],
                                    ports=list(workflow["goal_ports"]))
            else:
                skill = self.skills[name[2:]]
                fields[name] = dict(name=skill["name"], description=skill.get("description", ""),
                                    tags=list(skill.get("tags", ())),
                                    ports=list(skill.get("requires", ())) + list(skill.get("produces", ())))
            row = fields[name]
            docs[name] = Counter(terms(fold(" ".join([row['name'], row['description'], *row['tags'], *row['ports']]))))
        edges, provenance = [], []

        def add(a, b, kind, weight, origin, evidence, **metadata):
            edges.append((a, b, kind, weight))
            provenance.append(dict(source=a, target=b, type=kind, weight=weight,
                                   provenance=origin, evidence=evidence, **metadata))

        for wid, workflow in workflows.items():
            for sid in workflow["skill_ids"]:
                if sid in self.skills:
                    add("w:" + wid, "s:" + sid, "workflow", 1.0, "GATEWAY_DESIGN", [wid, sid],
                        relation="workflow_skill")
        for fid, consumer in self.functions.items():
            for sid in sorted(self.gsf.by_function[fid]):
                add("s:" + sid, "f:" + fid, "workflow", 1.0, "GATEWAY_DESIGN", [sid, fid],
                    relation="membership")
            for pid, producer in self.functions.items():
                if pid == fid or not consumer.inputs:
                    continue
                matches = sorted(p.name for p in consumer.inputs.values()
                                 if any(p.accepts(out) for out in producer.outputs.values()))
                if matches:
                    weight = len(matches) / len(consumer.inputs)
                    add("f:" + pid, "f:" + fid, "dependency", weight, "deterministic_io", matches,
                        confidence=weight)
        for e in (*self.gs.edges, *getattr(self, "extension_relations", ())):
            a, b = "s:" + e.source, "s:" + e.target
            if e.kind == "conflicts_with":
                continue
            # Convert consumer->prereq to GoS's producer->consumer.
            if e.kind == "depends_on":
                a, b, kind = b, a, "dependency"
            elif e.kind == "produces_for":
                kind = "dependency"
            elif e.kind in {"composes_with", "workflow"}:
                kind = "workflow"
            elif e.kind in {"similar_to", "specializes"}:
                kind = "semantic"
            else:
                kind = "alternative"
            add(a, b, kind, e.weight, getattr(e, "origin", "declared_gs"), [e.source, e.target], relation=e.kind)
        self._retrieval_graph = key, names, tuple(edges), provenance, fields, docs
        return self._retrieval_graph

    def retrieve(self, request, goals, state, k=None, *, seed_top_k=None, top_n=None,
                 workflow_top_n=3, method="gos", excluded=()):
        """GoS lexical-seed mode (no embeddings or LLM rewrite).

        PORTED_WITH_PARITY_TEST: field rerank + lexical rank fusion, then PPR
        candidate scan/rerank. UPSTREAM_CALLED: reciprocal personalization/PPR.
        GATEWAY_DESIGN: BM25 index, projection and hard gates before seeds and
        final selection. k is the legacy alias for both unspecified function
        budgets. Workflow results have their own PPR scan/rerank and budget;
        CATALOG_ONLY/CHANGE records never seed function selection or add goals.
        """
        if k is not None and (type(k) is not int or k <= 0):
            raise ValueError("nonpositive or invalid k")
        seed_top_k = seed_top_k if seed_top_k is not None else (k if k is not None else 4)
        top_n = top_n if top_n is not None else (k if k is not None else 5)
        if method not in ("gos", "bm25") or any(type(n) is not int or n <= 0
                                               for n in (seed_top_k, top_n, workflow_top_n)):
            raise ValueError("unsupported retrieval method or nonpositive budget")
        allowed = {fid for fid in self.eligible(state, excluded) if not state.completed(self.functions[fid])}
        key, names, edges, provenance, fields, docs = self._static_retrieval_graph()
        query = self.state_query(request, goals, state)
        q = sorted(set(terms(fold(query))))
        df = {term: sum(term in d for d in docs.values()) for term in q}
        avg = sum(sum(d.values()) for d in docs.values()) / max(1, len(docs))
        lexical = {name: sum(math.log(1 + (len(docs) - df[t] + .5) / (df[t] + .5)) * d[t] * 2.2 /
                             (d[t] + 1.2 * (.25 + .75 * sum(d.values()) / max(1, avg))) for t in q)
                   for name, d in docs.items()}
        # BM25 uses every node, then gates precede seed fusion/top-k. Forbidden
        # and completed functions remain in the diffusion graph.
        workflows = getattr(self, "workflows", {})
        workflow_hits = sorted((n for n in names if n.startswith("w:") and lexical[n] > 0),
                               key=lambda n: (-lexical[n], n))
        workflow_seed_scores = {n: rerank_score(query, **fields[n], lexical_rank=i)
                                for i, n in enumerate(workflow_hits, 1)}
        workflow_seeds = sorted(workflow_hits, key=lambda n: (-workflow_seed_scores[n], n))[:seed_top_k]
        workflow_results = []
        if workflow_seeds:
            workflow_scores = rank(names, edges, workflow_seeds, graph_key=key) if method == "gos" else lexical
            workflow_ranks = {n: i for i, n in enumerate(workflow_seeds, 1)}
            for n in sorted((n for n in names if n.startswith("w:")),
                            key=lambda n: (-workflow_scores[n], n)):
                if workflow_scores[n] <= 0:
                    continue
                workflow_results.append(dict(workflow_id=n[2:], status=workflows[n[2:]]["status"],
                    score=workflow_scores[n], rerank_score=(rerank_score(query, **fields[n],
                        graph_score=workflow_scores[n], seed_rank=workflow_ranks.get(n))
                        if method == "gos" else lexical[n])))
                if len(workflow_results) >= workflow_top_n:
                    break
            workflow_results.sort(key=lambda w: (-w["rerank_score"], -w["score"], w["workflow_id"]))

        def may_seed(n):
            if n.startswith("w:"):
                row = workflows[n[2:]]
                return row["status"] != "CATALOG_ONLY" and row["kind"] != "CHANGE"
            return n.startswith("s:") or n[2:] in allowed

        hits = sorted((n for n in names if lexical[n] > 0 and may_seed(n)),
                      key=lambda n: (-lexical[n], n))
        seed_scores = {n: rerank_score(query, **fields[n], lexical_rank=i)
                       for i, n in enumerate(hits, 1)}
        ordered_seeds = sorted(seed_scores, key=lambda n: (-seed_scores[n], n))[:seed_top_k]
        seed_ranks = {n: i for i, n in enumerate(ordered_seeds, 1)}
        total = sum(1 / i for i in seed_ranks.values())
        seeds = {n: (1 / i) / total for n, i in seed_ranks.items()}
        lexical_match = bool(seeds)
        scores, reranked, candidates = {}, {}, []
        if lexical_match:
            scores = rank(names, edges, ordered_seeds, graph_key=key) if method == "gos" else lexical
            # async_retrieve scans PPR order, stops at top_n, then sorts that
            # selected subset by the field rerank (not a global rerank).
            for n in sorted(names, key=lambda n: (-scores[n], n)):
                if not n.startswith("f:") or n[2:] not in allowed:
                    continue
                if method == "bm25" and scores[n] <= 0:
                    continue
                candidates.append(n[2:])
                reranked[n] = (rerank_score(query, **fields[n], graph_score=scores[n],
                                            seed_rank=seed_ranks.get(n)) if method == "gos" else scores[n])
                if len(candidates) >= top_n:
                    break
            candidates.sort(key=lambda fid: (-reranked["f:" + fid], -scores["f:" + fid], self.objective(fid), fid))
        return {"functions": candidates, "workflows": workflow_results,
                "query": query, "seeds": seeds, "scores": scores,
                "eligible": sorted(allowed), "edges": list(edges), "method": method,
                "lexical_match": lexical_match,
                "upstream_kernel_used": method == "gos" and (lexical_match or bool(workflow_seeds)),
                "rerank_scores": reranked, "seed_ranks": seed_ranks, "graph_key": key,
                "edge_provenance": copy.deepcopy(provenance)}
