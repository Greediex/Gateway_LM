# Validation của gói benchmark (không phải kết quả Qwen)

- Frozen dataset: **1.000 cases**, **1.017 turns**, **120/120** Skill IDs được đại diện trong gold catalog.
- Chia theo track: catalog **390**, E2E **320** (bao gồm 17 lượt follow-up), fault/contract **290**.
- Chia split: **683 dev / 317 test**, theo scenario-family hash.
- Đã chạy **23/23 unit tests thành công** cho generator output, manifest hash, gold rubric, fault rubric, split integrity, an toàn loopback và metrics.
- Đã kiểm tra `python -m py_compile` cho các script chính và `benchmark.py --mode validate`.
- **Chưa chạy** `catalog-retrieval` từ repository thật, `catalog-llm` với Ollama, `fixture-llm` hoặc `fault` trên checkout Gateway_LM. Các phép thử đó cần đặt package vào repo + model tương ứng. Kết quả hiện tại **không chứng minh** correctness của integration với HEAD mới nhất hoặc chất lượng Qwen.

## Điều kiện nghiệm thu thực tế

1. Chạy unittest Gateway_LM và unittest benchmark không có lỗi.
2. `benchmark.py --mode fault --split all`: kiểm tra các test doubles dùng đúng `SkillChat`, `ReadSession`, `RCAAgent` đang có; sửa adapter nếu API của HEAD thay đổi (không sửa golden labels để ép pass).
3. `catalog-retrieval`: xem một số golden labels thất bại có phải mismatch semantic metadata.
4. `fixture-llm`: chạy model thật, kiểm tra grounding và safety.
5. Giữ holdout test để đánh giá sau khi đã cố định code/model; ghi Git SHA, model digest và environment.
