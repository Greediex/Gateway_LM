<!-- doc: ai_features.vi | topic: ai_features | lang: vi | as_of: 2026-11-08 | review: draft -->
# Các tính năng AI của router

## AI QoS là gì
<!-- id: ai.vi.qos | facts: ai.qos | src: esp32/main/ui/ui_showcase_slides.c (AI QoS page); docs/sec_qos_contract.md | aliases: ai qos là gì, qos là gì, ưu tiên thông minh, nhận biết ứng dụng, chất lượng dịch vụ, router biết ai đang chơi game | say_for: define | say: AI QoS nhận biết mỗi thiết bị đang chơi game, gọi video, gọi thoại hay xem video, và ưu tiên đúng thiết bị khi mạng bận. -->
AI QoS nhận biết mỗi thiết bị đang làm gì: chơi game, gọi video, gọi thoại, xem video hay việc khác, và ưu tiên đúng thiết bị khi mạng bận để cuộc gọi và game mượt hơn. Router cũng ghi thời gian từng thiết bị dùng mỗi loại: đang dùng, hôm nay và 7 ngày. Việc nhận biết là của AI nên có lúc nhầm loại ứng dụng; router nhìn loại lưu lượng, không đọc nội dung bạn xem.

## AI Security là gì
<!-- id: ai.vi.security | facts: ai.security | src: esp32/main/ui/ui_showcase_slides.c (AI Security pages); docs/ai_security_events.md | aliases: ai security là gì, bảo mật thông minh, router phát hiện tấn công, chống hack, an ninh mạng, bảo vệ thiết bị | say_for: define | say: AI Security theo dõi mọi thiết bị trong mạng ngay trên router, phát hiện camera bị nhiễm, quét cổng, xâm nhập, tấn công và thiết bị mới vào mạng. -->
AI Security theo dõi mọi thiết bị trong mạng, ngày và đêm, ngay trên router: phát hiện camera bị nhiễm, quét cổng, xâm nhập, tấn công và thiết bị mới vừa vào mạng. Mỗi sự kiện được đặt tên, có mức độ, có thể chặn thiết bị bằng một chạm hoặc một câu nói. Thống kê xem theo 24 giờ hoặc 7 ngày.

## AI xử lý ngay trên router qua năm bước
<!-- id: ai.vi.pipeline | facts: ai.pipeline | src: esp32/main/ui/ui_showcase_slides.c (pipeline page) | aliases: ai hoạt động thế nào, ai trong router làm gì, quy trình ai, xử lý dữ liệu mạng, edge ai hoạt động ra sao | say_for: define | say: AI trong router đi qua năm bước: thấy mọi thiết bị, phân loại lưu lượng, quyết định ai được ưu tiên hay bị chặn, áp dụng ngay trên router và cho trải nghiệm mượt hơn. -->
AI trong router đi từ lưu lượng thô tới trải nghiệm tốt hơn qua năm bước: thấy mọi thiết bị và luồng dữ liệu trong mạng; phân loại cuộc gọi, game, video và phát hiện tấn công; quyết định ai được ưu tiên và cái gì bị chặn; áp dụng ngay trên router theo thời gian thực; kết quả là cuộc gọi, game mượt và ngôi nhà được bảo vệ. Tất cả xử lý trên thiết bị: nhanh, riêng tư và vẫn chạy khi mất Internet.

## Trợ lý iGate hiểu và trả lời thế nào
<!-- id: ai.vi.llm | facts: ai.llm | src: llm/core/README.md (Pipeline); llm/docs/qwen35_tong_hop_20261107.md §1 | aliases: igate hoạt động thế nào, mô hình ngôn ngữ, llm, chatgpt, ai trả lời từ đâu, igate có bịa không, model nào, trí tuệ nhân tạo | say_for: define | say: iGate dùng một mô hình ngôn ngữ chạy ngay trên router, lấy dữ liệu thật của router hoặc hướng dẫn có sẵn để trả lời ngắn; không có dữ liệu thì nói là không có. -->
iGate dùng một mô hình ngôn ngữ (LLM) chạy trên bộ xử lý AI của router, không gọi lên cloud. Với mỗi câu, iGate hiểu bạn muốn hỏi hay ra lệnh, lấy dữ liệu thật của router (thiết bị, sóng, lưu lượng, kết quả đo) hoặc tài liệu hướng dẫn có sẵn, rồi trả lời ngắn gọn. Không có dữ liệu thì nói là không có, không đoán. Lệnh thay đổi mạng được kiểm tra an toàn và chờ bạn xác nhận. Mỗi câu thường mất vài giây.

## Wi-Fi Sensing nhận biết chuyển động
<!-- id: ai.vi.sensing | facts: ai.sensing | src: docs/wifi_sensing_preview.md §1-3 | aliases: wifi sensing là gì, cảm biến bằng wifi, phát hiện người, chăm sóc người già, phát hiện ngã, không cần camera | say_for: define | say: Wi-Fi Sensing dùng sóng Wi-Fi để nhận biết chuyển động trong nhà, không cần camera; trên router hiện tại đây là bản xem trước với dữ liệu mô phỏng. -->
Wi-Fi Sensing dùng chính sóng Wi-Fi để nhận biết chuyển động trong nhà, không cần camera hay thiết bị đeo, hướng tới chăm sóc người thân lớn tuổi (hoạt động hằng ngày, có người hay không, nhắc khi lâu không thấy vận động). Trên router hiện tại đây là bản xem trước với dữ liệu mô phỏng; router chưa đo thật và không nhận ra là ai.

## Dữ liệu của AI ở đâu
<!-- id: ai.vi.data | facts: ai.data | src: esp32/main/ui/ui_showcase_slides.c (pipeline page); docs/router_snapshot_yaml.md §2 | aliases: dữ liệu có gửi đi không, router xem video, router biết xem video gì, router có biết tôi xem gì, theo dõi lịch sử xem, ai có thu thập dữ liệu không, riêng tư, lưu dữ liệu ở đâu, ai biết tôi xem gì | say_for: define,judge | say: Dữ liệu của AI được xử lý ngay trên router và không gửi lên cloud; router biết loại hoạt động của thiết bị, không đọc nội dung bạn xem. -->
Các tính năng AI xử lý dữ liệu ngay trên router: loại lưu lượng, thời gian dùng, sự kiện an ninh và câu nói không được gửi lên cloud để phân tích. Router biết loại hoạt động của từng thiết bị (ví dụ đang xem video), không đọc nội dung trang hay video cụ thể. Thống kê lưu lượng và thời gian dùng giữ tối đa khoảng 7 ngày để hiện biểu đồ.
