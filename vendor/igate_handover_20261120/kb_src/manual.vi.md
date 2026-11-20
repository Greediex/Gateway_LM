<!-- doc: manual.vi | topic: igate_manual | lang: vi | as_of: 2026-11-08 | review: draft -->
# Hướng dẫn dùng màn hình router và trang web

## Màn hình chính (Home)
<!-- id: man.vi.home | facts: man.home | src: docs/home_screen.md; esp32/main/ui/ui_home.c | aliases: màn hình chính, trang chủ, home, xem tình trạng mạng, màn hình có gì, nút nói, tôi có thể nói gì | say_for: define | say: Màn hình chính cho biết Internet có hay không, bao nhiêu thiết bị đang kết nối, lưu lượng đang dùng và AI QoS, AI Security đang làm gì. -->
Màn hình chính cho biết ngay: Internet đang có hay không, bao nhiêu thiết bị đang kết nối, lưu lượng tải xuống và tải lên đang dùng, AI QoS và AI Security đang làm gì. Ở đây có nút nói chuyện với iGate và mục "Tôi có thể nói gì?" liệt kê câu mẫu. Chạm vào từng ô để mở màn hình chi tiết; nút Wi-Fi 8 mở trang giới thiệu Wi-Fi 6·7·8.

## Xem các thiết bị đang kết nối
<!-- id: man.vi.devices | facts: man.devices | src: esp32/main/ui/ui_popup_client_detail.c; docs/device_labels.md §6 | aliases: danh sách thiết bị, xem thiết bị, máy nào đang kết nối, chi tiết thiết bị, ip của máy, mac của máy, sóng của máy, xem ai đang kết nối, ai đang kết nối ở đâu, ai đang vào mạng | say_for: howto | say: Mở "Thiết bị kết nối" để xem danh sách máy đang dùng mạng; chạm vào một máy để xem băng Wi-Fi, cường độ sóng, địa chỉ IP và MAC. -->
Mở "Thiết bị kết nối" để xem danh sách máy đang dùng mạng. Chạm vào một máy để xem chi tiết: băng Wi-Fi (2,4, 5 hay 6 GHz) hoặc cắm dây, cường độ sóng, địa chỉ IP, địa chỉ MAC và nhãn thiết bị nếu đã gắn. Bạn cũng có thể hỏi iGate, ví dụ "Có bao nhiêu thiết bị đang kết nối?" hoặc "Điện thoại của mẹ bắt sóng thế nào?".

## Gắn nhãn thiết bị
<!-- id: man.vi.labels | facts: man.labels | src: docs/device_labels.md §1, §6 | aliases: gắn nhãn, đặt tên thiết bị, đổi tên máy, nhãn thiết bị ở đâu, cách gắn nhãn, sửa nhãn, xóa nhãn, điện thoại của mẹ | say_for: howto | say: Mở chi tiết thiết bị, bấm "Gắn nhãn", chọn loại, người dùng và phòng, rồi bấm Lưu. -->
Nhãn giúp gọi thiết bị theo cách nói trong nhà, ví dụ "điện thoại của mẹ" hay "TV phòng khách". Cách gắn: mở chi tiết một thiết bị, bấm "Gắn nhãn", chọn Loại (điện thoại, máy tính bảng, laptop, TV, camera, loa…), Người dùng (bố, mẹ, ông, bà, con, dùng chung hoặc tự gõ), Phòng (khách, ngủ, làm việc, bếp hoặc tự gõ), thêm tối đa 2 tên khác, rồi bấm Lưu. Router hiện ngay câu bạn có thể nói để gọi máy đó. Tên gốc của thiết bị không đổi.

