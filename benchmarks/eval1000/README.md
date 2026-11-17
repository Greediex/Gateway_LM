# Gateway_LM v2 — EVAL-1000

**1.000 kịch bản đánh giá, 1.017 lượt hỏi**, bao phủ đầy đủ **120 Skill IDs** trong catalog thiết kế. Bộ này đo *ba thứ khác nhau*, xuất **ba báo cáo riêng**:

1. **Catalog Intelligence** — 390 cases. Kiểm tra tìm/chọn Skill đúng trên **120 Skills thiết kế**, bất kể có backend thực thi hay chưa. Có chế độ baseline chạy `SkillRetriever` thật (`catalog-retrieval`) và chế độ kiểm tra Ollama trực tiếp (`catalog-llm`) dưới dạng *offline classification*, **không gọi bất kỳ Skill nào**.
2. **LLM Skill Chat E2E** — 320 cases, **337 turns**. Chạy `SkillChat → SkillLauncher → RuntimeSkillBridge → ReadSession/GraphRunner → Verifier/RCA`, với Ollama thật và **FakeLaptopBackend** có sẵn trong `tests/test_skill_launcher.py`. Tùy chọn `live-http` dùng `/api/chat` trên localhost với READ thật, yêu cầu bật `--allow-live`.
3. **Fault/Contract** — 290 cases. Chạy **Core thật** với model double/clock injection để kiểm tra TTL, model outage, proposal sai, quyền, bộ đếm, RCA, adaptive multiround. **Không được coi điểm này là độ chính xác của LLM.**

**Dữ liệu được cố định** tại `cases.jsonl`. `manifest.json` chứa SHA-256 để chống thay đổi nhãn không kiểm soát. `generate.py` là generator xác định với seed ổn định (chỉ dùng khi chủ động tạo phiên bản benchmark mới). **Không chạy generator trước khi đánh giá**, vì sẽ biến đổi dataset và SHA.

## 1. Bố cục

```text
benchmarks/eval1000/
├── README.md
├── DATA_CARD.md
├── cases.jsonl                 # 1000 cases, immutable when comparing models
├── review_cases.csv            # review/question/expected data
├── manifest.json               # SHA256 and stratification
├── benchmark.py                # runner and deterministic scorer
├── generate.py                 # regenerate only for benchmark version change
├── legacy_eval01_reference.py  # reused EVAL-01 scored E2E evidence contract
├── examples/
│   ├── seed_eval01_cases.jsonl
│   ├── gate_catalog.json
│   └── gate_contract.json
└── tests/
    └── test_eval1000.py
```

## 2. Cài trong repository Gateway_LM v2

Trong máy có bản clone của repo:

```bash
git switch v2
git pull --ff-only origin v2
# Đặt file ZIP đã tải ở repo root, rồi giải nén trực tiếp:
unzip Gateway_LM_v2_EVAL1000.zip -d .
# Nội dung ZIP sẽ nằm trong benchmarks/eval1000/, không đè baseline cũ
source .venv-graph/bin/activate
export PYTHONPATH="$PWD"
python benchmarks/eval1000/benchmark.py --mode validate
python -m unittest discover -s benchmarks/eval1000/tests -v
```

Để chạy các chế độ dùng LLM cần cài và chạy Ollama với model local như hướng dẫn của Gateway_LM, ví dụ `qwen3:1.7b`. Không có cloud API hay bước cài đặt tự động nào trong gói benchmark.

> **Quan trọng:** Chạy từ repo root. Các chế độ có Core import trực tiếp modules trong `gateway_pilot/` và fake backend hiện có `tests.test_skill_launcher.FakeLaptopBackend`. Không cài hệ thống Agent thứ hai.

## 3. Chạy benchmark

### A. Baseline retrieval trên toàn bộ 120 Skills

```bash
python benchmarks/eval1000/benchmark.py \
  --mode catalog-retrieval --split dev \
  --out runs/eval1000/catalog_retrieval_dev
```

`catalog-retrieval` chạy `SkillCatalog.load()` + `SkillRetriever.search(..., include_proposed=True)`. Đây là benchmark **retrieval BM25/graph**, không phải kết quả LLM.

### B. Kiểm tra LLM chọn Skill trên catalog 120

```bash
python benchmarks/eval1000/benchmark.py \
  --mode catalog-llm --split dev --model qwen3:1.7b \
  --out runs/eval1000/catalog_llm_dev
```

Benchmark gửi metadata của đúng 120 Skill cho Ollama local, yêu cầu trả về tối đa 5 IDs. Phần này là **một phép thử model selection ngoài ứng dụng** nhằm kiểm tra thiết kế catalog và chất lượng hiểu yêu cầu; **không phải đường đi `SkillChat.choose_skills` production**, không cấp quyền và không chạy commands.

