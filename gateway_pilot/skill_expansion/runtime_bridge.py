"""Opt-in bridge to the *existing* Gateway_LM Core v0.2.

No separate Runner, bypass, runtime registration or silent approval. Runtime
comes from trusted operator startup; proposed IDs are rejected unless actually
present in that runtime's validated registry and its provider capability lease.
"""
from __future__ import annotations
from dataclasses import dataclass
from .catalog import SkillCatalog

class SkillNotReady(PermissionError):
    """Skill is not an explicitly available READ capability."""

@dataclass(frozen=True)
class SkillReadPlan:
    skill_id: str
    runtime_skill_id: str
    function_ids: tuple[str,...]
    goals: tuple[str,...]

class RuntimeSkillBridge:
    def __init__(self, runtime, catalog: SkillCatalog | None = None):
        # Runtime must be the real operator-owned ReadRuntime or a deliberate test double.
        self.runtime = runtime
        self.catalog = catalog or SkillCatalog.load()

    @staticmethod
    def _runtime_id(sid: str) -> str:
        return sid if sid.startswith('SK') else 'gateway.'+sid.lower()

    def plan(self, sid: str, *, snapshot=None) -> SkillReadPlan:
        if sid not in self.catalog.skills:
            raise SkillNotReady('unknown_skill')
        rid=self._runtime_id(sid)
        registry=self.runtime.registry
        if getattr(registry,'contract_format',None)!='v0.2':
            raise SkillNotReady('runtime_must_be_v02')
        skill=registry.skills.get(rid)
        if not skill:
            raise SkillNotReady('skill_not_in_approved_registry')
        if snapshot is None:
            raise SkillNotReady('runtime_capability_snapshot_required')
        if (getattr(snapshot,'registry_digest',None)!=registry.catalog_digest or
            getattr(snapshot,'context',None)!=self.runtime.context or
            getattr(snapshot,'permissions',None)!=self.runtime.permissions or
            getattr(snapshot,'policy_context_id',None)!=self.runtime.policy_context_id):
            raise SkillNotReady('capability_context_mismatch')
        # Never grant by copying a proposal's Function IDs. Derive membership
        # exclusively from the loaded approved Runtime registry.
        functions={fid:f for fid,f in registry.functions.items() if rid in f.skills}
        if not functions:
            raise SkillNotReady('no_registered_function')
        statuses={f.function_id: f for f in snapshot.functions}
        for fid,f in functions.items():
            capability=statuses.get(fid)
            if (capability is None or capability.status!='AVAILABLE' or
                capability.version != f.version or capability.metadata_digest != f.metadata_digest or
                f.scope != self.runtime.context.scope or f.permission not in self.runtime.permissions):
                raise SkillNotReady('function_not_available:'+fid)
        # Snapshot time lease checked using runtime's own trusted clock.
        if not snapshot.checked_at <= self.runtime._clock() < snapshot.expires_at:
            raise SkillNotReady('capability_expired')
        goals=set()
        completion=set(skill.get('completion_ports', ()))
        outputs={pid for f in functions.values() for pid in f.outputs}
        if not completion or not completion <= outputs:
            raise SkillNotReady('completion_port_not_produced')
        goals.update(completion)
        return SkillReadPlan(sid,rid,tuple(sorted(functions)),tuple(sorted(goals)))

    def execute(self, sid: str, *, snapshot, max_calls: int=12):
        """Always enters the existing `ReadRuntime.execute` -> GraphRunner path."""
        plan=self.plan(sid,snapshot=snapshot)
        if type(max_calls) is not int or not 1<=max_calls<=64:
            raise ValueError('invalid_call_budget')
        return self.runtime.execute(plan.goals, request=f'Approved skill READ: {plan.runtime_skill_id}',max_calls=max_calls)