## Quản lý và xóa nhãn
<!-- id: man.vi.labels_manage | facts: man.labels_manage | src: docs/device_labels.md §1, §6 | aliases: quản lý nhãn, xóa tất cả nhãn, nhãn máy ngoại tuyến, nhãn thiết bị trong cài đặt, bao nhiêu nhãn | say_for: howto | say: Vào Cài đặt, thẻ "Nhãn thiết bị", chọn một máy để sửa hoặc xóa nhãn; menu "…" có Xóa tất cả. -->
Trong Cài đặt, thẻ "Nhãn thiết bị" mở danh sách mọi máy đã gắn nhãn, kể cả máy đang ngoại tuyến, lọc theo Tất cả / Đang kết nối / Ngoại tuyến. Chọn một máy để sửa hoặc xóa nhãn; menu "…" có Xóa tất cả (phải xác nhận). Nhãn gắn theo địa chỉ MAC và lưu trên router, tối đa 256 thiết bị. Điện thoại dùng "địa chỉ MAC riêng tư" có thể hiện như máy mới khi đổi MAC; khi đó nhãn cũ không theo.

## Đo tốc độ mạng
<!-- id: man.vi.speedtest | facts: man.speedtest | src: docs/speedtest.md; llm/core/README.md (Network check) | aliases: đo tốc độ, speed test, kiểm tra tốc độ, chất lượng mạng, đo mạng ở đâu, mạng nhanh không, tốc độ internet | say_for: howto | say: Vào Mạng → "Chất lượng mạng" và bấm đo, hoặc nói "Kiểm tra chất lượng mạng"; router đo khoảng 25 giây rồi hiện tải xuống, tải lên, ping và jitter. -->
Vào Mạng → "Chất lượng mạng" và bấm đo, hoặc nói "Hey iGate, kiểm tra chất lượng mạng". Router tự đo trong khoảng 25 giây và hiện tốc độ tải xuống, tải lên, độ trễ (ping) và độ dao động (jitter). Đây là tốc độ của đường Internet tới router, chưa tính chặng Wi-Fi tới điện thoại; điện thoại ở xa router có thể đạt thấp hơn. Hỏi lại "Kết quả đo tốc độ thế nào?" để nghe kết quả lần đo gần nhất.

## Xem lưu lượng theo giờ và theo dịch vụ
<!-- id: man.vi.traffic | facts: man.traffic | src: docs/traffic_analytics.md §1-2 | aliases: phân tích lưu lượng, lưu lượng, dùng bao nhiêu gb, giờ cao điểm, biểu đồ, thống kê mạng, 24 giờ, 7 ngày | say_for: howto | say: Mở "Phân tích lưu lượng" từ ô lưu lượng ở màn hình chính để xem biểu đồ 24 giờ hoặc 7 ngày và lưu lượng theo dịch vụ. -->
"Phân tích lưu lượng" (mở từ ô lưu lượng ở màn hình chính hoặc trong Mạng) có hai thẻ. Tổng quan: biểu đồ tải xuống/tải lên 24 giờ hoặc 7 ngày, giờ hoặc ngày cao điểm. Dịch vụ: lưu lượng tải xuống theo nhóm chơi game, xem video, gọi thoại, gọi video và khác. Phần theo dịch vụ là ước lượng theo loại thiết bị đang dùng gì, không phải đo từng ứng dụng.

## AI QoS: ai đang chơi game, gọi video, xem phim
<!-- id: man.vi.qos | facts: man.qos | src: docs/sec_qos_contract.md; esp32/main/ui/ui_showcase_slides.c (AI QoS page) | aliases: ai qos, ai đang chơi game, ai đang xem video, ưu tiên, thời gian chơi game, bật tắt ai qos, cài đặt ai, máy nào đang xem video, xem video ở màn nào | say_for: howto,define | say: Ô AI QoS ở màn hình chính cho biết thiết bị nào đang chơi game, gọi video hay xem video; bật hoặc tắt AI QoS ở "Cài đặt AI". -->
Ô AI QoS ở màn hình chính cho biết thiết bị nào đang chơi game, gọi video, gọi thoại hay xem video, và mỗi máy đã dùng bao lâu hôm nay hoặc 7 ngày. Router dùng thông tin này để ưu tiên đúng thiết bị khi mạng bận. Bật hoặc tắt AI QoS và AI Security ở "Cài đặt AI". Phân loại là của AI nên có lúc nhầm loại ứng dụng.