### C. LLM thật + SkillChat thật + backend synthetic

```bash
python benchmarks/eval1000/benchmark.py \
  --mode fixture-llm --split dev --model qwen3:1.7b \
  --limit 10 \
  --out runs/eval1000/fixture_smoke

# Khi đã xem đủ lỗi/latency, chạy mọi case thuộc E2E dev:
python benchmarks/eval1000/benchmark.py \
  --mode fixture-llm --split dev \
  --out runs/eval1000/fixture_dev
```

Một số câu có follow-up chung session (17 cases). Các câu khác tách session; dữ liệu mô phỏng không được trình bày như dữ liệu laptop thực.

### D. Fault injection với Core thật

```bash
python benchmarks/eval1000/benchmark.py \
  --mode fault --split all \
  --out runs/eval1000/fault_all \
  --gate benchmarks/eval1000/examples/gate_contract.json
```

Có **80 ca TTL**, **70 ca error/budget**, và các ca kiểm thử khác. Model double chỉ tạo quyết định giả lập; thời gian được đẩy tiến qua clock tiêm vào (không cần chờ 30 giây thật). Chú ý: 80 ca TTL đều kiểm **cùng một loại nguyên tắc chống stale evidence** với nhiều cách diễn đạt, không phải 80 sự cố độc lập.

### E. READ thật trên laptop (tùy chọn, KHÔNG khuyến khích chạy cả bộ mù quáng)

```bash
bash web_gateway/start_linux.sh

# Terminal khác:
python benchmarks/eval1000/benchmark.py \
  --mode live-http --split dev --category multi_intent \
  --limit 5 --allow-live \
  --base-url http://127.0.0.1:8765 \
  --out runs/eval1000/live_smoke
```

Chỉ được dùng HTTP loopback; script không gửi tới gateway ngoài mạng hay remote IP. NetworkManager, route, ICMP và DNS vẫn có thể bị đọc qua Core, do đó phải chọn chủ động.

### F. Chạy tập test giữ kín

Sau khi ổn định trên dev, không sửa nhãn/test theo kết quả model. Lưu SHA-256, git HEAD, model digest và inference config rồi chạy:

```bash
python benchmarks/eval1000/benchmark.py --mode catalog-llm \
  --split test --out runs/eval1000/catalog_llm_test
python benchmarks/eval1000/benchmark.py --mode fixture-llm \
  --split test --out runs/eval1000/fixture_test
python benchmarks/eval1000/benchmark.py --mode fault \
  --split test --out runs/eval1000/fault_test
```

`--case-id EVAL-0001`, `--category safety` và `--limit 10` có thể dùng để tái hiện/giảm chi phí trong dev. Không trộn kết quả chỉ chạy subset với kết quả toàn bộ benchmark. `--timeout` chỉ hạn chế thời gian gọi HTTP/LLM từ runner, không thay đổi TTL của Gateway_LM.

## 4. Phân bố 1.000 cases

| Nhóm | Tổng | Catalog | E2E | Fault |
|---|---:|---:|---:|---:|
| Single-Skill Selection | 120 | 120 | 0 | 0 |
| Multi-Skill Coordination/Selection | 150 | 150 | 0 | 0 |
| Multi-Intent | 100 | 60 | 40 | 0 |
| Adaptive Planning | 100 | 0 | 50 | 50 |
| RCA & Evidence Reasoning | 100 | 0 | 50 | 50 |
| Unsupported Capabilities | 80 | 20 | 40 | 20 |
| Safety & Scope | 100 | 0 | 80 | 20 |
| TTL & Session | 80 | 0 | 0 | 80 |
| Model Error & Budget | 70 | 0 | 0 | 70 |
| Vietnamese Natural Language | 100 | 40 | 60 | 0 |
| **Tổng** | **1000** | **390** | **320** | **290** |

**Split**: dev **683 cases** và test **317 cases**, phân theo `scenario_family` bằng hash để cùng họ kịch bản không nằm ở hai split. Có **17 ca E2E nhiều lượt**, nên tổng là **1.017 turns**. Đây là split giữ lại để đánh giá phiên bản sau, **không phải** train set cho fine-tuning.

## 5. Gold labels và cách chấm

### Catalog

`gold.required_skill_ids` là 1–3 Skill IDs đúng cho một nhu cầu. Chấm precision/recall/F1, exact set match, Hit@1/3, theo Skill và category. Không có execution; tất cả metadata vẫn là design-only. Mỗi ID xuất hiện ít nhất một lần trong gold catalog. **Việc chọn đúng ID không chứng minh Function đã khả dụng.**

### E2E

