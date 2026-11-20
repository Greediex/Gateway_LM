<!-- doc: voice.vi | topic: igate_voice | lang: vi | as_of: 2026-11-08 | review: draft -->
# Nói chuyện với iGate

## Cách bắt đầu nói
<!-- id: voc.vi.start | facts: voc.start | src: docs/web_voice_mic.md; docs/kws_operating_point.md | aliases: cách nói, bắt đầu nói, cách ra lệnh igate, ra lệnh cho igate, gọi igate, hey igate, nút nói, đang nghe, làm sao để ra lệnh, nói thế nào, hủy câu nói | say_for: howto | say: Nói "Hey iGate" hoặc bấm nút nói ở màn hình chính, chờ hiện "Đang nghe" rồi nói một câu ngắn, rõ. -->
Nói "Hey iGate" về phía router, hoặc bấm nút nói ở màn hình chính, chờ hiện "Đang nghe" rồi nói một câu ngắn, rõ. Trên điện thoại mở trang vnpt.internal: nhấn giữ nút nói trong lúc nói, buông tay khi xong. Khi iGate đang nghĩ, màn hình xoay và hiện bước đang làm; bấm X để hủy. Mỗi lần nên nói một yêu cầu.

## Tôi có thể nói những gì
<!-- id: voc.vi.say | facts: voc.say | src: llm/config/skills/catalog.json; docs/voice_command_execution.md §2 | aliases: tôi có thể nói gì, nói được gì, igate làm được gì, hỏi được gì, câu mẫu, ví dụ câu lệnh, có những lệnh nào, bạn giúp được gì | say_for: ability,howto | say: Bạn có thể hỏi tình trạng router và thiết bị, đo chất lượng mạng, ra lệnh chặn, giới hạn tốc độ, ưu tiên, bật wifi khách, hẹn giờ, và hỏi kiến thức như "Wi-Fi 8 là gì?". -->
Bạn có thể hỏi tình trạng router ("CPU router bao nhiêu?", "Có Internet không?", "Router đang phát những băng nào?"); hỏi thiết bị ("Có bao nhiêu thiết bị đang kết nối?", "Điện thoại của mẹ bắt sóng thế nào?", "Ai đang chơi game?"); đo mạng ("Kiểm tra chất lượng mạng"); ra lệnh ("Chặn mạng máy chơi game", "Giới hạn tải xuống của TV 5 Mbps", "Ưu tiên mạng cho laptop của bố", "Bật wifi khách 30 phút"); hẹn giờ và xem lịch; và hỏi kiến thức ("Wi-Fi 8 là gì?", "RSSI là gì?", "VNPT Technology là công ty gì?").

## Cách nói lệnh chặn và mở mạng
<!-- id: voc.vi.block | facts: voc.block | src: Router_App/router_display_src/LLM_JSON_CMD.md §5.5-5.6; docs/voice_command_execution.md §2 | aliases: muốn chặn mạng thì nói thế nào, cách chặn mạng, phải nói thế nào để chặn, chặn internet một máy, mở lại mạng, bỏ chặn, cắt mạng | say_for: howto | say: Nói hành động rồi tên thiết bị, ví dụ "Chặn mạng máy chơi game" hoặc "Bỏ chặn TV phòng khách"; router chỉ chặn khi bạn bấm Xác nhận. -->
Nói hành động rồi tên thiết bị: "Chặn mạng máy chơi game", "Chặn mạng điện thoại của con", "Mở lại mạng cho máy tính bảng của con" hoặc "Bỏ chặn TV phòng khách". Tên là tên hiện trong danh sách thiết bị hoặc nhãn bạn đã gắn. Màn hình router hỏi lại "Chặn … ?" và chỉ chặn khi bạn bấm Xác nhận trong khoảng 20 giây. Chặn theo ứng dụng ("chặn game cho …") hiện sẽ chặn Internet của cả máy đó, iGate sẽ nói rõ điều này.

