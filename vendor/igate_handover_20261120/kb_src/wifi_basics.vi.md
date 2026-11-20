<!-- doc: wifi_basics.vi | topic: wifi_basics | lang: vi | as_of: 2026-11-08 | review: draft -->
# Kiến thức Wi-Fi cơ bản

## Băng 2,4 GHz, 5 GHz và 6 GHz khác nhau thế nào
<!-- id: wb.vi.bands | facts: wb.bands | src: docs/wifi_generations_compare.md; general: Wi-Fi band characteristics | aliases: 2.4ghz và 5ghz, 6ghz, băng tần nào tốt, nên dùng băng nào, khác nhau giữa các băng, băng 2.4 hay 5, wifi 5g là gì | say_for: define,compare | say: 2,4 GHz đi xa và xuyên tường tốt nhưng chậm và đông; 5 GHz nhanh hơn nhưng yếu nhanh qua tường; 6 GHz rất nhanh khi ở gần router nhưng tầm ngắn nhất. -->
2,4 GHz đi xa và xuyên tường tốt nhất nhưng chậm và đông, vì nhiều thiết bị và cả lò vi sóng, Bluetooth dùng chung. 5 GHz nhanh hơn nhiều, ít nhiễu hơn, nhưng yếu đi nhanh qua tường. 6 GHz (có từ Wi-Fi 6E trở lên) rộng và thoáng nhất, rất nhanh khi ở gần router, nhưng tầm ngắn nhất và chỉ máy đời mới dùng được. Lưu ý: "Wi-Fi 5G" thường là băng 5 GHz, không phải mạng di động 5G.

## Nên dùng băng nào cho thiết bị nào
<!-- id: wb.vi.choose | facts: wb.choose | src: general: Wi-Fi band characteristics | aliases: thiết bị nên dùng băng nào, camera dùng băng nào, đồ thông minh 2.4, tv nên dùng 5ghz, máy xa router, chọn băng, điện thoại nên bắt băng nào, nên bắt băng nào, nên kết nối băng nào, laptop nên dùng băng nào | say_for: judge,howto | say: Máy ở gần router và cần nhanh nên dùng 5 GHz hoặc 6 GHz; máy ở xa, sau nhiều tường, nên dùng 2,4 GHz hoặc 5 GHz tùy sóng. -->
Máy ở gần router và cần nhanh (TV xem 4K, máy chơi game, laptop) nên dùng 5 GHz hoặc 6 GHz. Máy ở xa, sau nhiều tường, nên dùng 2,4 GHz hoặc 5 GHz tùy sóng. Camera, ổ cắm, bóng đèn thông minh thường chỉ hỗ trợ 2,4 GHz, nên giữ băng 2,4 GHz bật. Khi router và thiết bị cùng hỗ trợ đa liên kết (MLO), thiết bị tự dùng nhiều băng cùng lúc.

## MLO (đa liên kết) là gì
<!-- id: wb.vi.mlo | facts: wb.mlo | src: docs/wifi8_features.md; docs/wifi_generations_compare.md | aliases: mlo, multi-link, đa liên kết, dùng nhiều băng cùng lúc, wifi 7 mlo | say_for: define | say: MLO (đa liên kết) có từ Wi-Fi 7: một thiết bị nối với router qua nhiều băng cùng lúc, nên nhanh hơn, ít trễ và ít rớt hơn. -->
MLO (Multi-Link Operation) có từ Wi-Fi 7: một thiết bị nối với router qua nhiều băng cùng lúc, ví dụ 5 GHz và 6 GHz. Lợi ích là nhanh hơn, ít trễ hơn và ít rớt hơn, vì khi một băng bận hoặc yếu, dữ liệu đi qua băng kia. Cần cả router và thiết bị cùng hỗ trợ.

## Wi-Fi 6, Wi-Fi 7 và Wi-Fi 8 khác nhau thế nào
<!-- id: wb.vi.gens | facts: wb.gens | src: docs/wifi_generations_compare.md §2; esp32/main/ui/ui_wifi_compare.c | aliases: wifi 6 wifi 7 wifi 8, so sánh các thế hệ wifi, khác nhau giữa wifi 6 và 7, thế hệ wifi, tốc độ tối đa từng chuẩn | say_for: compare | say: Wi-Fi 6 phục vụ nhiều thiết bị cùng lúc, Wi-Fi 7 dùng nhiều băng cùng lúc nên nhanh hơn, còn Wi-Fi 8 làm tốc độ thực tế ổn định hơn, ít rớt và ít giật. -->
Mỗi thế hệ mạnh ở một điểm: Wi-Fi 6 phục vụ nhiều thiết bị cùng lúc mà không chậm đi; Wi-Fi 7 dùng nhiều băng cùng lúc nên nhanh hơn và ít trễ; Wi-Fi 8 làm cho tốc độ thực tế ổn định hơn ở mọi phòng, ít rớt và ít giật. Tốc độ đỉnh lý thuyết của Wi-Fi 8 bằng Wi-Fi 7; đó là mức tối đa của chuẩn, không phải của một thiết bị (iGate A86-C: tới 11,5 Gbps).

