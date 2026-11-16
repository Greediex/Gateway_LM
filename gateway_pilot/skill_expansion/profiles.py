"""CAT-01 metadata selection and mapping audit. No runtime/probe/approval I/O."""
from __future__ import annotations

import copy
from dataclasses import asdict
from collections import Counter
from pathlib import Path

from ..core import ROOT
from ..command_catalog.builder import build_registry
from ..command_catalog.contracts import _SCHEMA, _json_value, validate_contract
from jsonschema import Draft202012Validator
from ..command_catalog.indexes import GROUP_KEYS, build_indexes
from ..command_catalog.loader import _parse, _read_bytes, digest, read_json, require
from ..command_catalog.validator import select_catalog, validate_catalog
from .catalog import Relation, Skill, SkillCatalog

DEFAULT_PROFILE = ROOT / 'config/skill_profiles/wifi_gateway_replay_v1.json'
_MODES = {'LEGACY_DISCOVER_FROM_REPO', 'PROPOSED_READ_METADATA', 'NO_DIRECT_READ_FUNCTION'}
_MAPPING_FIELDS = {'skill_id', 'catalog_skill_id', 'name_vi', 'domain', 'proposal_mode',
                   'declared_v02_function_refs', 'requires_operator_review', 'runtime_enabled', 'comment',
                   'suggested_evidence_functions', 'evidence_scope_set', 'cross_scope_aggregation',
                   'suggestions_are_bindings', 'requires_claim_or_workflow_definition'}


def _array(path: Path) -> list:
    # Reuse bounded duplicate-key/nonfinite JSON parser; source files are arrays.
    rows = _parse(b'{"rows":' + _read_bytes(path, 1048576) + b'}')['rows']
    _json_value(rows)
    require(type(rows) is list and len(rows) <= 10000, 'profile_array')
    return rows


def load_bundle(repo: Path = ROOT) -> dict:
    from ..command_catalog.loader import load_catalog
    repo = Path(repo)
    data = repo / 'data/skill_expansion_v1'
    skills, relations = _array(data/'skills.json'), _array(data/'relations.json')
    design = SkillCatalog([Skill(**s) for s in skills], [Relation(**r) for r in relations])
    catalog = load_catalog(repo/'proposed_catalog_v02')
    # Vocabulary only, not a probe implementation or authorization.
    policy = {'schema_version':'0.2.0', 'allowed_probe_ids':sorted({f['capability_probe'] for f in catalog['functions']})}
    validate_catalog(catalog, policy)
    aggregate = _array(data/'function_proposals.json')
    require(sorted(aggregate, key=lambda f:f['function_id']) == sorted(catalog['functions'], key=lambda f:f['function_id']),
            'aggregate_proposal_drift')
    return {'design':design, 'mapping':_array(data/'skill_function_mapping_120.json'),
            'catalog':catalog, 'policy':policy, 'legacy':read_json(repo/'data/registry_v01.json', max_bytes=1048576)}


def bundle_digest(bundle: dict) -> str:
    catalog = bundle['catalog']
    return digest({'skills':sorted([asdict(s) for s in bundle['design'].skills.values()], key=lambda r:r['id']),
                   'relations':sorted([asdict(r) for r in bundle['design'].relations], key=lambda r:(r['source'],r['target'],r['type'])),
                   'mapping':sorted(bundle['mapping'], key=lambda r:r['skill_id']),
                   'records':{group:sorted(catalog[group], key=lambda r:(r[key],r['version'])) for group,key in GROUP_KEYS.items()},
                   'legacy':bundle['legacy']})


