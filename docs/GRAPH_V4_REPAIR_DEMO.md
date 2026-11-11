# Demo repair graph v4 (T6)

Sinh bằng cách chạy `GraphRunner.run` trên fixture `dns_fail` với registry legacy và các Function
thay thế dựng trong test (`tests_graph_v3/test_repair_t6.py`). Mọi số là **replay tổng hợp trên host**,
không phải router thật. Demo cũ `GRAPH_V3_REPAIR_DEMO.md` giữ nguyên.

Thứ tự thử toán tử theo loại lỗi (theo bảng của bản tái lập GraSP không chính thức):

| Loại lỗi | Thứ tự |
|---|---|
| precondition | INSERT_PREREQ, REBIND, SUBSTITUTE, REWIRE, BYPASS |
| postcondition | SUBSTITUTE, REBIND, REWIRE, BYPASS, INSERT_PREREQ |
| execution | SUBSTITUTE, REBIND, REWIRE, BYPASS |
| timeout | SUBSTITUTE, BYPASS |

Giới hạn: `L_max=3` node, `E_max=5` cạnh mỗi patch; `R_max=2` lần vá mỗi node; patch chỉ chạm node
trong `h=2` bước; `P_max=1` lần GLOBAL_REPLAN cho mỗi runner, sau đó `INCOMPLETE`.

### A. Timeout ở wan.status, có producer thay thế cùng port → SUBSTITUTE cục bộ

- {"revision": 1, "operator": "COMPILE", "cost": 4.004}
- {"revision": 2, "previous_revision": 1, "operator": "SUBSTITUTE", "node": "wan.status", "failure": "timeout", "added_nodes": ["z.status.backup"], "removed_nodes": ["wan.status"], "added_edges": [{"source": "z.status.backup", "target": "wan.routes", "kind": "DATA", "port": "wan.status", "hard": true}], "removed_edges": [{"source": "wan.status", "target": "wan.routes", "kind": "DATA", "port": "wan.status", "hard": true}], "invalidated_evidence": ["e2"], "replaced": {"wan.status": "z.status.backup"}}

calls=5 repairs=1 global_replans=0 incomplete=False

### B. Mọi thay thế đều timeout → hết R_max → một GLOBAL_REPLAN → INCOMPLETE

- {"revision": 1, "operator": "COMPILE", "cost": 2.002}
- {"revision": 2, "previous_revision": 1, "operator": "SUBSTITUTE", "node": "wan.status", "failure": "timeout", "added_nodes": ["z.status.a"], "removed_nodes": ["wan.status"], "added_edges": [{"source": "z.status.a", "target": "wan.routes", "kind": "DATA", "port": "wan.status", "hard": true}], "removed_edges": [{"source": "wan.status", "target": "wan.routes", "kind": "DATA", "port": "wan.status", "hard": true}], "invalidated_evidence": ["e1"], "replaced": {"wan.status": "z.status.a"}}
- {"revision": 3, "previous_revision": 2, "operator": "SUBSTITUTE", "node": "z.status.a", "failure": "timeout", "added_nodes": ["z.status.b"], "removed_nodes": ["z.status.a"], "added_edges": [{"source": "z.status.b", "target": "wan.routes", "kind": "DATA", "port": "wan.status", "hard": true}], "removed_edges": [{"source": "z.status.a", "target": "wan.routes", "kind": "DATA", "port": "wan.status", "hard": true}], "invalidated_evidence": ["e2"], "replaced": {"z.status.a": "z.status.b"}}
- {"revision": 4, "operator": "COMPILE", "cost": 5.003}
- {"revision": 4, "operator": "GLOBAL_REPLAN", "escalated_from": "local-exhausted", "previous_revision": 3, "failed": "z.status.b", "invalidated_nodes": ["wan.routes", "z.status.b"], "reused_evidence": [], "added": ["system.resources", "z.status.global"], "removed": ["z.status.b"]}
- {"revision": 4, "operator": "INCOMPLETE", "node": "z.status.global", "escalated_from": "local-failed"}

calls=5 repairs=3 global_replans=1 incomplete=True

### C. Bằng chứng tiền đề bị vô hiệu → precondition → INSERT_PREREQ

- {"revision": 1, "operator": "COMPILE", "cost": 1.001}
- {"revision": 2, "previous_revision": 1, "operator": "INSERT_PREREQ", "node": "wan.probe", "failure": "precondition", "added_nodes": ["wan.routes"], "removed_nodes": [], "added_edges": [{"source": "wan.routes", "target": "wan.probe", "kind": "DATA", "port": "wan.routes", "hard": true}], "removed_edges": [], "invalidated_evidence": []}

calls=2 repairs=1 global_replans=0 incomplete=False
