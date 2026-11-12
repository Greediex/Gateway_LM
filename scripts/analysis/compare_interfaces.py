"""Compare completed v1/v2 runs without treating follow-up as blinded evidence."""
import argparse
import json
from pathlib import Path


def load(path):
    meta = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    if not meta.get("finished_at"):
        raise ValueError("Run not complete: " + str(path))
    rows = [json.loads(x) for x in (path / "episodes.jsonl").read_text(encoding="utf-8").splitlines()]
    return meta, rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("primary", type=Path)
    p.add_argument("native", type=Path)
    p.add_argument("--output", type=Path, default=Path("EXPERIMENT_OVERVIEW_VI.md"))
    a = p.parse_args()
    m1, r1 = load(a.primary)
    m2, r2 = load(a.native)
    assert m1["model"] == m2["model"]
    assert m1["dataset_manifest"]["sha256"] == m2["dataset_manifest"]["sha256"]
    hashes1 = {name.replace("\\", "/"): value for name, value in m1["source_sha256"].items()}
    hashes2 = {name.replace("\\", "/"): value for name, value in m2["source_sha256"].items()}
    for source in ("gateway_pilot/core.py", "gateway_pilot/run.py", "prepare_data.py"):
        assert hashes1[source] == hashes2[source], source
    for setting in ("seed", "max_tools", "max_decisions", "candidate_k"):
        assert m1["args"][setting] == m2["args"][setting], setting
    s1 = json.loads((a.primary / "summary.json").read_text(encoding="utf-8"))
    s2 = json.loads((a.native / "summary.json").read_text(encoding="utf-8"))
    lines = ["# Gateway LM — kết quả thử model nhỏ với graph", "",
             f"Model `{m1['model']}`, GGUF {m1['model_metadata']['details']['quantization_level']}, actual parameter count {m1['model_metadata']['parameter_count']:,} (<3B). Runtime CPU; tool adapters là synthetic replay.", "",
             "## Kết quả đo được", "",
             "| Interface / Arm | Tự hoàn tất đúng | Buộc dừng | Tool/ca | LLM p50 / p95 (s) |",
             "|---|---:|---:|---:|---:|"]
    for interface, summary in (("v1 JSON-text", s1), ("v2 native (exploratory)", s2)):
        for arm in ("rules", "flat", "retrieval", "graph", "graph_batch"):
            if arm not in summary["arms"]:
                continue
            value = summary["arms"][arm]
            lines.append(f"| {interface} / {arm} | {value['autonomous_success']}/{value['n']} ({value['success_rate']:.2%}) | {value['forced_stops']} | {value['mean_tool_calls']:.2f} | {value['llm_call_p50_s']:.2f} / {value['llm_call_p95_s']:.2f} |")
    lines += ["", "## Đối chiếu interface trên ca chung", ""]
    for arm in sorted(set(s1["arms"]) & set(s2["arms"])):
        v1 = {r["case_id"]: r for r in r1 if r["arm"] == arm}
        v2 = {r["case_id"]: r for r in r2 if r["arm"] == arm}
        ids_ = v1.keys() & v2.keys()
        if not ids_:
            continue
        c1 = sum(v1[i]["autonomous_success"] for i in ids_)
        c2 = sum(v2[i]["autonomous_success"] for i in ids_)
        lines.append(f"- {arm}: v1 {c1}/{len(ids_)}, v2 {c2}/{len(ids_)}; chênh lệch {100*(c2-c1)/len(ids_):+.1f} điểm phần trăm trên cùng ca. Không coi đây là kiểm chứng holdout mới.")
    lines += ["", "## Có thể dùng đến mức nào trong dự án?", "",
              "Ở cấu hình đã thử, graph riêng chưa cải thiện khả năng model tự điều phối: 9/48 so với 10/48 ở tool phẳng. Chế độ model tốt nhất là Core/graph chuẩn bị evidence trước rồi model chọn verdict qua native tools: 27/48. Đây chưa đủ tin cậy để giao toàn bộ vòng chẩn đoán cho model.",
              "Với bốn workflow cố định hiện tại, giữ Fastpath/luật và Core nắm điều phối, dependency, scope, policy và validator. Model dùng thử như analyst/advisor có kiểm chứng. Lỗi chính gồm lặp bước, bỏ sót tiền điều kiện, kết luận ở mức triệu chứng và citation không đầy đủ."]
    analysis_path = a.native / "failure_analysis.json"
    if analysis_path.exists():
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        count = analysis["supported_correct_proposal_cases"].get("graph_batch", 0)
        answerable = analysis["breakdown"]["graph_batch"]["answerable"]
        lines.append(f"Trong {answerable['n']} ca đủ dữ liệu, native model từng đề xuất đúng nhãn với fact hỗ trợ ở {count}/{answerable['n']} ca, nhưng chỉ {answerable['success']}/{answerable['n']} ca hoàn tất đúng toàn bộ contract. Đây là phân tích thành phần, chưa phải một chế độ tự sửa citation đã triển khai.")
    lines += ["", "## Cách đọc kết quả", "",
              "- v1 là test protocol đã khóa trước khi chạy 48 ca × 5 arm. v2 là thử nghiệm interface tiếp nối sau khi quan sát lỗi v1; không gộp số liệu hoặc tuyên bố là đánh giá mù mới.",
              "- v2 đổi cả native template, tool/argument schema, terminal function và protocol wording. Cải thiện nếu có chưa tách được tác động riêng của native serialization hay schema.",
              "- graph tự điều phối và graph_batch là phân công khác nhau. graph_batch để Core thu thập evidence trước, model chỉ chọn verdict; nó không chứng minh model tự lập kế hoạch nhiều bước.",
              "- Cùng model, fixture, hash Core và scorer đã được kiểm tra. Workflow ID/checklist cho sẵn; chưa đo intent routing, văn bản giải thích, router thật hoặc NPU.",
              "- Baseline rules được xây cùng các workflow/fixture đơn giản. Điểm cao không chứng minh khả năng khái quát cho sự cố mới.",
              "- Mọi kết quả thất bại, citation sai, đề xuất bị chặn và Core buộc dừng vẫn giữ trong JSONL. Core buộc dừng không tính là model tự thành công.",
              "", "## Hồ sơ đầy đủ", "",
              f"- Primary: [{a.primary.as_posix()}/REPORT_VI.md]({a.primary.as_posix()}/REPORT_VI.md)",
              f"- Primary error analysis: [{a.primary.as_posix()}/TAKEAWAYS_VI.md]({a.primary.as_posix()}/TAKEAWAYS_VI.md)",
              f"- Native follow-up: [{a.native.as_posix()}/REPORT_VI.md]({a.native.as_posix()}/REPORT_VI.md)",
              f"- Native error analysis: [{a.native.as_posix()}/TAKEAWAYS_VI.md]({a.native.as_posix()}/TAKEAWAYS_VI.md)",
              "- Code papers: [docs/PAPER_SOURCES.md](docs/PAPER_SOURCES.md)",
              "- Scope: [docs/PROJECT_ALIGNMENT.md](docs/PROJECT_ALIGNMENT.md)",
              "- Primary-source interface notes: [docs/MODEL_INTERFACE_NOTES.md](docs/MODEL_INTERFACE_NOTES.md)"]
    a.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("INTERFACE_COMPARISON_WRITTEN", a.output)


if __name__ == "__main__":
    main()