def audit_mappings(bundle: dict) -> list[dict]:
    """Resolve every mapping to owning contracts; suggestions never authorize."""
    indexed = validate_catalog(bundle['catalog'], bundle['policy'])
    design, mapping = bundle['design'], bundle['mapping']
    require(type(mapping) is list and len(mapping) == len(design.skills), 'mapping_count')
    require(all(type(r) is dict and _MAPPING_FIELDS <= set(r) <= _MAPPING_FIELDS | {'notes'} for r in mapping), 'mapping_fields')
    ids = [r['skill_id'] for r in mapping]
    require(all(type(s) is str for s in ids) and len(ids) == len(set(ids)), 'duplicate_mapping')
    require(set(ids) == set(design.skills), 'unknown_or_missing_mapping')
    versions = {}
    for (fid, version), f in indexed['functions'].items():
        require(fid not in versions, 'ambiguous_function_version')
        versions[fid] = f
    legacy = bundle['legacy']
    legacy_skills = {s['skill_id']:s for s in legacy['skills']}
    require({sid for sid,s in design.skills.items() if s.catalog_status == 'EXISTING_V01'} == set(legacy_skills),
            'legacy_reference_drift')
    rows, owners = [], set()
    for row in sorted(mapping, key=lambda r:r['skill_id']):
        sid, mode = row['skill_id'], row['proposal_mode']
        s = design.skills[sid]
        rid = sid if s.catalog_status == 'EXISTING_V01' else 'gateway.'+sid.lower()
        require(row['catalog_skill_id'] == rid and row['domain'] == s.domain and row['name_vi'] == s.name_vi
                and type(mode) is str and mode in _MODES, 'mapping_identity')
        require(row['requires_operator_review'] is True and row['runtime_enabled'] is False
                and row['suggestions_are_bindings'] is False, 'mapping_cannot_grant_execution')
        refs, suggestions = row['declared_v02_function_refs'], row['suggested_evidence_functions']
        for values in (refs, suggestions):
            require(type(values) is list and all(type(v) is str for v in values)
                    and len(values) == len(set(values)) and set(values) <= set(versions), 'mapping_function_refs')
        scopes = sorted({versions[fid]['scope'] for fid in suggestions})
        require(row['evidence_scope_set'] == scopes and row['cross_scope_aggregation'] is (len(scopes)>1), 'mapping_scope_claim')
        completions, gaps, legacy_refs = {}, [], []
        if mode == 'LEGACY_DISCOVER_FROM_REPO':
            require(s.catalog_status == 'EXISTING_V01' and sid in legacy_skills and not refs and not suggestions
                    and row['requires_claim_or_workflow_definition'] is False, 'invalid_legacy_mapping')
            legacy_refs = sorted(f['function_id'] for f in legacy['functions'] if sid in f['skill_ids'])
            require(bool(legacy_refs), 'legacy_without_function')
            gaps.append('LEGACY_REQUIRES_EXPLICIT_V02_MAPPING')
        elif mode == 'PROPOSED_READ_METADATA':
            require(s.catalog_status == 'PROPOSED' and bool(refs) and set(refs) == set(suggestions)
                    and row['requires_claim_or_workflow_definition'] is False, 'invalid_direct_mapping')
            skill_versions = set()
            for fid in refs:
                f = versions[fid]
                memberships = [ref for ref in f['skill_refs'] if ref['skill_id'] == rid]
                require(len(memberships) == 1, 'mapping_membership')
                skill_versions.add(memberships[0]['version'])
                owners.add(fid)
                if f['scope'] == 'client' and 'client.identity' not in f['outputs'] and 'client.identity' not in f['inputs']:
                    gaps.append('CLIENT_IDENTITY_DEPENDENCY_NOT_DECLARED')
            require(len(skill_versions) == 1 and len(scopes) == 1, 'ambiguous_skill_or_scope')
            skill = indexed['skills'].get((rid, next(iter(skill_versions))))
            require(skill is not None and set(skill['function_refs']) == set(refs) and bool(skill['completion_ports']),
                    'mapping_skill_completion')
            completions = copy.deepcopy(skill['completion_ports'])
            gaps.append('NO_APPROVED_DEPLOYMENT_BINDING')
        else:
            require(s.catalog_status == 'PROPOSED' and not refs and bool(suggestions)
                    and row['requires_claim_or_workflow_definition'] is True, 'invalid_composite_mapping')
            gaps.append('WORKFLOW_OR_CLAIM_REQUIRED')
            if len(scopes)>1:
                gaps.append('CROSS_SCOPE_AGGREGATION_REQUIRED')
        rows.append({'skill_id':sid, 'catalog_skill_id':rid, 'domain':s.domain, 'mode':mode,
                     'declared_functions':{fid:versions[fid]['version'] for fid in refs},
                     'legacy_function_references':legacy_refs, 'suggested_functions':list(suggestions),
                     'evidence_scopes':scopes, 'completion_ports':completions, 'gaps':sorted(set(gaps))})
    require(owners == set(versions), 'unmapped_proposal_function')
    require({sid for sid,_ in indexed['skills']} == {r['catalog_skill_id'] for r in rows if r['mode']=='PROPOSED_READ_METADATA'},
            'unmapped_proposal_skill')
    return rows


