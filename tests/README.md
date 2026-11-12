# Regression tests

Run from the repository root with Python 3.12 after `python setup_upstream.py`.

```bash
python -m unittest discover -s tests -v
```

The single command discovers all tests (legacy, Graph and Web) because the nested suites are Python packages.

Focused checks:

```bash
python -m unittest tests.graph_v3.test_composite_adapter -v
python -m unittest discover -s tests/graph_v3 -v
python -m unittest discover -s tests/web -v
```

- `test_native.py`, `test_pilot.py`: baseline and legacy compatibility.
- `graph_v3/`: Registry, DAG, planning, evidence, replay and adapters.
- `web/`: HTTP adapter, dynamic/Core and Windows live (Windows-only tests skip elsewhere).

Avoid modifying frozen benchmark fixtures simply to satisfy tests. See [Developer Guide](../docs/DEVELOPER_GUIDE.md).