## AI Security: cảnh báo và chặn thiết bị
<!-- id: man.vi.security | facts: man.security | src: docs/ai_security_events.md §1 | aliases: ai security, cảnh báo bảo mật, sự kiện an ninh, bị tấn công, chặn thiết bị đáng ngờ, quét cổng, thiết bị nhiễm, cảnh báo nằm ở màn nào, màn cảnh báo, xem cảnh báo ở đâu | say_for: howto | say: Ô AI Security mở trang có ba thẻ Tổng quan, Sự kiện và Thiết bị; khi có cảnh báo, router hiện nút chặn thiết bị đó. -->
Ô AI Security mở trang có ba thẻ: Tổng quan (số sự kiện, mức độ cao, thiết bị bị đánh dấu trong 24 giờ hoặc 7 ngày), Sự kiện (từng sự kiện có giờ, thiết bị, mức độ, trạng thái) và Thiết bị (máy đang tấn công, bị tấn công, đã chặn). Khi có cảnh báo, router hiện thông báo và nút chặn thiết bị đó. Bảng trống chỉ có nghĩa là chưa ghi nhận gì, không chứng minh mạng an toàn tuyệt đối.

## Mạng khách và chia sẻ bằng QR
<!-- id: man.vi.guest | facts: man.guest | src: docs/voice_command_execution.md §2, §4; docs/json_command_protocol.md (guest_toggle) | aliases: wifi khách, mạng khách, bật wifi khách, chia sẻ wifi, mã qr, mật khẩu wifi khách, khách đến nhà, wifi cho khách | say_for: howto | say: Bật hoặc tắt mạng khách trong màn hình Wi-Fi, hoặc nói "Bật wifi khách 30 phút"; khi bật, màn hình hiện mã QR để khách quét. -->
Mạng khách cho khách dùng Internet mà không cần mật khẩu mạng chính. Bật hoặc tắt trong màn hình Wi-Fi, hoặc nói "Bật wifi khách", "Bật wifi khách 30 phút", "Tắt wifi khách". Khi bật, màn hình hiện mã QR để khách quét là vào; nếu có hẹn giờ thì ghi luôn giờ tự tắt. Bật hoặc tắt mạng khách làm Wi-Fi nạp lại khoảng 20 giây, các máy có thể rớt mạng ngắn rồi tự kết nối lại.

## Hẹn giờ và quản lý lịch
<!-- id: man.vi.schedules | facts: man.schedules | src: docs/schedule_settings.md; Router_App/router_display_src/LLM_JSON_CMD.md §5.12 | aliases: hẹn giờ, lập lịch, quản lý lập lịch, lịch chặn, xem lịch, hủy lịch, lịch hằng ngày, ngày trong tuần | say_for: howto | say: Nói lệnh kèm thời gian, ví dụ "Chặn mạng máy tính bảng của con từ 21 giờ đến 6 giờ"; xem lịch ở Cài đặt → "Quản lý lập lịch", hủy bằng "Hủy lịch số 3". -->
Có thể hẹn giờ cho chặn, mở mạng, giới hạn tốc độ, ưu tiên và mạng khách bằng giọng nói, ví dụ "Chặn mạng máy tính bảng của con từ 21 giờ đến 6 giờ các ngày trong tuần". Xem các lịch ở Cài đặt → "Quản lý lập lịch" (số lịch, việc, thiết bị, thời gian còn lại) hoặc hỏi "Danh sách lịch hẹn giờ"; hủy bằng "Hủy lịch số 3". Router giữ tối đa 8 lịch cùng lúc. Lịch theo giờ đồng hồ cần router đã có giờ đúng; lịch giờ đồng hồ được giữ qua khởi động lại.