def _validate_profile(profile: dict, bundle: dict, rows: list[dict]) -> dict:
    """Return selected metadata, never a runtime/approved binding."""
    _json_value(profile)
    fields = {'format','profile_id','version','domain','scope','backend','skill_refs','selection',
              'contract_digests','source_bundle_digest','edge_policy','target_policy'}
    require(type(profile) is dict and set(profile) == fields and profile['format'] == 'gateway-lm.skill-profile/v1', 'profile_fields')
    require(Draft202012Validator(_SCHEMA['$defs']['id']).is_valid(profile['profile_id'])
            and Draft202012Validator(_SCHEMA['$defs']['version']).is_valid(profile['version']), 'profile_identity')
    require(profile['backend'] == {'backend_id':'expansion.synthetic_replay', 'revision':'0.2.0',
                                   'source':'synthetic_replay/skill_expansion_v2', 'synthetic_only':True} and profile['backend']['synthetic_only'] is True, 'profile_backend')
    require(profile['target_policy'] == {'scope':profile['scope'], 'target_id_prefix':'synthetic-',
                                         'environment':'EXPLICIT_TRUSTED_CONTEXT_REQUIRED'}, 'profile_target_policy')
    require(profile['edge_policy'] == 'TYPED_CONTRACTS_ONLY', 'unapproved_graph_policy')
    indexed = validate_catalog(bundle['catalog'], bundle['policy'])
    validate_contract(profile['selection'])
    selected = select_catalog(profile['selection'], indexed)
    validate_catalog(selected, bundle['policy'])
    functions, ports, skills = selected['functions'], selected['ports'], selected['skills']
    require(all(f['scope'] == profile['scope'] for f in functions)
            and all(p['scope'] == profile['scope'] for p in ports), 'profile_scope_mismatch')
    require(all(p['provenance'] == 'synthetic_replay/' for p in ports), 'profile_source_mismatch')
    require(all(f['lifecycle'] == 'PROPOSED' for f in functions), 'profile_proposal_only')
    refs = profile['skill_refs']
    require(type(refs) is dict and bool(refs) and all(type(r) is dict and set(r)=={'skill_id','version'}
                and type(r['skill_id']) is str and type(r['version']) is str for r in refs.values()), 'profile_skill_refs')
    resolved = {r['skill_id']:r for r in rows}
    require(set(refs) <= set(resolved), 'unknown_profile_skill')
    require({ref['skill_id'] for ref in refs.values()} <= {s['skill_id'] for s in skills}, 'profile_skill_selection')
    selected_functions = {f['function_id'] for f in functions}
    required_functions = set()
    for sid, ref in refs.items():
        row = resolved[sid]
        require(row['mode'] == 'PROPOSED_READ_METADATA' and row['domain'] == profile['domain'], 'profile_domain_or_mode')
        require(set(ref) == {'skill_id','version'} and ref['skill_id'] == row['catalog_skill_id']
                and (ref['skill_id'],ref['version']) in indexed['skills'], 'profile_skill_version')
        require('CLIENT_IDENTITY_DEPENDENCY_NOT_DECLARED' not in row['gaps'], 'profile_identity_unresolved')
        required_functions.update(row['declared_functions'])
    # Dependencies may cross domain, but never scope. The builder verifies exact refs.
    indexes = build_indexes(functions)
    from ..command_catalog.indexes import dependency_closure
    require(set(dependency_closure(indexes, required_functions)) == selected_functions, 'extraneous_profile_function')
    pins = {group:{r[key]+'@'+r['version']:digest(r) for r in selected[group]} for group,key in GROUP_KEYS.items()}
    require(profile['contract_digests'] == pins, 'profile_contract_digest')
    require(profile['source_bundle_digest'] == bundle_digest(bundle), 'profile_source_drift')
    return selected


