"""Validate proposal metadata using the actual Gateway_LM v2 catalog validator.

Run INSIDE the v2 checkout after non-destructive installation. Valid metadata
is NOT runtime permission, binding approval or firmware conformance.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def validate():
    from gateway_pilot.command_catalog.loader import load_catalog
    from gateway_pilot.command_catalog.validator import validate_catalog
    from gateway_pilot.command_catalog.builder import build_registry
    from tempfile import TemporaryDirectory
    source=ROOT/'proposed_catalog_v02'
    catalog=load_catalog(source)
    policy={'schema_version':'0.2.0',
            'allowed_probe_ids':sorted({f['capability_probe'] for f in catalog['functions']})}
    validate_catalog(catalog,policy)
    selection={'schema_version':'0.2.0','kind':'selection',
               'functions':{f['function_id']:f['version'] for f in catalog['functions']},
               'ports':{p['port_id']:p['version'] for p in catalog['ports']}}
    with TemporaryDirectory(prefix='gateway-skill-proposal-') as tmp:
        artifact=build_registry(catalog,selection,policy,Path(tmp)/'registry.json')
    return {'contracts_valid':True,'functions':len(catalog['functions']),
            'ports':len(catalog['ports']),'skills':len(catalog['skills']),
            'artifact_content_digest':artifact['content_digest'],
            'execution_enabled':False,'operator_approved':False}

if __name__=='__main__':
    try:print(json.dumps(validate(),indent=2))
    except ImportError as e:sys.exit('Run in actual Gateway_LM v2 checkout: '+str(e))