Tái sử dụng scorer EVAL-01 trên các trường thực từ `SkillChat`: `skill_runs`, `calls`, `case_status`, `stop_reason`, `snapshot`, `evidence_ids`, `unavailable_skills`, `rca_assessments`. Labels có nhóm Skill thay thế tương đương, required answer ports, unacceptable selections, stop/status rules và một số fixture truth claims. Không ép mạng thật phải trả `MEASURED` khi thiếu capability. Chấm **khả năng gắn lời đáp với evidence**, không tự chấm độ chính xác nguyên nhân không có ground truth.

### Fault

`gold.fault` điều khiển một model double thật sự gọi `SkillChat`, có thể đưa `invalid_model_proposal`, `model_unavailable`, `round_budget_exhausted`, `write_intent_requires_approval`, tự tăng clock 31 giây, ... Scorer xác minh **không thực thi trái quyền** và **không sử dụng stale evidence**, bằng actual response. Đây là *conformance/safety regression*, không phải chất lượng suy luận LLM. Các lỗi được cố tình tiêm vào và xử lý đúng sẽ tính **PASS**.

### Các chỉ số đầu ra

- `pass_rate`, `selection_precision/recall/f1`, `selection_exact_rate` (catalog), `by_skill.csv`.
- `grounding_rate`, `fixture_rca_accuracy` (nếu có claim truth được chấm).
- `mean_tool_calls`, `safety_violation_cases`, error reasons.
- `p50_latency_ms`, `p95_latency_ms`, `p99_latency_ms`.
- `by_category`, `stop_reason_counts`, `distinct_scenario_families`.

Tất cả là *observed metrics*; benchmark không tự tuyên bố model đạt mức tốt khi chưa chạy thật.

## 6. Báo cáo và CI gates

Mỗi run xuất `scores.jsonl`, `summary.json`, `report.md`; catalog mode có `by_skill.csv`. Để tránh lưu IP/MAC thật ra tệp một cách mặc định, **raw responses không được lưu**. Thêm `--store-raw` nếu có lý do rõ ràng và hiểu rằng output có thể chứa thông tin mạng nhạy cảm. Giữ thư mục `runs/` trong `.gitignore`.

`--gate examples/gate_*.json` cho exit code 2 nếu metric thấp hơn `minimum` hoặc vượt `maximum`; ngưỡng trong ví dụ chỉ là minh họa, **không phải** mức đã hiệu chỉnh bằng số đo thật. Có thể chạy `validate` và unit tests trong CI không cần Ollama. Nên chạy LLM benchmark theo lịch trên máy tự quản lý có CPU/GPU phù hợp, không chạy ngầm trên runner public.

## 7. Cảnh báo phương pháp (quan trọng)

- Các **gold label được xây từ 120 intent seeds biên soạn thủ công + 52 scenarios EVAL-01 trước đó**, rồi sinh biến thể bằng template/seed cố định. Chúng **không phải 1.000 câu được chuyên gia gán nhãn độc lập**. Nên lấy mẫu kiểm duyệt khoảng 100–200 cases (ưu tiên test và label khó) trước khi dùng số liệu trong báo cáo nghiên cứu.
- Variants của một scenario seed có **tương quan cao**, nên không được báo khoảng tin cậy như thể có 1.000 mẫu độc lập. `distinct_scenario_families` nhằm làm lộ giới hạn này.
- Catalog (120) là thiết kế; Linux live chỉ có một tập con approved. Thực thi tất cả 120 trên hardware là không đúng mục tiêu và bị Core ngăn.
- `catalog-llm` đo classifier trên catalog; không đồng nghĩa đo chính xác con đường model production `choose_skills`, do adapter chat hiện phân biệt `READY/UNAVAILABLE`.
- Fault mode tiêm model double. Không đưa điểm Fault vào điểm LLM tổng hợp.
- Kết quả `live-http` phụ thuộc máy, đường mạng, thời gian, TTL và cấu hình. Phải ghi môi trường và tránh so sánh trực tiếp với fixture.
- Không có phép đo real model từ người tạo gói; **không bịa ra accuracy, latency, pass rate**.

## 8. Trình tự nghiệm thu khuyến nghị

1. `validate` + unittest trên CI, xác nhận SHA và đủ 120 IDs.
2. `catalog-retrieval --split dev`: baseline lexical/graph, tìm lỗi metadata/gold.
3. `catalog-llm --split dev`: tối ưu cách phân loại ở môi trường ngoại tuyến.
4. `fixture-llm --split dev`: đánh giá *luồng thật* và evidence correctness trên synthetic backend.
5. `fault --split all`: gate về kiểm soát quyền/TTL/lỗi.
6. Khoá model config, chạy `--split test`, rồi báo cáo **ba bảng riêng**; đối chiếu các case bị lỗi để phát hiện sai nhãn.
7. Thử nghiệm READ trên laptop thật với **mẫu đã chọn**, không đánh đồng với synthetic.

**Giữ nguyên Core của repository; benchmark chỉ nhập và gọi thành phần có sẵn.**
