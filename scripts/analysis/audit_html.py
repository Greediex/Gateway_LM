"""Extract the supplied Gateway HTML catalog and link verified replay coverage to code."""

import argparse
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path

from gateway_pilot.core import ROOT


WORKFLOW_CODE = {
    "WF-018": ("workflow.py", "internet_workflow"),
    "WF-023": ("workflow.py", "dns_workflow"),
    "WF-024": ("workflow.py", "dhcp_workflow"),
    "WF-031": ("operations.py", "apply_qos"),
    "WF-039": ("workflow.py", "system_workflow"),
    "WF-047": ("lifecycle.py", "preflight_artifact"),
    "WF-054": ("monitor.py", "monitor_window"),
    "WF-063": ("operations.py", "tick"),
    "WF-066": ("workflow.py", "diagnose"),
    "WF-067": ("context.py", "retrieve_context"),
    "WF-068": ("orchestrator.py", "run_plan"),
    "WF-069": ("rag.py", "explain"),
    "WF-081": ("lifecycle.py", "preflight_artifact"),
}
REPLAY_REQUIREMENTS = {
    "F076": ("operations.py", "apply_qos"),
    "F077": ("operations.py", "apply_qos"),
    "F160": ("operations.py", "tick"),
    "F162": ("operations.py", "cancel"),
}
PARTIAL_REQUIREMENTS = {
    **{key: WORKFLOW_CODE["WF-018"] for key in ("F040", "F041", "F042", "F043")},
    **{key: WORKFLOW_CODE["WF-023"] for key in ("F054", "F055", "F056")},
    **{key: WORKFLOW_CODE["WF-024"] for key in ("F060", "F061", "F062", "F065")},
    **{key: WORKFLOW_CODE["WF-039"] for key in ("F093", "F095", "F096")},
    **{key: WORKFLOW_CODE["WF-054"] for key in ("F138", "F139", "F140")},
    **{key: WORKFLOW_CODE["WF-066"] for key in ("F171", "F172", "F174")},
    **{key: WORKFLOW_CODE["WF-067"] for key in ("F175", "F176", "F177")},
    **{key: WORKFLOW_CODE["WF-068"] for key in ("F178", "F179", "F180")},
    **{key: WORKFLOW_CODE["WF-069"] for key in ("F181", "F182", "F183")},
    "F119": WORKFLOW_CODE["WF-047"],
    "F224": WORKFLOW_CODE["WF-081"],
}
INTEGRATION_CODE = {
    "IT-01": ("operations.py", "apply_qos"),
    "IT-02": ("operations.py", "tick"),
    "IT-09": ("monitor.py", "monitor_window"),
    "IT-08": ("lifecycle.py", "preflight_artifact"),
}
PHASE_CODE = {
    "P1": ("core.py", "bind_and_gate"),
    "P2": ("workflow.py", "diagnose"),
    "P3": ("operations.py", "apply_qos"),
    "P4": ("monitor.py", "monitor_window"),
    "P5": ("lifecycle.py", "preflight_artifact"),
}
SKILL_CODE = {
    "SK01": ("workflow.py", "match_device"),
    "SK02": WORKFLOW_CODE["WF-018"],
    "SK03": WORKFLOW_CODE["WF-024"],
    "SK04": ("workflow.py", "wan"),
    "SK05": WORKFLOW_CODE["WF-023"],
    "SK06": ("operations.py", "verify_qos"),
    "SK08": WORKFLOW_CODE["WF-039"],
    "SK09": ("state.py", "usable"),
    "SK10": ("workflow.py", "order_probes"),
    "SK11": WORKFLOW_CODE["WF-069"],
    "SK12": ("operations.py", "plan_qos"),
    "SK13": WORKFLOW_CODE["WF-031"],
    "SK14": WORKFLOW_CODE["WF-063"],
    "SK15": WORKFLOW_CODE["WF-054"],
    "SK17": WORKFLOW_CODE["WF-047"],
}