## Cài đặt
<!-- id: man.vi.settings | facts: man.settings | src: docs/home_screen.md; docs/wallclock_schedules_timezone.md; docs/demo_mode.md | aliases: cài đặt, ngôn ngữ, đổi ngôn ngữ, múi giờ, đổi giờ, chế độ demo, tiếng anh, tiếng việt | say_for: define,howto | say: Màn Cài đặt có Ngôn ngữ, Múi giờ, Quản lý lập lịch, Nhãn thiết bị, Chế độ Demo, Cài đặt AI và thẻ "Dùng trên điện thoại". -->
Màn Cài đặt có: Ngôn ngữ (Tiếng Việt / English, đổi cả màn hình và trang web), Múi giờ (chọn tay hoặc tự dò qua Internet), Quản lý lập lịch, Nhãn thiết bị, Chế độ Demo (dữ liệu mô phỏng để trình diễn), Cài đặt AI (bật/tắt AI QoS, AI Security) và thẻ "Dùng trên điện thoại" có mã QR mở trang web của router.

## Dùng trên điện thoại hoặc máy tính
<!-- id: man.vi.phone | facts: man.phone | src: docs/web_panel_https.md §1; docs/web_voice_mic.md; Router_App/router_screen_src/README.md (Several people) | aliases: dùng trên điện thoại, dùng router trên điện thoại, dùng trợ lý trên điện thoại, trợ lý trên điện thoại, vnpt.internal, quét qr, trang web, mở trên máy tính, nói bằng điện thoại, mic điện thoại, nhiều người cùng xem | say_for: howto | say: Trên điện thoại hoặc máy tính trong mạng nhà, mở trình duyệt gõ vnpt.internal hoặc quét mã QR ở Cài đặt → "Dùng trên điện thoại". -->
Trên điện thoại hoặc máy tính đang nối mạng nhà, mở trình duyệt và gõ vnpt.internal, hoặc quét mã QR ở Cài đặt → "Dùng trên điện thoại". Trang web hiện đúng màn hình của router và thao tác như trên router. Có thể nói bằng mic của điện thoại: nhấn giữ nút nói, buông tay là xong (trên máy tính: chạm để bắt đầu). Tối đa 10 màn hình xem cùng lúc; người không điều khiển sẽ không thấy thông tin riêng như mật khẩu.

## Wi-Fi và các băng tần
<!-- id: man.vi.wifi | facts: man.wifi | src: esp32/main/ui_controller/wifi_overview_ctrl.c; docs/json_command_protocol.md §5.3 | aliases: cài đặt wifi, đổi tên wifi, đổi mật khẩu wifi, xem mật khẩu wifi, tắt băng 2.4, băng tần, ssid, tên mạng | say_for: howto | say: Vào Mạng → Wi-Fi để xem từng băng, tên mạng và số máy; tên mạng và mật khẩu đổi ở "Cài đặt Wi-Fi", iGate không đổi mật khẩu bằng giọng nói. -->
Trong Mạng → Wi-Fi bạn xem từng băng (2,4 GHz, 5 GHz, 6 GHz), tên mạng và số máy trên mỗi băng. Tên mạng và mật khẩu đổi ở "Cài đặt Wi-Fi"; bản trình diễn có thể khóa phần sửa này. Đổi cấu hình Wi-Fi làm router nạp lại Wi-Fi, các máy có thể rớt ngắn và phải kết nối lại bằng mật khẩu mới. iGate không đổi mật khẩu Wi-Fi bằng giọng nói và không đọc to mật khẩu.

## Trang Wi-Fi 6 · 7 · 8 và các tính năng Wi-Fi 8
<!-- id: man.vi.wifi8page | facts: man.wifi8page | src: docs/wifi_generations_compare.md; docs/demo_showcase.md (Wi-Fi 8 chapter) | aliases: trang wifi 8, so sánh wifi, tính năng wifi 8, npca, multi-ap, dso, imcs, ldpc, elr, dru, smd, xem minh họa | say_for: define,howto | say: Nút Wi-Fi 8 ở màn hình chính mở trang so sánh Wi-Fi 6, 7 và 8, cùng 8 trang minh họa các tính năng Wi-Fi 8. -->
Nút Wi-Fi 8 ở màn hình chính (hoặc Mạng → Wi-Fi 6·7·8) mở trang so sánh ba thế hệ: Wi-Fi 6 cho nhiều thiết bị cùng lúc, Wi-Fi 7 cho tốc độ, Wi-Fi 8 cho độ tin cậy. Thẻ Tính năng có 8 trang minh họa: NPCA, Multi-AP, DSO, iMCS, LDPC, ELR, DRU, SMD, mỗi trang so "Trước Wi-Fi 8" với "Với Wi-Fi 8". Đây là minh họa nguyên lý, không phải số đo của nhà bạn.

