<!-- doc: metric_glossary.vi | topic: metric_glossary | lang: vi | as_of: 2026-10-29 | review: draft -->
# Ý nghĩa các chỉ số của router

## RSSI — cường độ tín hiệu Wi-Fi
<!-- id: mg.vi.rssi | facts: mg.rssi | src: docs/router_snapshot_yaml.md §3 (clients.rssi_dbm) | aliases: rssi, cường độ sóng, độ mạnh tín hiệu, signal strength, dBm | say_for: define | say: RSSI là mức tín hiệu Wi-Fi mà router nhận được từ một thiết bị, đo bằng dBm và luôn là số âm: càng gần 0 thì càng mạnh. -->
RSSI là mức tín hiệu Wi-Fi mà router nhận được từ một thiết bị, đo bằng dBm và luôn là số âm: càng gần 0 thì càng mạnh (ví dụ −50 dBm mạnh hơn −75 dBm). Đo được: sóng giữa thiết bị đó và router tại thời điểm lấy mẫu. Chưa kết luận được: RSSI yếu không tự chứng minh là nguyên nhân làm video giật hay mạng chậm; cần xem thêm tốc độ liên kết, mức nhiễu và những thiết bị khác. Thiết bị nối dây không có RSSI.

## SNR — tỷ lệ tín hiệu trên nhiễu
<!-- id: mg.vi.snr | facts: mg.snr | src: docs/router_snapshot_yaml.md §3 (clients.snr_db) | aliases: snr, tín hiệu trên nhiễu, nhiễu, noise | say_for: define | say: SNR là khoảng cách giữa tín hiệu của thiết bị và mức nhiễu nền, tính bằng dB; số càng lớn thì đường truyền càng sạch. -->
SNR là khoảng cách giữa tín hiệu của thiết bị và mức nhiễu nền, tính bằng dB; số càng lớn thì đường truyền càng sạch. Cùng một RSSI nhưng nhiễu cao hơn thì SNR thấp hơn và kết nối dễ chập chờn hơn. Đo được: chất lượng sóng tại router. Chưa kết luận được: nhiễu đến từ đâu (thiết bị nào, mạng hàng xóm nào), vì router không xuất thông tin đó.

## Tốc độ liên kết (link rate) không phải tốc độ Internet
<!-- id: mg.vi.link | facts: mg.link | src: docs/router_snapshot_yaml.md §6 | aliases: link rate, tốc độ liên kết, phy rate, link_mbps, tốc độ kết nối, máy hiện mbps cao mà tải chậm, tải không tới, wifi hiện bao nhiêu mbps | say_for: define,compare | say: Tốc độ liên kết là tốc độ vật lý mà thiết bị và router thỏa thuận qua sóng hoặc cáp; đó không phải tốc độ Internet. -->
Tốc độ liên kết là tốc độ vật lý mà thiết bị và router thỏa thuận qua sóng hoặc cáp, đo bằng Mbit/s. Nó cho biết đoạn đường giữa thiết bị và router có thể đạt tối đa bao nhiêu trong điều kiện hiện tại; đó không phải tốc độ tải thực tế và không phải tốc độ Internet. Con số máy hiện trong phần Wi-Fi, như 866, 1200, 2400 hay 5760 Mbps, là tốc độ liên kết; tải thực tế thường chỉ đạt một phần. Tốc độ Internet còn bị giới hạn bởi gói cước, đường WAN và máy chủ phía xa. Lưu ý đơn vị: Mbit/s (megabit) khác MB/s (megabyte); 8 Mbit/s ≈ 1 MB/s.

## Lưu lượng (throughput) đang dùng
<!-- id: mg.vi.throughput | facts: mg.throughput | src: docs/router_snapshot_yaml.md §6 (rx_mbps/tx_mbps) | aliases: lưu lượng, throughput, rx, tx, tải xuống, tải lên, băng thông đang dùng | say_for: define | say: Lưu lượng là lượng dữ liệu thực sự đi qua trong vài giây gần nhất; con số thấp chỉ có nghĩa là lúc đó ít ai tải, không cho biết mạng nhanh tới đâu. -->
Lưu lượng là lượng dữ liệu thực sự đi qua trong vài giây gần nhất, tính bằng Mbit/s từ bộ đếm byte của router: rx là chiều nhận, tx là chiều gửi, nhìn từ phía router. Con số thấp có thể chỉ có nghĩa là lúc đó không ai đang tải nhiều; nó không đo được mạng tối đa nhanh tới đâu. Muốn biết tốc độ tối đa cần một phép đo tốc độ riêng, router không tự chạy phép đo đó khi trả lời câu hỏi.

