# Demo repair từ trace thực của replay

Timeout ở đây được điều khiển bằng fixture, không phải phép đo trên router thật.

## Plan revision 1

```mermaid
flowchart LR
  n0["dns.config / SUCCEEDED"]
  n1["dns.probe / SUCCEEDED"]
  n2["wan.status / FAILED"]
  n3["wan.routes / BLOCKED"]
  n0 -->|DATA| n1
  n2 -->|DATA| n3
```

## Plan revision 2

```mermaid
flowchart LR
  n0["wan.status.backup / SUCCEEDED"]
  n1["wan.routes / SUCCEEDED"]
  n2["dns.config / SUCCEEDED"]
  n3["dns.probe / SUCCEEDED"]
  n0 -->|DATA| n1
```

Revision 2 thay WAN status bằng backup, giữ DNS đã xác minh; chi tiết binding/evidence/audit diff nằm trong `../runs/graph_v3_structural_final/repair_demo.json`.
