# Gateway LM pilot

Prototype chẩn đoán Gateway và thử nghiệm graph, RAG và workflow. Các phép đo dùng dữ liệu replay tổng hợp.

## Thiết lập

Cài Python, tạo môi trường ảo và cài dependencies từ `requirements-graph-v3.lock`. Chạy `python setup_upstream.py` để tải đúng các commit GoS và SkillDAG dùng bởi runtime.

## Kiểm tra

```powershell
python -m unittest discover -s tests_graph_v3 -v
python -m unittest discover -s tests -v
python -m gateway_pilot.workflow --fixture GLM-21-1 --request "Laptop An vẫn có Wi-Fi, sao không truy cập Internet?" --guide --context-bytes 1800 --trace
python run_html_benchmark.py --output runs/html_benchmark --repeat 3
python run_rag_benchmark.py --output runs/rag_benchmark
```

RAG mặc định dùng runbook cho profile replay. Nguồn tham khảo và giới hạn của các repo paper được ghi trong `docs/PAPER_SOURCES.md`.

Thư mục `third_party`, kết quả chạy, môi trường ảo và dữ liệu cấu hình nhạy cảm không nằm trong bản xuất này. Script thiết lập chỉ tải hai nguồn được runtime sử dụng; các repository nghiên cứu khác được liệt kê để tham khảo. Một số báo cáo và dữ liệu vận hành cục bộ của dự án gốc không được đưa vào bản xuất.