## Ping tới một đích
<!-- id: mg.vi.ping | facts: mg.ping | src: docs/router_snapshot_yaml.md §3 (wan.ping_ms) | aliases: ping, độ trễ, latency, ms, ping khác jitter, ping và jitter khác nhau | say_for: define | say: Ping là thời gian một gói tin đi tới một máy chủ đích và quay về, tính bằng mili giây; router chỉ đo tới một đích do nó chọn. -->
Ping là thời gian một gói tin đi tới một máy chủ đích và quay về, tính bằng mili giây. Router chỉ đo tới một đích do nó chọn, nên ping tốt nghĩa là đường tới đích đó đang tốt, chưa chứng minh mọi dịch vụ (game, video, ngân hàng) đều ổn. Độ dao động (jitter) chỉ có trong kết quả đo tốc độ; router không đo mất gói (packet loss). Khi không có số đo thì phải nói là chưa biết, không coi là bằng 0.

## Trạng thái WAN và Internet
<!-- id: mg.vi.wan | facts: mg.wan | src: docs/router_snapshot_yaml.md §3 (wan.up, wan.internet) | aliases: wan, internet, mất mạng, kết nối nhà mạng, up, down | say_for: define,compare | say: WAN là cổng nối router với nhà mạng; WAN có kết nối chưa chắc router đã vào được Internet. -->
WAN là cổng nối router với nhà mạng. "WAN up" nghĩa là cổng đã có kết nối; "internet" là router kiểm tra được đường ra Internet. Hai trạng thái này khác nhau: WAN có thể up nhưng Internet vẫn lỗi (ví dụ lỗi phía nhà mạng hoặc DNS). Máy chủ DNS cấu hình trên router chỉ là địa chỉ được đặt, không chứng minh DNS đang phân giải tên miền tốt.

## CPU, RAM và nhiệt độ của router
<!-- id: mg.vi.system | facts: mg.cpu, mg.ram, mg.temp | src: docs/router_snapshot_yaml.md §3 (sys) | aliases: cpu, ram, bộ nhớ, nhiệt độ, tải hệ thống, load | say_for: define | say: CPU là mức bận của bộ xử lý, RAM là phần bộ nhớ đang dùng, nhiệt độ lấy từ cảm biến của bo mạch; mức cao chỉ đáng chú ý khi kéo dài nhiều phút. -->
CPU (%) là mức bận của bộ xử lý, RAM (%) là phần bộ nhớ đang dùng, nhiệt độ (°C) lấy từ cảm biến của bo mạch nếu có. Một lần đo cao trong chốc lát là bình thường; đáng chú ý khi mức cao kéo dài nhiều phút. Nếu bo mạch không có cảm biến nhiệt thì router không báo nhiệt độ, và khi đó phải nói là không có dữ liệu chứ không đoán một con số. Một ngưỡng tham khảo không phải là chính sách tự tắt máy.

## Độ mới của dữ liệu
<!-- id: mg.vi.freshness | facts: mg.freshness | src: docs/router_snapshot_yaml.md §4 | aliases: dữ liệu cũ, độ mới, stale, cập nhật, thời gian dữ liệu | say_for: define | say: Router ghi trạng thái khoảng 2 giây một lần; nếu bản ghi đã cũ thì câu trả lời phải nói rõ là dữ liệu cũ. -->
Router ghi trạng thái khoảng 2 giây một lần. Mỗi câu trả lời dựa trên một bản ghi có tuổi riêng; nếu bản ghi đã cũ (ví dụ trong lúc đo tốc độ, router tạm ngừng cập nhật một số số liệu, hoặc router vừa khởi động lại) thì câu trả lời phải nói rõ là dữ liệu cũ. Một phần dữ liệu có thể mới trong khi phần khác cũ, nên không lấy thời điểm của cả tệp để coi mọi số liệu là vừa đo.