## Thiết bị đời cũ có dùng được router Wi-Fi 8 không
<!-- id: wb.vi.compat | facts: wb.compat | src: esp32/main/ui/ui_wifi_compare.c | aliases: điện thoại cũ có kết nối được không, tương thích ngược, có cần đổi điện thoại, máy wifi 5, máy wifi 6 dùng wifi 8 | say_for: judge | say: Có. Thiết bị đời cũ vẫn kết nối router Wi-Fi 8 như trước; muốn có đủ lợi ích của Wi-Fi 8 thì thiết bị cũng phải hỗ trợ Wi-Fi 8. -->
Có. Điện thoại, laptop đời cũ (Wi-Fi 4, 5, 6, 7) vẫn kết nối router Wi-Fi 8 như trước. Thiết bị nhận được phần lợi ích ở phía router, nhưng muốn có đủ lợi ích của Wi-Fi 8 thì thiết bị cũng phải hỗ trợ Wi-Fi 8. Không cần đổi máy để dùng mạng.

## Cường độ sóng bao nhiêu là tốt
<!-- id: wb.vi.rssi_levels | facts: wb.rssi_levels | src: esp32/main/ui/ui_wifi_signal.h (signal grades, user 2026-11-10); Router_App/router_context_src/kb/src/metric_glossary.vi.md (mg.vi.rssi) | aliases: rssi bao nhiêu là tốt, sóng mạnh hay yếu, -70 dbm là tốt không, mức sóng, dbm bao nhiêu, rssi tốt, sóng yếu là bao nhiêu | say_for: judge | say: RSSI từ −55 dBm trở lên là tốt; −56 đến −70 là khá, đủ xem video; −71 đến −75 là yếu; dưới −75 là kém, dễ chậm hoặc rớt. | judge: rssi_dbm -55 tốt, -70 khá, -75 yếu, kém -->
RSSI tính bằng dBm, số âm, càng gần 0 càng mạnh. Router chia bốn mức, cùng màu với biểu tượng sóng trên màn hình: từ −55 dBm trở lên là tốt (xanh lá); −56 đến −70 khá, đủ cho xem video và gọi video (vàng); −71 đến −75 yếu, có thể chậm hoặc giật (cam); dưới −75 kém, dễ rớt (đỏ). Tốc độ thực còn phụ thuộc nhiễu, băng tần và thiết bị. Router đọc được 0 dBm nghĩa là không có số đo, không phải sóng mạnh.

## Đặt router ở đâu cho sóng tốt
<!-- id: wb.vi.placement | facts: wb.placement | src: general: Wi-Fi placement guidance; Router_App/router_context_src/kb/src/troubleshooting.vi.md (ts.vi.slow.s2) | aliases: đặt router ở đâu, vị trí router, sóng yếu phòng xa, router để chỗ nào, tăng sóng wifi, phủ sóng | say_for: howto,judge | say: Đặt router ở giữa nhà, cao ngang tầm ngực trở lên, thoáng, không để trong tủ, sau TV hay sát vật kim loại. -->
Đặt router ở giữa nhà, cao ngang tầm ngực trở lên, thoáng, không nhét trong tủ hay sau TV. Tránh để sát vật kim loại, gương lớn, bể cá, lò vi sóng. Mỗi bức tường, nhất là tường bê tông, và mỗi tầng nhà làm sóng yếu đi rõ rệt; 5 GHz và 6 GHz yếu nhanh hơn 2,4 GHz. Nhà nhiều tầng hoặc dài nên dùng thêm điểm phát (mesh).

