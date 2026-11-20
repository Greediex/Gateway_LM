"""Pinned handover data and the separate five-Skill replay catalog."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from ..adapters.bindings import require
from ..command_catalog.loader import read_json
from ..core import ROOT

VENDOR = ROOT / 'vendor/igate_handover_20261120'
CATALOG = ROOT / 'config/skill_launcher/replay_sim.igate.json'
SCENARIOS = ROOT / 'data/igate_sim_v1'
DOMAIN = 'igate'
KIND = 'igate_simulated'


def vendor_data(folder: Path = VENDOR) -> tuple[dict, dict[str, bytes]]:
    path = folder / 'PROVENANCE.json'
    manifest = read_json(path)
    files = manifest['files']
    present = {item.relative_to(folder).as_posix() for item in folder.rglob('*') if item.is_file()}
    require(present == (set(files) | {path.name}), 'skill_sim_igate_vendor_membership')
    contents = {}
    for name, row in files.items():
        item = folder / name
        require(not item.is_symlink() and item.resolve().is_relative_to(folder.resolve()),
                'skill_sim_igate_vendor_path')
        contents[name] = item.read_bytes()
        require(sha256(contents[name]).hexdigest() == row['vendored_sha256'], 'skill_sim_igate_vendor_pin')
        require('sanitization' in row or row['source_sha256'] == row['vendored_sha256'],
                'skill_sim_igate_vendor_source_pin')
    return manifest, contents


def catalog() -> dict:
    doc = read_json(CATALOG)
    require(doc['format'] == 'gateway-lm.replay-sim-igate/v1', 'skill_sim_igate_catalog_format')
    return doc['skills']


def function_id(sid: str) -> str:
    return DOMAIN + '.' + sid.lower()


def action(sid: str, row: dict) -> dict:
    return {'skill_id': sid, 'name': row['name'], 'domain': DOMAIN, 'kind': KIND,
            'scope': 'gateway', 'required_ports': {function_id(sid): '1.0.0'}, 'optional_ports': {}}
