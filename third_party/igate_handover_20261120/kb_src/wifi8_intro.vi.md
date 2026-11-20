<!-- doc: wifi8_intro.vi | topic: wifi8_intro | lang: vi | as_of: 2026-10-29 | review: draft -->
# Wi-Fi 8 (IEEE 802.11bn, UHR) — giải thích dễ hiểu

## Wi-Fi 8 là gì
<!-- id: w8.vi.what | facts: w8.name, w8.goal | src: docs/wifi8_overview.md §1 | aliases: wifi 8 là gì, wi-fi 8, wifi8, 802.11bn, UHR, ultra high reliability | say_for: define | say: Wi-Fi 8 là chuẩn IEEE 802.11bn, tập trung vào tốc độ thực tế ổn định, độ tin cậy, độ trễ thấp và giữ kết nối liên tục, thay vì tốc độ đỉnh lớn hơn. -->
Wi-Fi 8 là chuẩn IEEE 802.11bn, còn gọi là UHR (Ultra High Reliability — độ tin cậy cực cao). Khác với các thế hệ trước vốn quảng bá tốc độ đỉnh lớn hơn, Wi-Fi 8 tập trung vào tốc độ thực tế ổn định, độ tin cậy, độ trễ thấp và giữ kết nối liên tục, nhất là ở nhà đông thiết bị, văn phòng, mạng mesh và ở rìa vùng phủ sóng. Tại thời điểm tài liệu nguồn được viết, 802.11bn vẫn là bản dự thảo.

## Wi-Fi 8 so với Wi-Fi 7
<!-- id: w8.vi.vs7 | facts: w8.peak, w8.new | src: docs/wifi8_overview.md §1-2 | aliases: wifi 8 khác wifi 7, so sánh wifi 7, tốc độ tối đa wifi 8, nhanh hơn không | say_for: compare | say: Tốc độ đỉnh của Wi-Fi 8 vẫn khoảng 23 Gbps như Wi-Fi 7; phần mới là phối hợp nhiều điểm phát, chuyển vùng liền mạch, dùng kênh linh hoạt khi có nhiễu và chế độ tầm xa. -->
Tốc độ đỉnh của Wi-Fi 8 vẫn khoảng 23 Gbps như Wi-Fi 7 (kênh 320 MHz, 8 luồng, 4096-QAM); tài liệu nguồn nhấn mạnh con số này không phải để quảng cáo. Phần mới nằm ở chỗ khác: phối hợp nhiều điểm phát (multi-AP), chuyển vùng liền mạch, dùng kênh linh hoạt khi có nhiễu (NPCA, DSO) và chế độ tầm xa (ELR). Vì vậy không nên kỳ vọng tải một tệp ngay cạnh router nhanh hơn Wi-Fi 7.

## Ba trải nghiệm mà Wi-Fi 8 nhắm tới
<!-- id: w8.vi.experience | facts: w8.experiences | src: docs/wifi8_overview.md §1 | aliases: lợi ích wifi 8, nhanh ổn định, tin cậy, luôn kết nối | say_for: define | say: Wi-Fi 8 nhắm tới ba trải nghiệm: nhanh và ổn định hơn, tin cậy hơn khi mạng bận, và luôn kết nối khi di chuyển. -->
Tài liệu nguồn chia các tính năng thành ba nhóm trải nghiệm: Nhanh — tốc độ thực tế cao và ổn định hơn chứ không chỉ con số đỉnh; Tin cậy — ít khựng, ít trễ, gọi video và chơi game ổn định hơn khi mạng bận; Luôn kết nối — vùng phủ rộng hơn, pin lâu hơn, không rớt khi di chuyển.

## Vùng xa router và chiều gửi từ điện thoại
<!-- id: w8.vi.uplink | facts: w8.dru, w8.elr | src: docs/wifi8_overview.md §3.1 | aliases: sóng yếu xa router, phòng xa, DRU, ELR, tầm xa, uplink | say_for: define | say: Ở xa router, router có thể không nghe rõ điện thoại; Wi-Fi 8 thêm DRU để thiết bị phát mạnh hơn và ELR là chế độ rất chậm nhưng đi rất xa. -->
Điện thoại phát yếu hơn router nên ở xa, router có thể không nghe rõ điện thoại dù điện thoại vẫn nghe được router. Wi-Fi 8 có hai cách cải thiện: DRU trải tín hiệu của thiết bị trên dải phổ rộng hơn để mỗi phần được phát mạnh hơn trong giới hạn cho phép; ELR là chế độ rất chậm nhưng đi rất xa, giữ kết nối qua tường ở tốc độ chỉ vài Mbit/s. Các mức cải thiện là số liệu của tài liệu hãng trong điều kiện thuận lợi.