## Cách nói giới hạn tốc độ và ưu tiên
<!-- id: voc.vi.limit | facts: voc.limit | src: Router_App/router_display_src/LLM_JSON_CMD.md §5.7-5.8 | aliases: giới hạn tốc độ, giới hạn băng thông, hạn chế tốc độ, ưu tiên mạng, ưu tiên game, tối ưu chơi game, nói thế nào để giới hạn | say_for: howto | say: Nói thiết bị và số Mbps, ví dụ "Giới hạn tải xuống của TV 5 Mbps"; muốn ưu tiên thì nói "Ưu tiên mạng cho laptop của bố". -->
Giới hạn: nói thiết bị và số Mbps, có thể chỉ một chiều: "Giới hạn tải xuống của TV 5 Mbps", "Giới hạn máy chơi game 20 Mbps tải xuống, 5 Mbps tải lên". Chiều không nói giữ nguyên như cũ. Ưu tiên: "Ưu tiên mạng cho laptop của bố" hoặc "Ưu tiên chơi game cho máy chơi game"; router ưu tiên cả thiết bị đó khi mạng bận, không làm chậm máy khác khi mạng rảnh. Số Mbps phải là số nguyên từ 1 đến 10.000.

## Cách nói hẹn giờ
<!-- id: voc.vi.schedule | facts: voc.schedule | src: Router_App/router_display_src/LLM_JSON_CMD.md §5.12 | aliases: hẹn giờ, đặt lịch, chặn trong 30 phút, chặn từ mấy giờ, mỗi ngày, các ngày trong tuần, cuối tuần, hủy lịch, danh sách lịch | say_for: howto | say: Thêm thời gian vào lệnh, ví dụ "Chặn mạng máy tính bảng của con trong 30 phút" hoặc "từ 21 giờ đến 6 giờ"; hủy bằng "Hủy lịch số 3". -->
Thêm thời gian vào lệnh: "Chặn mạng máy tính bảng của con trong 30 phút" (hết giờ tự trả lại như cũ), "Chặn mạng máy chơi game sau 10 phút", "Chặn mạng máy tính bảng của con từ 21 giờ đến 6 giờ các ngày trong tuần" (hoặc hằng ngày, cuối tuần), "Bật wifi khách 2 tiếng". Xem lịch: "Danh sách lịch hẹn giờ"; hủy: "Hủy lịch số 3". Lệnh có điều kiện như "nếu… thì…" không hẹn được, hãy nêu giờ cụ thể.

## Cách nói về mạng khách
<!-- id: voc.vi.guest | facts: voc.guest | src: docs/voice_command_execution.md §2, §4 | aliases: bật wifi khách, tắt wifi khách, mạng khách, wifi cho khách, khách đến nhà, mật khẩu wifi khách | say_for: howto | say: Nói "Bật wifi khách", "Bật wifi khách 30 phút" hoặc "Tắt wifi khách"; khi bật, màn hình router hiện mã QR cho khách quét. -->
"Bật wifi khách", "Bật wifi khách 30 phút", "Tắt wifi khách". Khi bật, màn hình router hiện mã QR cho khách quét; nếu hẹn giờ, mạng khách tự tắt đúng giờ và màn hình ghi giờ tắt. Muốn khách vào lại khi mạng khách đang bật, mở màn hình Wi-Fi để hiện mã QR. iGate không đọc mật khẩu thành tiếng.