## Tour giới thiệu sản phẩm
<!-- id: man.vi.tour | facts: man.tour | src: docs/demo_showcase.md §2-3 | aliases: giới thiệu sản phẩm, tour, trình chiếu, xem giới thiệu, giới thiệu công ty, về vnpt, giới thiệu router | say_for: howto | say: Chạm vào logo ở màn hình chính để xem tour giới thiệu router, Wi-Fi 8, nền tảng AI Gateway và VNPT Technology. -->
Chạm vào logo ở màn hình chính để xem tour giới thiệu: các tính năng của router, Wi-Fi 8, nền tảng AI Gateway và công ty VNPT Technology. Màn "Giới thiệu" cũng có hai thẻ mở tour sản phẩm iGate A86-C và tour công ty. Dùng nút ‹ › để chuyển trang, nút Trang chủ để thoát; nút "Thử ngay" mở màn hình thật của tính năng đó. Khi bật Chế độ Demo, tour tự chạy nếu không ai chạm màn hình 90 giây.

## Chế độ Demo
<!-- id: man.vi.demo | facts: man.demo | src: docs/demo_mode.md §1-2 | aliases: chế độ demo, dữ liệu mô phỏng, demo là gì, tắt demo, nhãn demo, trình diễn | say_for: define,howto | say: Chế độ Demo trong Cài đặt cho router hiện một gia đình mô phỏng 12 thiết bị để trình diễn; tắt trong Cài đặt để quay về dữ liệu thật. -->
Chế độ Demo (trong Cài đặt) cho router hiện một gia đình mô phỏng gồm 12 thiết bị, có lưu lượng, AI QoS và AI Security, để trình diễn khi không có mạng thật. Mọi màn hình có số liệu đều mang nhãn DEMO, và iGate mở đầu câu trả lời bằng "Dữ liệu mô phỏng". Lệnh lên thiết bị mô phỏng không đụng tới mạng thật. Tắt Chế độ Demo trong Cài đặt để quay về dữ liệu thật.

## Wi-Fi Sensing (bản xem trước)
<!-- id: man.vi.sensing | facts: man.sensing | src: docs/wifi_sensing_preview.md §1-3 | aliases: wifi sensing, cảm biến wifi, phát hiện chuyển động, chăm sóc người già, phát hiện người, cảm biến không camera | say_for: define | say: Wi-Fi Sensing dùng sóng Wi-Fi để nhận biết chuyển động trong nhà; trên router hiện tại đây mới là bản xem trước với dữ liệu mô phỏng. -->
Wi-Fi Sensing dùng chính sóng Wi-Fi để nhận biết chuyển động trong nhà, không cần camera hay thiết bị đeo, hướng tới chăm sóc người lớn tuổi. Trên router hiện tại đây là bản xem trước: màn hình cho thấy tính năng sẽ làm gì bằng dữ liệu mô phỏng (khi bật Chế độ Demo), chưa phải số đo thật trong nhà bạn.

## Màn Giới thiệu và hỗ trợ
<!-- id: man.vi.about | facts: man.about | src: esp32/main/ui/ui_home_screens.c (About) | aliases: giới thiệu, about, thông tin router, liên hệ hỗ trợ, hỗ trợ ở đâu, phiên bản | say_for: define,howto | say: Màn "Giới thiệu" ghi tên router iGate A86-C, đơn vị phát triển, địa chỉ trang hỗ trợ và mã QR liên hệ. -->
Màn "Giới thiệu" ghi tên router iGate A86-C, đơn vị phát triển (Trung tâm Xuất sắc VNPT – Qualcomm, thuộc VNPT Technology), địa chỉ trang hỗ trợ và mã QR liên hệ, cùng hai thẻ mở tour sản phẩm và tour công ty.
