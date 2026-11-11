"""GATEWAY_DESIGN: evidence-grounded Answer Composer (C3, G20).

Every turn leaves as one structure with an explicit grounding. Diagnostic text
is built from the concluded claim's message plus verified facts, each with the
measurement point and time; without evidence there are no numbers. A PARTIAL
answer always names what was not verified. An optional LLM may only rephrase
the selected claims, facts and documents: any number or diagnosis code in its
text that is not in that input rejects the LLM text and the template is used.
"""
from __future__ import annotations

import json
import re

from .rag import DEFAULT_CATALOG, RunbookIndex, lexical_scores

GROUNDINGS = ("EVIDENCE", "DOCS", "CATALOG", "NONE")
SCOPE_TEXT = {"gateway": "đo tại router", "client": "đo tại thiết bị"}
NO_GROUNDING_NOTE = "Lưu ý: câu trả lời này không dựa trên phép đo hay tài liệu của thiết bị."
FACT_LABELS = {
    "router_wan_link": "liên kết WAN của router", "router_default_route": "tuyến mặc định của router",
    "router_wan_reachable": "kết nối ra ngoài từ router", "router_dns_works": "DNS tại router",
    "router_dhcp_running": "dịch vụ DHCP", "router_dhcp_pool_available": "dải địa chỉ DHCP",
    "router_memory_ok": "RAM của router", "router_cpu_ok": "CPU của router", "router_storage_ok": "bộ nhớ lưu trữ",
    "client_identified": "định danh thiết bị", "client_ip_configured": "địa chỉ IP của thiết bị",
    "client_wifi_associated": "kết nối Wi-Fi của thiết bị", "client_lease_valid": "lease DHCP của thiết bị",
    "client_internet_reachable": "kết nối Internet từ chính thiết bị", "client_dns_works": "DNS từ chính thiết bị",
}
NUMBER = re.compile(r"(?<![A-Za-z0-9-])-?\d+(?:[.,]\d+)?")  # digits inside identifiers (SK22) are not numbers
CODE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")
IDENT = re.compile(r"\b[A-Z]{1,3}-?\d{2,3}\b")  # SK22, WF-018, F002


def _evidence_line(e):
    value = json.dumps(e.get("value"), ensure_ascii=False)
    return (f"• {e['port']}: {value} ({SCOPE_TEXT.get(e.get('scope'), 'phạm vi ' + str(e.get('scope')))}, "
            f"lúc {e.get('observed_at', 'chưa rõ')}) [{e['id']}]")


def _nearest_topics(message, limit=3):
    try:
        docs = RunbookIndex(DEFAULT_CATALOG).docs
    except FileNotFoundError:
        return []
    scores = lexical_scores(message, {d: f"{row['title']} {row.get('keywords', '')}" for d, row in docs.items()})
    ranked = sorted(docs, key=lambda d: (-scores.get(d, 0.0), d))
    return [docs[d]["title"] for d in ranked[:limit]]


def check_llm_text(text, payload):
    """Accept LLM text only if every number and diagnosis code already appears in its input."""
    if not isinstance(text, str) or not text.strip():
        return False, "empty"
    source = json.dumps(payload, ensure_ascii=False)
    numbers = {n.replace(",", ".") for n in NUMBER.findall(source)}
    for number in NUMBER.findall(text):
        if number.replace(",", ".") not in numbers:
            return False, "number_not_in_input:" + number
    for code in (*CODE.findall(text), *IDENT.findall(text)):
        if code not in source:
            return False, "code_not_in_input:" + code
    return True, ""


def _grounding(result):
    kind, router = result["turn_type"], result.get("router") or {}
    evidence = result.get("graph", {}).get("evidence") or []
    if kind in ("DIAGNOSE", "LOOKUP", "FOLLOW_UP") and evidence:
        return "EVIDENCE"
    if kind == "KNOWLEDGE":
        return "DOCS" if router.get("documents") else "NONE"
    if kind == "CAPABILITY" or router.get("action") == "UNSUPPORTED":
        return "CATALOG"
    if router.get("action") == "ASK_USER" and any(isinstance(o, dict) for o in router.get("options", ())):
        return "CATALOG"
    return "NONE"