## Khi mạng đông và bận
<!-- id: w8.vi.busy | facts: w8.npca, w8.dso, w8.latency | src: docs/wifi8_overview.md §3.2 | aliases: mạng đông, nhiều thiết bị, độ trễ thấp, gọi video ổn định, chơi game, NPCA, DSO | say_for: define | say: Khi mạng đông, NPCA cho thiết bị chuyển sang phần kênh còn trống và DSO cho router phục vụ nhiều thiết bị cùng lúc, giúp giảm độ trễ. -->
Khi hàng xóm chiếm kênh chính, NPCA cho thiết bị tạm chuyển sang phần kênh còn trống thay vì im lặng chờ; DSO cho router kênh rộng phục vụ nhiều thiết bị kênh hẹp cùng lúc. Các cơ chế ưu tiên cho phép gói tin khẩn (lệnh game, tiếng nói) chen trước một lần truyền dài và tách làn cho cuộc gọi, giúp giảm độ trễ lúc mạng bận. Hiệu quả thực tế phụ thuộc cả router lẫn thiết bị đều hỗ trợ.

## Nhiều điểm phát phối hợp và chuyển vùng liền mạch
<!-- id: w8.vi.mesh | facts: w8.mapc, w8.smd | src: docs/wifi8_overview.md §3.3 | aliases: mesh, nhiều router, multi-AP, chuyển vùng, roaming, đi lại trong nhà không rớt | say_for: define | say: Wi-Fi 8 cho các điểm phát phối hợp với nhau thay vì tranh nhau, và chuyển vùng liền mạch nên đi lại trong nhà ít bị ngắt; cần từ hai điểm phát trở lên. -->
Hiện nay các điểm phát gần nhau không phối hợp mà tranh nhau thời gian phát. Wi-Fi 8 đưa vào phối hợp nhiều điểm phát (MAPC): cùng giảm công suất để phát đồng thời, hướng sóng tránh thiết bị của nhau, hoặc chia lượt có bảo đảm. Chuyển vùng liền mạch (SMD) cho thiết bị gia nhập cả một "miền" điểm phát, nên khi đi lại trong nhà cuộc gọi và video ít bị ngắt. Lợi ích này chỉ có khi có từ hai điểm phát trở lên.

## Ví dụ trong gia đình và cửa hàng
<!-- id: w8.vi.examples | facts: w8.home | src: docs/wifi8_overview.md §4 | aliases: gia đình, cửa hàng, quán cà phê, văn phòng nhỏ, ứng dụng thực tế | say_for: define | say: Nhà nhiều tầng dùng mesh được lợi rõ nhất: phòng xa giữ kết nối tốt hơn và đi lại giữa các tầng ít rớt cuộc gọi. -->
Một ngôi nhà nhiều tầng dùng mesh có thể được lợi rõ nhất: phòng xa giữ kết nối tốt hơn và đi lại giữa các tầng ít rớt cuộc gọi. Một cửa hàng đông khách, nhiều thiết bị cùng dùng, có thể thấy mạng "bình tĩnh" hơn lúc cao điểm. Thiết bị IoT và điện thoại có thể tiết kiệm pin hơn nhờ chế độ nghe công suất thấp (DPS). Đây là khả năng của chuẩn, không phải cam kết về một sản phẩm cụ thể.

## Điều kiện và giới hạn
<!-- id: w8.vi.limits | facts: w8.limits, w8.both_ends | src: docs/wifi8_overview.md §4-5 | aliases: giới hạn wifi 8, điều kiện, cần thiết bị hỗ trợ, có cần đổi điện thoại | say_for: define,judge | say: Phần lớn tính năng Wi-Fi 8 cần cả router và thiết bị cùng hỗ trợ; điện thoại Wi-Fi 6/7 vẫn dùng được nhưng chỉ có lợi ích phía router. -->
Phần lớn tính năng cần cả hai đầu cùng hỗ trợ: router Wi-Fi 8 dùng với điện thoại Wi-Fi 6/7 vẫn hoạt động nhưng chỉ có lợi ích phía router. Một số tính năng có ràng buộc riêng, ví dụ phối hợp hướng sóng cần router nhiều anten, chuyển vùng liền mạch cần thiết bị đa liên kết và đường nối giữa các điểm phát. Các con số phần trăm là số liệu của hãng trong điều kiện thuận lợi, nên hiểu là "có thể lên tới".

## Wi-Fi 8 và router đang dùng
<!-- id: w8.vi.board | facts: w8.scope, prod.wifi8 | src: esp32/main/ui/ui_showcase_slides.c (cover); docs/wifi8_overview.md | aliases: router này có wifi 8 không, router này có phải wifi 8, đang bật wifi 8, tính năng router hiện tại, igate wifi 8 | say_for: define | say: Router đang dùng, iGate A86-C, là router Wi-Fi 8 (IEEE 802.11bn) ba băng 2,4/5/6 GHz. -->
Router đang dùng, iGate A86-C, là router Wi-Fi 8 (IEEE 802.11bn) ba băng 2,4/5/6 GHz. Phần trên là kiến thức chung về chuẩn: một tính năng cụ thể (ví dụ phối hợp nhiều điểm phát) có lợi hay không còn tùy thiết bị của bạn có hỗ trợ Wi-Fi 8 và nhà có nhiều điểm phát hay không. Trạng thái bật/tắt của từng tính năng không suy ra từ tài liệu giới thiệu này.