def validate_profile(profile: dict, bundle: dict) -> dict:
    return _validate_profile(profile, bundle, audit_mappings(bundle))


def coverage_report(profile: dict, bundle: dict) -> dict:
    rows = audit_mappings(bundle)
    selected = _validate_profile(profile, bundle, rows)
    selected_ids = set(profile['skill_refs'])
    for row in rows:
        row['selected_for_cat02'] = row['skill_id'] in selected_ids
    edge_rows = []
    mapping = {row['skill_id']:row for row in rows}
    functions = {f['function_id']:f for f in bundle['catalog']['functions']}
    for edge in bundle['design'].relations:
        if edge.status != 'PROPOSED':
            continue
        producer, consumer = (edge.target, edge.source) if edge.type == 'depends_on' else (edge.source, edge.target)
        witnesses = []
        if edge.type in {'produces_for','depends_on'}:
            for p in mapping[producer]['declared_functions']:
                for c in mapping[consumer]['declared_functions']:
                    if functions[p]['scope'] == functions[c]['scope']:
                        for pid, version in functions[p]['outputs'].items():
                            if functions[c]['inputs'].get(pid) == version:
                                witnesses.append({'producer':p,'consumer':c,'port_id':pid,'version':version})
        edge_rows.append({'source':edge.source, 'target':edge.target, 'type':edge.type,
                          'decision':'NOT_APPLIED', 'runtime_approved':False, 'typed_witnesses':witnesses,
                          'reason':('TYPED_WITNESS_REQUIRES_REVIEW' if witnesses else 'NO_TYPED_WITNESS')
                                   if edge.type in {'produces_for','depends_on'} else 'DISCOVERY_OR_WORKFLOW_PROPOSAL_ONLY'})
    return {'protocol':'skill-profile-coverage/v1', 'profile_id':profile['profile_id'],
            'source_bundle_digest':profile['source_bundle_digest'], 'execution_enabled':False,
            'coverage':{'declared_skills':len(rows), 'legacy_references':sum(r['mode']=='LEGACY_DISCOVER_FROM_REPO' for r in rows),
                        'direct_read_proposals':sum(r['mode']=='PROPOSED_READ_METADATA' for r in rows),
                        'composite_without_direct_function':sum(r['mode']=='NO_DIRECT_READ_FUNCTION' for r in rows),
                        'selected_skills':len(selected_ids), 'selected_functions':len(selected['functions']),
                        'selected_ports':len(selected['ports']), 'runtime_bindings':0,
                        'current_profile_replay_verified':0, 'current_profile_live_verified':0},
            'selected_completion_ports':{s['skill_id']:s['completion_ports'] for s in selected['skills']},
            'gap_counts':dict(sorted(Counter(g for r in rows for g in r['gaps']).items())),
            'dependency_indexes':build_indexes(selected['functions']), 'mapping_rows':rows,
            'edge_reviews':edge_rows,
            'limitations':['Metadata selection only; CAT-02 must review deployment and bindings.',
                           'Historical individual synthetic smokes do not attest this profile.',
                           'No proposed graph edge is applied to execution.']}


def build_profile(profile: dict, bundle: dict, output: Path) -> tuple[dict, dict]:
    report = coverage_report(profile, bundle)
    artifact = build_registry(bundle['catalog'], profile['selection'], bundle['policy'], output)
    report['artifact_content_digest'] = artifact['content_digest']
    return artifact, report