def plain(text):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def catalog(path):
    raw = path.read_text(encoding="utf-8")
    data = {"source": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "workflows": {}, "requirements": {}, "skills": {}, "phases": {}, "integration": {}}

    def line(match):
        return raw.count("\n", 0, match.start()) + 1

    for match in re.finditer(r'<details\b[^>]*class="case-entry"[^>]*data-search="([^"]+)"', raw):
        fields = html.unescape(match[1])
        uc, workflow, rest = fields.split(" ", 2)
        data["workflows"][workflow] = {
            "uc": uc, "title": re.split(r"\bF\d{3}\b", rest, maxsplit=1)[0].strip(),
            "requirements": sorted(set(re.findall(r"\bF\d{3}\b", rest))),
            "skills": sorted(set(re.findall(r"\bSK\d{2}\b", rest))),
            "line": line(match),
        }
    for section, pattern in (
        ("requirements", r"<tr><td>(F\d{3})</td><td>(.*?)</td>"),
        ("skills", r'id="canonical-(SK\d{2})"><b>SK\d{2}\s*·\s*(.*?)</b>'),
        ("phases", r'<article class="phase-card"><h3><span>(P[0-7])</span>(.*?)</h3>'),
        ("integration", r"<tr><td>(IT-\d{2})</td><td>(.*?)</td>"),
    ):
        for match in re.finditer(pattern, raw, re.S):
            data[section][match[1]] = {"title": plain(match[2]), "line": line(match)}

    expected_ids = {
        "workflows": {f"WF-{i:03}" for i in range(1, 102)},
        "skills": {f"SK{i:02}" for i in range(1, 23)},
        "phases": {f"P{i}" for i in range(8)},
        "integration": {f"IT-{i:02}" for i in range(1, 11)},
    }
    for section, expected in expected_ids.items():
        if data[section].keys() != expected:
            raise ValueError(f"Unexpected HTML catalog IDs in {section}")
    if {row["uc"] for row in data["workflows"].values()} != {f"UC-{i:03}" for i in range(1, 102)}:
        raise ValueError("Unexpected use case IDs")
    expected_requirements = {f"F{i:03}" for i in range(1, 271)}
    if not data["requirements"] or not data["requirements"].keys() <= expected_requirements:
        raise ValueError("Unexpected requirement IDs")
    data["missing_requirement_ids"] = sorted(expected_requirements - data["requirements"].keys())
    data["workflows_without_requirement_ids"] = sorted(
        key for key, row in data["workflows"].items() if not row["requirements"])
    for row in data["workflows"].values():
        if (not set(row["requirements"]) <= data["requirements"].keys()
                or not set(row["skills"]) <= data["skills"].keys()):
            raise ValueError(f"Broken reference in {row['uc']}")
    return data


def annotate(data):
    for key, row in data["workflows"].items():
        row["coverage"] = "partial_replay" if key in WORKFLOW_CODE else "unmapped"
        if key in WORKFLOW_CODE:
            row["runtime"] = WORKFLOW_CODE[key]
    for key, row in data["requirements"].items():
        if key in REPLAY_REQUIREMENTS:
            row.update(coverage="tested_replay", runtime=REPLAY_REQUIREMENTS[key])
        elif key in PARTIAL_REQUIREMENTS:
            row.update(coverage="partial_replay", runtime=PARTIAL_REQUIREMENTS[key])
        else:
            row["coverage"] = "unmapped"
    for section, mapping in (("integration", INTEGRATION_CODE), ("phases", PHASE_CODE), ("skills", SKILL_CODE)):
        for key, row in data[section].items():
            row["coverage"] = "partial_replay" if key in mapping else "unmapped"
            if key in mapping:
                row["runtime"] = mapping[key]


def render_report(data):
    workflows = Counter(row["coverage"] for row in data["workflows"].values())
    functions = Counter(row["coverage"] for row in data["requirements"].values())
    lines = [
        "# Đối chiếu HTML Gateway LM với pilot",
        "",
        f"Nguồn HTML có 101 UC, 101 workflow, 22 skill, 8 pha và 10 ca tích hợp.",
        f"Trong dải 270 mã F, HTML liệt kê {len(data['requirements'])} hạng mục.",
        "Các mã vắng mặt gồm " + ", ".join(data["missing_requirement_ids"]) + ".",
        "Các workflow không có ID hạng mục trực tiếp gồm "
        + ", ".join(data["workflows_without_requirement_ids"]) + ".",
        f"SHA-256 `{data['sha256']}`.",
        "",
        f"- Workflow có lát cắt replay **{workflows['partial_replay']}/101**.",
        f"- Skill có ánh xạ một phần **{len(SKILL_CODE)}/22**. "
        f"Pha **{len(PHASE_CODE)}/8** và ca tích hợp **{len(INTEGRATION_CODE)}/10** có lát cắt replay.",
        f"- Hạng mục có test replay trực tiếp **{functions['tested_replay']}**, có một phần "
        f"**{functions['partial_replay']}**, chưa ánh xạ **{functions['unmapped']}**.",
        "- Trạng thái replay giới hạn ở code và fixture. Xem điều kiện đầy đủ trong HTML.",
        "",
        "| Workflow | Đường chạy | Phạm vi còn thiếu |",
        "|---|---|---|",
        "| WF-018 | Chẩn đoán Internet từ client | Adapter OpenWrt và phép đo thật |",
        "| WF-023 | Kiểm DNS theo scope | Cửa sổ độ trễ, upstream và cache |",
        "| WF-024 | Lease, pool, dịch vụ DHCP | Chuỗi DORA và trùng IP từ sự kiện |",
        "| WF-031 | QoS có duyệt, version, hậu kiểm và phục hồi replay | Policy chồng lấn, dataplane và thiết bị thật |",
        "| WF-039 | CPU, RAM và dung lượng tức thời | Nhiệt độ, filesystem, OOM và diễn biến theo thời gian |",
        "| WF-054 | Cảnh báo ngưỡng theo cửa sổ | Collector thật và mô hình dự báo đã hiệu chuẩn |",
        "| WF-063 | Lịch một lần, lưu bền, recheck quyền, hết hạn và hủy | Rule firewall thật và profile tái diễn |",
        "| WF-066–WF-068 | Chọn intent, hỏi lại target, kiểm dependency, lập lịch node | Đa ý định, tham chiếu qua lượt và hủy case đang chạy |",
        "| WF-069 | Tra runbook đúng profile replay, nguồn tài liệu và evidence đo tách riêng | Corpus được xác minh theo firmware thật |",
        "| WF-047 / WF-081 | Preflight manifest, chữ ký qua verifier, digest, version, dung lượng và recovery | Trust root, staging, canary và phục hồi trên nền tảng đích |",
        "",
        "Dữ liệu từng mục nằm trong [catalog.json](catalog.json). Graphify nối ID đặc tả với "
        "symbol đã trích xuất từ mã nguồn. Các cạnh ánh xạ do audit khai báo.",
    ]
    return "\n".join(lines) + "\n"