## Nhiễu và kênh Wi-Fi đông
<!-- id: wb.vi.interference | facts: wb.interference | src: general: Wi-Fi interference; docs/wifi8_overview.md §3.2 | aliases: nhiễu wifi, hàng xóm làm nhiễu, kênh đông, wifi chậm buổi tối, nhiều mạng xung quanh, đổi kênh | say_for: define,howto | say: Wi-Fi hàng xóm, lò vi sóng và Bluetooth có thể gây nhiễu, nhất là ở 2,4 GHz; nên chuyển thiết bị quan trọng sang 5 GHz hoặc 6 GHz. -->
Wi-Fi của nhà hàng xóm, lò vi sóng, thiết bị Bluetooth cùng dùng sóng nên có thể làm mạng chậm hoặc giật, nhất là ở 2,4 GHz và vào buổi tối khi mọi nhà cùng dùng. Cách giảm: chuyển thiết bị quan trọng sang 5 GHz hoặc 6 GHz, đặt router xa nguồn nhiễu. Router tự chọn và đổi kênh khi thấy nhiễu, nên thỉnh thoảng thiết bị rớt vài giây rồi tự nối lại. Wi-Fi 8 có thêm cơ chế né phần kênh bận (NPCA).

## Địa chỉ MAC riêng tư (MAC ngẫu nhiên)
<!-- id: wb.vi.randommac | facts: wb.randommac | src: docs/device_labels.md §1; general: private Wi-Fi address on phones | aliases: mac ngẫu nhiên, địa chỉ riêng tư, private address, máy hiện là thiết bị mới, mất nhãn, chặn rồi vẫn vào được, đổi mac | say_for: define | say: Điện thoại đời mới thường dùng địa chỉ MAC riêng tư, đổi MAC theo mạng hoặc theo thời gian, nên router có thể thấy nó như thiết bị mới. -->
Điện thoại đời mới thường dùng "địa chỉ Wi-Fi riêng tư": mỗi mạng, hoặc sau một thời gian, máy dùng một địa chỉ MAC khác. Router nhận biết thiết bị theo MAC, nên khi MAC đổi máy hiện như thiết bị mới: nhãn, lệnh chặn hay giới hạn cũ không còn áp. Với mạng nhà, có thể tắt "địa chỉ riêng tư" cho riêng mạng này trong cài đặt Wi-Fi của điện thoại. Địa chỉ MAC có chữ số thứ hai là 2, 6, A hoặc E thường là địa chỉ tự đặt kiểu này.

## Tốc độ gói cước, tốc độ Wi-Fi và tốc độ thực
<!-- id: wb.vi.speeds | facts: wb.speeds | src: Router_App/router_context_src/kb/src/metric_glossary.vi.md (mg.vi.link); docs/speedtest.md | aliases: tốc độ gói cước, sao không đạt tốc độ gói, mbps và mb/s, tốc độ thực, wifi chậm hơn gói cước, đo trên điện thoại thấp hơn | say_for: compare | say: Có ba con số khác nhau: tốc độ gói cước, tốc độ đường Internet tới router và tốc độ Wi-Fi tới điện thoại; điện thoại thấy con số nhỏ nhất. -->
Có ba con số khác nhau: tốc độ gói cước (nhà mạng bán), tốc độ đường Internet tới router (router đo bằng "Kiểm tra chất lượng mạng") và tốc độ Wi-Fi giữa router và điện thoại (tùy sóng, băng, đời máy). Tốc độ bạn thấy trên điện thoại là con số nhỏ nhất trong chuỗi đó. Đơn vị: Mbps là megabit mỗi giây, MB/s là megabyte mỗi giây; 100 Mbps chỉ tải khoảng 12,5 MB/s.

## Khi nào cần thêm điểm phát (mesh)
<!-- id: wb.vi.mesh | facts: wb.mesh | src: docs/wifi8_overview.md §3.3; esp32/main/ui/ui_showcase_slides.c (coming soon page) | aliases: mesh, thêm cục phát, bộ kích sóng, nhà nhiều tầng, wifi không tới phòng xa, repeater | say_for: judge | say: Nếu nhà nhiều tầng hoặc tường dày mà có phòng sóng dưới khoảng −75 dBm dù router đặt giữa nhà, nên thêm điểm phát mesh, tốt nhất nối bằng dây. -->
Nếu nhà nhiều tầng, dài hoặc tường dày mà có phòng sóng dưới khoảng −75 dBm dù đã đặt router ở giữa nhà, nên thêm điểm phát (mesh) nối với router, tốt nhất nối bằng dây. Bộ kích sóng (repeater) loại rẻ thường làm giảm tốc độ. Chuyển vùng liền mạch giữa nhiều điểm phát của iGate đang trên lộ trình, chưa có trên router hiện tại.