## Gọi thiết bị bằng tên hoặc nhãn
<!-- id: voc.vi.names | facts: voc.names | src: docs/device_labels.md §5 | aliases: gọi tên thiết bị, tên máy, hai điện thoại, nhiều máy cùng tên, gọi thiết bị thế nào, nhãn, điện thoại của mẹ, máy nào, trùng tên, không tìm thấy thiết bị, nói tên thiết bị | say_for: howto | say: Gọi thiết bị bằng tên trong danh sách hoặc bằng nhãn đã gắn, ví dụ "điện thoại của mẹ" hay "TV phòng khách". -->
Gọi thiết bị bằng tên trong danh sách ("Galaxy-A54") hoặc bằng nhãn đã gắn: loại + người dùng + phòng, ví dụ "điện thoại của mẹ", "TV phòng khách", "laptop của An ở phòng làm việc". Có thể nói "tivi", "ti vi" hay "TV", "bố", "ba" hay "cha". Nếu nhiều máy cùng khớp (mẹ có hai điện thoại), iGate hỏi lại máy nào; nếu không có máy nào, iGate nói không tìm thấy chứ không đoán.

## Xác nhận lệnh và kết quả
<!-- id: voc.vi.confirm | facts: voc.confirm | src: docs/voice_command_execution.md §1-2; llm/docs/qwen4b_voice_demo_execution_plan_20261104.md §2b | aliases: xác nhận, bấm xác nhận, lệnh có chạy chưa, đã chặn chưa, không thành công, không phản hồi, sao chưa làm, hủy lệnh | say_for: define,howto | say: Lệnh thay đổi mạng chỉ chạy khi bạn bấm Xác nhận; sau khi chạy, router kiểm tra lại và báo Đã xong, Không thành công hoặc Không phản hồi. -->
Lệnh làm thay đổi mạng không bao giờ tự chạy khi bạn chưa đồng ý: lệnh chặn có nút Xác nhận trên màn hình router; các lệnh khác có nút Xác nhận/Hủy trên trang trợ lý. Không bấm trong thời gian chờ thì không có gì thay đổi. Sau khi chạy, router kiểm tra lại thật và báo Đã xong, Không thành công hoặc Không phản hồi; router không báo thành công khi chưa thấy kết quả.

## Mẹo để iGate hiểu đúng
<!-- id: voc.vi.tips | facts: voc.tips | src: docs/web_voice_mic.md; llm/core/README.md (guards) | aliases: igate không hiểu, nghe nhầm, nói không được, mẹo, nói sao cho đúng, ồn quá, không nghe rõ | say_for: howto | say: Nói một yêu cầu mỗi lần, câu ngắn, nêu rõ tên thiết bị, và chờ hiện "Đang nghe" rồi mới nói. -->
Nói một yêu cầu mỗi lần, câu ngắn, nêu rõ tên thiết bị. Chờ "Đang nghe" rồi mới nói. Nơi ồn, nói gần router hơn hoặc dùng mic điện thoại qua vnpt.internal. Đổi ý giữa câu ("à thôi") thì iGate sẽ không làm gì. Câu hỏi về cách làm ("làm sao để chặn…") được trả lời bằng hướng dẫn chứ không tự thực hiện. Không nghe rõ thì nói lại; câu mơ hồ iGate sẽ hỏi lại.

## Riêng tư khi nói chuyện
<!-- id: voc.vi.privacy | facts: voc.privacy | src: esp32/main/ui/ui_showcase_slides.c (voice page); Router_App/router_screen_src/README.md (iGate Portal home) | aliases: có ghi âm không, có gửi lên mạng không, riêng tư, nghe lén, dữ liệu giọng nói, ai nghe được | say_for: define,judge | say: Giọng nói được xử lý ngay trên router, không gửi lên cloud, và router chỉ nghe sau khi bạn nói "Hey iGate" hoặc bấm nút nói. -->
Giọng nói được nhận dạng và xử lý ngay trên router, không gửi lên cloud. Router chỉ nghe sau khi bạn nói "Hey iGate" hoặc bấm nút nói. Màn hình router không hiện câu bạn nói; trang web của router có cột "Hỏi đáp với iGate" hiện vài câu hỏi và trả lời gần nhất cho người đang xem trong mạng nhà, và danh sách này mất khi router khởi động lại.