def graphify_catalog(data, output):
    from graphify.analyze import god_nodes, suggest_questions, surprising_connections
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.detect import detect
    from graphify.diagnostics import diagnose_extraction
    from graphify.export import to_html, to_json
    from graphify.extract import extract
    from graphify.report import generate

    root = ROOT / "gateway_pilot"
    detected = detect(root)
    if detected["total_files"] > 500 or detected["total_words"] > 2_000_000:
        raise ValueError("Graphify corpus exceeds scoped extraction budget")
    raw = extract([Path(path) for path in detected["files"]["code"]], root=root, parallel=False)
    symbols = {}
    for node in raw["nodes"]:
        name = node.get("label", "").lstrip(".").removesuffix("()")
        symbols[Path(node.get("source_file") or "").name, name] = node["id"]
    source = data["source"]

    def add_node(key, title, line):
        raw["nodes"].append({"id": key, "label": f"{key} {title}", "file_type": "document",
                             "source_file": source, "source_location": f"L{line}"})

    def add_edge(src, dst, kind, line):
        raw["edges"].append({"source": src, "target": dst, "relation": kind,
                             "confidence": "EXTRACTED", "confidence_score": 1.0,
                             "source_file": source, "source_location": f"L{line}"})

    for section in ("workflows", "requirements", "skills", "phases", "integration"):
        for key, row in data[section].items():
            add_node(key, row["title"], row["line"])
            if row.get("runtime"):
                target = symbols.get(tuple(row["runtime"]))
                if target is None:
                    raise ValueError(f"Missing code symbol for {key}: {row['runtime']}")
                add_edge(key, target, "mapped_to_replay", row["line"])
            if section == "workflows":
                add_node(row["uc"], row["title"], row["line"])
                add_edge(row["uc"], key, "specifies", row["line"])
                for member in row["requirements"] + row["skills"]:
                    add_edge(key, member, "requires", row["line"])

    graph = build_from_json(raw, root=str(root), directed=True)
    communities = cluster(graph)
    labels = {}
    for group, members in communities.items():
        dominant = Counter(Path(graph.nodes[node].get("source_file") or "").name for node in members)
        label = dominant.most_common(1)[0][0]
        labels[group] = f"HTML catalog {group}" if label.endswith(".html") else label or f"Group {group}"
    output.mkdir()
    assert to_json(graph, communities, str(output / "graph.json"), community_labels=labels)
    to_html(graph, communities, str(output / "graph.html"), community_labels=labels)
    health = diagnose_extraction(raw, directed=True, root=str(root))
    audit = {name: health[name] for name in ("dangling_endpoint_edges", "missing_endpoint_edges",
                                            "self_loop_edges", "directed_same_endpoint_collapsed_edges")}
    report = generate(graph, communities, score_all(graph, communities), labels, god_nodes(graph),
                      surprising_connections(graph, communities), detected, {"input": 0, "output": 0},
                      str(root), suggested_questions=suggest_questions(graph, communities, labels))
    (output / "GRAPH_REPORT.md").write_text(
        report + "\n## Extraction health\n\n" + json.dumps(audit) + "\n", encoding="utf-8")
    return {"code_files": len(detected["files"]["code"]), "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(), "ast_tokens": 0, "health": audit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--graphify", action="store_true")
    args = parser.parse_args()
    data = catalog(args.html)
    annotate(data)
    args.output.mkdir(parents=True)
    if args.graphify:
        data["graphify"] = graphify_catalog(data, args.output / "graphify-out")
    (args.output / "catalog.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "HTML_IMPLEMENTATION_MAP.md").write_text(render_report(data), encoding="utf-8")
    print(json.dumps({key: len(data[key]) for key in ("workflows", "requirements", "skills", "phases", "integration")}))
    print(json.dumps({"missing_requirement_ids": data["missing_requirement_ids"],
                      "workflows_without_requirement_ids": data["workflows_without_requirement_ids"]}))
    if args.graphify:
        print(json.dumps(data["graphify"]))


if __name__ == "__main__":
    main()