def compose(result, message, *, llm=None):
    """Turn the assistant's raw result into the C3 Turn structure (in place, also returned)."""
    graph, router = result.get("graph", {}), result.get("router") or {}
    terminal = result.get("terminal") or {}
    by_id = {e["id"]: e for e in graph.get("evidence", ())}
    status = result.get("case_status")
    evidence_ids = [eid for eid in terminal.get("evidence_ids", ()) if eid in by_id]
    if not evidence_ids:
        evidence_ids = [e["id"] for e in result.get("goal_facts", ()) if e.get("id") in by_id]
    contract_c = graph.get("contract_c") or {}
    lines, next_steps = [result.get("answer") or ""], []

    if evidence_ids and not result.pop("facts_listed", False):
        lines.append("Bằng chứng đã xác minh:")
        lines.extend(_evidence_line(by_id[eid]) for eid in evidence_ids)
    if status == "PARTIAL":
        missing = [FACT_LABELS.get(q, q) for q in contract_c.get("outstanding_questions", ())]
        if not missing:
            scope = (result.get("target") or {}).get("scope")
            missing = ["phần đường đi từ chính thiết bị" if scope == "client" else "phần còn lại ngoài phạm vi đã đo"]
        lines.append("Chưa xác minh: " + "; ".join(missing) + ".")
        next_steps.append("Đo thêm: " + "; ".join(missing))
    elif status == "INCONCLUSIVE" and graph.get("evidence") and not evidence_ids:
        measured = [e for e in graph["evidence"] if e.get("status") == "OK"][-4:]
        if measured:
            lines.append("Đã đo được:")
            lines.extend(_evidence_line(e) for e in measured)
            evidence_ids = [e["id"] for e in measured]
    doc_ids = [d["id"] for d in router.get("documents", ())] if result["turn_type"] == "KNOWLEDGE" else []
    if result["turn_type"] == "KNOWLEDGE" and not doc_ids:
        topics = _nearest_topics(message)
        if topics:
            lines.append("Chủ đề gần nhất hiện có: " + "; ".join(topics) + ".")
    options = [o["title"] if isinstance(o, dict) else o for o in router.get("options", ())]
    if status == "NEEDS_INPUT" and options:
        next_steps.append("Chọn: " + "; ".join(options))
    grounding = _grounding(result)
    answer = "\n".join(line for line in lines if line)

    llm_used, rejected = False, None
    if llm is not None:
        payload = {"turn_type": result["turn_type"], "case_status": status,
                   "claim": {"diagnosis": terminal.get("diagnosis"), "message": terminal.get("response")},
                   "facts": [by_id[eid] for eid in evidence_ids],
                   "documents": [{"id": d["id"], "text": d.get("text", "")} for d in router.get("documents", ())]}
        try:
            text = llm(payload)
        except (OSError, TimeoutError, ValueError, KeyError, TypeError) as exc:
            text, rejected = None, type(exc).__name__
        ok, reason = check_llm_text(text, payload) if text is not None else (False, rejected or "no_text")
        if ok:
            llm_used = True
            answer = text.strip()
            if status == "PARTIAL":
                answer += "\n" + next(line for line in lines if line.startswith("Chưa xác minh"))
        else:
            rejected = reason
    if result["turn_type"] == "KNOWLEDGE" and grounding == "NONE" and llm_used:
        answer += "\n" + NO_GROUNDING_NOTE

    result.update(answer=answer, grounding=grounding, evidence_ids=evidence_ids, doc_ids=doc_ids,
                  options=options, next_steps=next_steps, llm_used=llm_used,
                  contracts={"c0": (graph.get("contract_0") or [{}])[-1],
                             "a": next((p.get("contract_a") for p in reversed(graph.get("plans", ()))
                                        if p.get("contract_a")), {}),
                             "c": contract_c})
    if rejected:
        result["llm_rejected"] = rejected
    return result
