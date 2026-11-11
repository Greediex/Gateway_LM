"""Generate outcome/failure analysis after a completed run, without model calls."""
import argparse
import json
from collections import Counter
from pathlib import Path

from gateway_pilot.core import ROOT, Registry, new_state, read_json, support


def pct(n, d):
    return f"{n}/{d} ({n / d:.1%})" if d else "0/0"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    a = p.parse_args()
    meta = json.loads((a.run / "metadata.json").read_text(encoding="utf-8"))
    if not meta.get("finished_at"):
        p.error("Wait for run completion before writing conclusions")
    records = [json.loads(x) for x in (a.run / "episodes.jsonl").read_text(encoding="utf-8").splitlines()]
    summary = json.loads((a.run / "summary.json").read_text(encoding="utf-8"))
    unique = {r["case_id"]: r for r in records}
    registry = Registry()
    case_by_id = {c["id"]: c for c in read_json(ROOT / "data/cases.json")}
    supported_correct = {}
    for row in records:
        case = case_by_id[row["case_id"]]
        available = len(case.get("initial_evidence", []))
        found = False
        for step in row["trace"]:
            if step.get("phase") == "core_graph_acquisition":
                available = len(row["evidence"])
            decision = step.get("decision") or {}
            if not isinstance(decision, dict):
                decision = {}
            if (row["gold"]["action"] == "FINISH" and decision.get("action") == "FINISH"
                    and decision.get("diagnosis") == row["gold"]["diagnosis"]):
                state = new_state(case, registry)
                state.evidence = row["evidence"][:available]
                if support(decision["diagnosis"], state, case)[0]:
                    found = True
            available = step.get("evidence_after", available)
        supported_correct[(row["case_id"], row["arm"])] = found
    constant_abstain = sum(r["gold"] == {"action": "INCOMPLETE", "diagnosis": "insufficient_evidence"} for r in unique.values())
    lines = ["# Kết luận thực nghiệm Gateway LM v0.1", "",
             f"Chạy hoàn tất {len(records)} episode trên {len(unique)} ca test synthetic; model `{meta['model']}`.",
             f"Actual artifact parameter count: {meta['model_metadata']['parameter_count']:,}; quantization {meta['model_metadata']['details']['quantization_level']}.",
             "", "## Phân biệt chẩn đoán được và cần dừng/hỏi lại", "",
             "| Arm | Đúng tổng | Ca đủ dữ liệu để kết luận | Ca cần hỏi/dừng | Việt | Anh |",
             "|---|---:|---:|---:|---:|---:|"]
    breakdown = {}
    for arm in summary["arms"]:
        group = [r for r in records if r["arm"] == arm]
        subsets = {"answerable": [r for r in group if r["gold"]["action"] == "FINISH"],
                   "abstention": [r for r in group if r["gold"]["action"] != "FINISH"],
                   "vi": [r for r in group if r["case_id"].endswith("-1")],
                   "en": [r for r in group if r["case_id"].endswith("-2")]}
        counts = {name: {"n": len(rs), "success": sum(r["autonomous_success"] for r in rs)}
                  for name, rs in subsets.items()}
        breakdown[arm] = counts
        vals = [pct(sum(r["autonomous_success"] for r in group), len(group))]
        vals += [pct(counts[k]["success"], counts[k]["n"]) for k in ("answerable", "abstention", "vi", "en")]
        lines.append("| " + arm + " | " + " | ".join(vals) + " |")
    lines += ["", f"Baseline tham chiếu luôn trả `INCOMPLETE/insufficient_evidence` sẽ khớp nhãn ở {pct(constant_abstain, len(unique))} ca. Vì vậy cần đọc riêng cột ca đủ dữ liệu, không chỉ tỷ lệ tổng.",
              "", "## Model nhận đúng nguyên nhân nhưng vướng contract citation?", "",
              "Bảng dưới chỉ xét ca gold là FINISH: có ít nhất một đề xuất FINISH đúng nhãn và đã có fact hỗ trợ ở đúng thời điểm, tạm bỏ qua citation/shape validation. Đây là phép phân tích lỗi, không thay metric thành công chính.",
              "", "| Arm | Từng đề xuất đúng nhãn và đủ fact |", "|---|---:|"]
    for arm in summary["arms"]:
        answerable = [r for r in records if r["arm"] == arm and r["gold"]["action"] == "FINISH"]
        lines.append(f"| {arm} | {pct(sum(supported_correct[(r['case_id'], arm)] for r in answerable), len(answerable))} |")
    lines += [
              "", "## Điều quan sát được", ""]
    graph = summary["arms"].get("graph", {})
    batch = summary["arms"].get("graph_batch", {})
    flat = summary["arms"].get("flat", {})
    if graph and flat:
        lines.append(f"- Model tự điều phối + graph: {pct(graph['autonomous_success'], graph['n'])}; tool phẳng: {pct(flat['autonomous_success'], flat['n'])}. Graph không tự biến observation thành kết luận đúng.")
    if batch and graph:
        lines.append(f"- Core thu thập evidence bằng graph, model chỉ kết luận: {pct(batch['autonomous_success'], batch['n'])}. Đây là phân công khác với model tự chọn bước; số tool/ca có thể tăng.")
    lines.append("- Catalog coverage là phép đo cấu trúc riêng: flat 100%, BM25 top-4 khoảng 79.4%, graph 100% trên goal contracts đã khai báo. Độ phủ cao không bảo đảm model phân tích đúng hoặc biết dừng.")
    lines.append("- Policy/validator chặn đề xuất sai là hiệu quả của Core. Không cộng các lần bị chặn vào thành tích suy luận của model; Core buộc dừng cũng không tính là autonomous success.")
    lines.append("- Metric chính đòi hỏi nhãn nguyên nhân chuẩn của fixture. Một nhãn triệu chứng như mất gói có thể được validator chấp nhận nhưng vẫn chưa đạt nếu nguyên nhân cụ thể trong ca là không có default route. Xem trace thay vì đồng nhất mọi nhãn lệch gold với số đo bịa.")
    if meta.get("interface", "").startswith("native"):
        lines.append("- Native follow-up được thiết kế sau khi xem v1 và dùng tool/argument schema cùng enum diagnosis. Không phải holdout mù mới; không xác lập trần năng lực model <3B hoặc tách riêng tác động của native serialization khỏi schema/prompt.")
    else:
        lines.append("- Đây là giới hạn của cấu hình v1, chưa phải trần năng lực của mọi model <3B. v1 không dùng native tool-calling hoặc grammar ép action/label. Catalog v1 expose prerequisite/port và hướng dẫn Core bind args, chưa expose JSON Schema argument đầy đủ cho model. Xem native follow-up riêng nếu có; không gộp kết quả.")
    lines += ["", "## Lỗi thực tế theo arm", ""]
    error_counts = {}
    for arm in summary["arms"]:
        group = [r for r in records if r["arm"] == arm]
        errors = Counter(e for r in group for e in r["raw_rejections"])
        error_counts[arm] = dict(errors)
        lines.append(f"- **{arm}**: " + (", ".join(f"`{k}` × {v}" for k, v in errors.most_common(8)) or "không có đề xuất bị chặn") + ".")
    lines += ["", "## Dấu vết để xem trực tiếp", ""]
    selected = []
    for arm in ("graph_batch", "graph", "flat", "rules"):
        group = [r for r in records if r["arm"] == arm]
        success = next((r for r in group if r["autonomous_success"] and r["gold"]["action"] == "FINISH"), None)
        failure = next((r for r in group if not r["autonomous_success"] and r["gold"]["action"] == "FINISH"), None)
        for r in (success, failure):
            if not r:
                continue
            selected.append({k: r[k] for k in ("case_id", "arm", "gold", "terminal", "autonomous_success", "raw_rejections", "executed", "evidence", "trace")})
            lines.append(f"- `{r['case_id']}` / `{arm}`: gold `{r['gold']['action']}/{r['gold']['diagnosis']}`, nhận `{r['terminal']['action']}/{r['terminal']['diagnosis']}`, tự hoàn tất đúng={r['autonomous_success']}.")
    lines += ["", "```powershell", f"python inspect_case.py {a.run.as_posix()} --case GLM-01-1 --arm graph_batch", "```", "",
              "## Hướng dùng trong dự án", "",
              "1. Với bốn workflow xác định WAN/DNS/DHCP/sức khỏe, giữ Fastpath/luật làm nền và dùng graph/contract để kiểm tra dependency, scope, capability và evidence.",
              "2. Chưa giao model nhỏ quyền tự điều phối hoàn toàn. Dùng model ở vai trò analyst/advisor có validator; chỉ giữ phần nào vượt baseline trên dữ liệu mới.",
              "   Một hướng kỹ thuật cần thử riêng là Core tạo proof bundle từ verifier khi nhãn model đã được fact hỗ trợ, để giảm việc LLM phải tự liệt kê mọi evidence ID. Vẫn lưu raw proposal và chấm riêng citation do model/Core tạo; pilot này chưa triển khai hoặc tính đó là thành công.",
              "3. Trước khi mở rộng Skill, cần test capture từ firmware thật, lỗi mới không chung template, nhiều client và bằng chứng mâu thuẫn; tách intent routing và chất lượng lời giải thích thành bài đánh giá riêng.",
              "4. Repo GoS/SkillDAG/SE-GoS/SkillSeek/JitSkill/FaulT-Bench đã được pin để nghiên cứu. Chưa chạy benchmark upstream, chưa chứng minh paper reproduction hoặc graph tự học.",
              "", "Kết quả chỉ áp dụng cho model/prompt/quantization, registry và fixture đã ghi trong metadata. Chưa đo hiệu năng NPU, hành vi router thật, giao dịch ghi hoặc ảnh hưởng forwarding. Các p-value chỉ mang tính thăm dò; xem CI ghép cặp trong REPORT_VI.md."]
    (a.run / "TAKEAWAYS_VI.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (a.run / "failure_analysis.json").write_text(json.dumps({"breakdown": breakdown, "constant_abstain_matches": constant_abstain,
                                                            "supported_correct_proposal_cases": {arm: sum(value for (cid, x), value in supported_correct.items() if x == arm) for arm in summary["arms"]},
                                                            "errors": error_counts, "examples": selected}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ANALYSIS_WRITTEN", a.run / "TAKEAWAYS_VI.md")


if __name__ == "__main__":
    main()