## Lớp QoS và thời gian sử dụng
<!-- id: mg.vi.qos | facts: mg.qos | src: docs/router_snapshot_yaml.md §3 (qos_today, qos_7d) | aliases: qos, chơi game, xem phim, thời gian dùng, ứng dụng, GAMING, VSTREAM | say_for: define | say: Router xếp thiết bị vào các lớp lưu lượng như chơi game, xem video, gọi thoại, gọi video; đó là lớp do bộ phân loại gán, không phải tên ứng dụng. -->
Router xếp thiết bị vào các lớp lưu lượng như GAMING (chơi game), VSTREAM (xem video), VOICE, VIDEOCALL. Đây là lớp mà bộ phân loại gán, không phải tên ứng dụng cụ thể; router không biết bạn đang xem trang nào. Thời gian sử dụng theo ngày/tuần là con số ước lượng. Khi router chưa có giờ thực, nó không đếm được "hôm nay", nên bảng trống lúc đó không có nghĩa là không ai dùng.

## Bảng cảnh báo bảo mật trống không có nghĩa là an toàn
<!-- id: mg.vi.security | facts: mg.security | src: docs/router_snapshot_yaml.md §5 | aliases: bảo mật, cảnh báo, tấn công, an toàn, security, feed | say_for: define,judge | say: Bảng cảnh báo bảo mật trống chỉ có nghĩa là chưa ghi nhận gì hoặc nguồn dữ liệu đang tắt, không chứng minh mạng an toàn. -->
Cảnh báo bảo mật đến từ một dịch vụ phân tích riêng. Nếu dịch vụ đó không chạy, danh sách cảnh báo sẽ trống nhưng điều đó chỉ có nghĩa là nguồn dữ liệu đang tắt, không phải mạng an toàn. Một cảnh báo cũng không tự chứng minh thiết bị đã bị xâm nhập; nó cho biết bộ phát hiện đã thấy một dấu hiệu theo quy tắc của nó.

## Ping bao nhiêu là tốt
<!-- id: mg.vi.ping_levels | facts: mg.ping_levels | src: Router_App/router_context_src/kb/src/activity_needs.vi.md (an.vi.game, an.vi.call); grades chosen 2026-11-10 (response-latency plan step 1E, user delegated) | aliases: ping bao nhiêu là tốt, ping cao hay thấp, độ trễ bao nhiêu là ổn, ping 100 ms có chậm không, mức ping, ping tốt | say_for: judge | say: Ping từ 50 ms trở xuống là tốt; 51 đến 100 ms là khá, vẫn chơi game và gọi video được; 101 đến 150 ms là yếu, dễ thấy trễ; trên 150 ms là kém. | judge: ping_ms <=50 tốt, <=100 khá, <=150 yếu, kém -->
Ping càng thấp càng tốt. Router chia bốn mức: từ 50 ms trở xuống là tốt, đủ cho cả game trực tuyến; 51 đến 100 ms khá, vẫn chơi game và gọi video được; 101 đến 150 ms yếu, dễ thấy trễ khi chơi game hay gọi video; trên 150 ms kém. Ping chỉ đo tới một đích nên mức tốt chưa chứng minh mọi dịch vụ đều ổn.

## Jitter bao nhiêu là tốt
<!-- id: mg.vi.jitter_levels | facts: mg.jitter_levels | src: docs/speedtest.md (jitter); grades chosen 2026-11-10 (response-latency plan step 1E, user delegated) | aliases: jitter bao nhiêu là tốt, jitter cao hay thấp, độ dao động bao nhiêu là ổn, mức jitter, jitter tốt | say_for: judge | say: Jitter từ 10 ms trở xuống là tốt; 11 đến 30 ms là khá; 31 đến 50 ms là yếu, gọi video và game dễ giật; trên 50 ms là kém. | judge: jitter_ms <=10 tốt, <=30 khá, <=50 yếu, kém -->
Jitter là độ dao động của ping, chỉ có trong lần kiểm tra chất lượng mạng; càng thấp càng tốt. Router chia bốn mức: từ 10 ms trở xuống là tốt; 11 đến 30 ms khá; 31 đến 50 ms yếu, gọi video và game dễ bị giật; trên 50 ms kém.
