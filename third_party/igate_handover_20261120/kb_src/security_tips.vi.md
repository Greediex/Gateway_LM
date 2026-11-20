<!-- doc: security_tips.vi | topic: security_tips | lang: vi | as_of: 2026-11-08 | review: draft -->
# An toàn cho mạng nhà

## Mật khẩu Wi-Fi thế nào là mạnh
<!-- id: st.vi.password | facts: st.password | src: general: password guidance | aliases: mật khẩu wifi mạnh, mật khẩu dễ đoán, đặt mật khẩu wifi, mật khẩu an toàn, 12345678, mật khẩu bao nhiêu ký tự, đổi mật khẩu wifi | say_for: judge,howto | say: Mật khẩu Wi-Fi nên dài ít nhất 12 ký tự, có cả chữ và số; tránh dãy số liền, ngày sinh hay số điện thoại. -->
Mật khẩu Wi-Fi nên dài ít nhất 12 ký tự, có cả chữ và số, tốt nhất là một cụm từ dễ nhớ với bạn nhưng khó đoán với người khác. Tránh: dãy số liền (12345678), ngày sinh, số điện thoại, tên nhà hay tên mạng. Mật khẩu chỉ gồm số rất dễ bị dò. Đổi mật khẩu khi nghi có người lạ vào mạng; sau khi đổi, mọi thiết bị phải nhập lại.

## Các kiểu mã hóa Wi-Fi: WPA3, WPA2, mạng mở
<!-- id: st.vi.encryption | facts: st.encryption | src: general: Wi-Fi security modes; docs/json_command_protocol.md §5.3 (encryption values) | aliases: wpa3, wpa2, mã hóa wifi, bảo mật wifi, mạng không mật khẩu, mạng mở, sae, psk, mixed | say_for: compare,judge | say: WPA3 là kiểu mã hóa an toàn nhất hiện nay; WPA2 vẫn chấp nhận được nếu mật khẩu mạnh, còn mạng mở thì ai ở gần cũng vào được. -->
WPA3 (SAE) là kiểu an toàn nhất hiện nay và bắt buộc ở băng 6 GHz. WPA2 vẫn chấp nhận được nếu mật khẩu mạnh. Chế độ hỗn hợp WPA2/WPA3 cho máy cũ vẫn kết nối được. Mạng mở (không mật khẩu) thì ai ở gần cũng vào và có thể xem lưu lượng chưa mã hóa; chỉ nên dùng có chủ đích, ví dụ mạng khách có giới hạn thời gian.

## Dùng mạng khách cho khách và đồ thông minh
<!-- id: st.vi.guest | facts: st.guest | src: esp32/main/ui/ui_showcase_slides.c (Wi-Fi page); docs/voice_command_execution.md §4 | aliases: có nên dùng mạng khách, mạng khách có an toàn không, cách ly, khách thấy máy trong nhà không, wifi khách cho camera | say_for: howto,judge | say: Nên đưa khách vào mạng khách thay vì mạng chính: không phải đưa mật khẩu chính, có thể hẹn giờ tự tắt và chia sẻ bằng mã QR. -->
Đưa khách vào mạng khách thay vì mạng chính: bạn không phải đưa mật khẩu chính, có thể hẹn giờ tự tắt và chia sẻ bằng mã QR. Mạng khách được thiết kế để khách không thấy thiết bị trong nhà; mức cách ly thực tế phụ thuộc cấu hình của router, nên hỏi người quản lý mạng nếu cần chắc chắn. Tắt mạng khách khi không dùng.

## Mật khẩu quản trị router
<!-- id: st.vi.admin | facts: st.admin | src: docs/json_command_protocol.md §5.5 (set_password); general: router admin password | aliases: mật khẩu quản trị, mật khẩu admin, mật khẩu đăng nhập router, root, trang quản trị, có cần đặt mật khẩu router | say_for: define,judge | say: Router có mật khẩu quản trị riêng, khác mật khẩu Wi-Fi; hãy đặt mật khẩu quản trị mạnh từ 8 đến 128 ký tự. -->
Router có mật khẩu quản trị riêng, khác mật khẩu Wi-Fi, dùng để vào trang cấu hình. Nếu để trống hoặc dùng mật khẩu mặc định, bất kỳ ai trong mạng nhà cũng có thể đổi cấu hình router. Hãy đặt mật khẩu quản trị mạnh (8 đến 128 ký tự) và không dùng chung với mật khẩu Wi-Fi.

## NAT kép là gì
<!-- id: st.vi.nat | facts: st.nat | src: general: double NAT; Router_App/router_context_src/kb/src/metric_glossary.vi.md (mg.vi.wan) | aliases: nat kép, double nat, router sau modem, hai router, mở cổng không được, xem camera từ xa không được, chế độ bridge, địa chỉ wan nội bộ | say_for: define | say: NAT kép xảy ra khi router nằm sau một modem hoặc router khác cũng chia địa chỉ; Internet vẫn dùng được nhưng mở cổng, một số game và cuộc gọi có thể gặp khó. -->
NAT kép xảy ra khi router nằm sau một modem hoặc router khác cũng chia địa chỉ: địa chỉ WAN của router là địa chỉ nội bộ (bắt đầu bằng 192.168., 10. hoặc 172.16–31.). Internet vẫn dùng bình thường, nhưng mở cổng, xem camera từ xa, một số game và cuộc gọi có thể gặp khó. Cách khắc phục thường dùng là chuyển modem nhà mạng sang chế độ bridge để router này nhận địa chỉ trực tiếp.

## UPnP và mở cổng
<!-- id: st.vi.upnp | facts: st.upnp | src: general: UPnP and port forwarding | aliases: upnp, mở cổng, port forwarding, chuyển tiếp cổng, cổng mở ra internet, game yêu cầu mở cổng, nat strict | say_for: define,judge | say: Mở cổng cho phép kết nối từ Internet vào một máy trong nhà, còn UPnP cho thiết bị tự mở cổng; chỉ nên bật khi thật cần. -->
Mở cổng (port forwarding) cho phép kết nối từ Internet vào một máy trong nhà, ví dụ camera hay máy chủ game. UPnP cho phép thiết bị tự mở cổng mà không hỏi. Tiện nhưng có rủi ro: một thiết bị nhiễm mã độc cũng tự mở cổng được. Chỉ bật UPnP hoặc mở cổng khi thật cần, và đóng khi không dùng nữa.

## WPS nên bật hay tắt
<!-- id: st.vi.wps | facts: st.wps | src: general: WPS weaknesses | aliases: wps, nút wps, kết nối bằng nút, mã pin wps, có nên bật wps | say_for: judge,define | say: WPS cho thiết bị kết nối bằng nút bấm hoặc mã PIN thay vì gõ mật khẩu; tốt nhất để WPS tắt, vì kiểu dùng mã PIN có điểm yếu đã được biết rộng rãi. -->
WPS cho thiết bị kết nối bằng nút bấm hoặc mã PIN thay vì gõ mật khẩu. Kiểu dùng mã PIN đã có điểm yếu được biết rộng rãi, nên tốt nhất để WPS tắt và kết nối bằng mật khẩu hoặc mã QR.

## Camera và đồ thông minh
<!-- id: st.vi.iot | facts: st.iot | src: general: IoT security; esp32/main/ui/ui_showcase_slides.c (AI Security page) | aliases: camera an toàn không, camera bị hack, đồ thông minh, iot, mật khẩu mặc định camera, cập nhật camera | say_for: howto | say: Đổi mật khẩu mặc định của camera và đồ thông minh, cập nhật phần mềm của nó và tắt xem từ xa nếu không dùng. -->
Camera và đồ thông minh hay bị tấn công vì dùng mật khẩu mặc định và ít được cập nhật. Nên đổi mật khẩu mặc định của thiết bị, cập nhật ứng dụng và phần mềm của nó, tắt tính năng xem từ xa nếu không dùng. AI Security của router theo dõi các dấu hiệu như camera bị nhiễm hay quét cổng và báo trên màn hình.

## Thấy thiết bị lạ trong mạng thì làm gì
<!-- id: st.vi.unknown | facts: st.unknown | src: docs/device_labels.md §6; esp32/main/ui/ui_showcase_slides.c (AI Security page) | aliases: thiết bị lạ, máy lạ, ai đang dùng wifi nhà tôi, người lạ vào wifi, chặn máy lạ, có người dùng trộm wifi | say_for: howto | say: Trước hết xem đó có phải máy người nhà đổi MAC riêng tư không; nếu không biết là máy nào, chặn mạng máy đó rồi đổi mật khẩu Wi-Fi. -->
Trước hết kiểm tra xem đó có phải máy của người nhà đổi địa chỉ MAC riêng tư không (tên, loại máy, lúc vào mạng). Nếu là máy của mình, gắn nhãn để lần sau nhận ra. Nếu không biết là máy nào: chặn mạng máy đó ("Chặn mạng <tên máy>"), rồi đổi mật khẩu Wi-Fi để người lạ không vào lại được, vì chỉ chặn thì máy đổi MAC vẫn có thể vào lại.

## Cảnh báo của AI Security nghĩa là gì
<!-- id: st.vi.alerts | facts: st.alerts | src: docs/ai_security_events.md §1-2 | aliases: cảnh báo bảo mật nghĩa là gì, quét cổng là gì, ddos, bị tấn công, thiết bị nhiễm, sự kiện mức cao, có nguy hiểm không | say_for: define | say: Mỗi cảnh báo AI Security là một dấu hiệu cần kiểm tra, ví dụ quét cổng là một máy dò xem máy khác mở những cổng nào; cảnh báo chưa phải kết luận chắc chắn máy đó bị hack. -->
AI Security đặt tên cho từng sự kiện: quét cổng (một máy dò xem máy khác mở những cổng nào), tấn công từ chối dịch vụ (DDoS), xâm nhập, thiết bị nghi nhiễm mã độc, thiết bị mới vào mạng. Mức độ cao nghĩa là nên xử lý ngay: xem máy nào gây ra, chặn nếu không nhận ra, đổi mật khẩu Wi-Fi. Một cảnh báo là dấu hiệu cần kiểm tra, chưa phải kết luận chắc chắn máy đó bị hack.

## Cập nhật phần mềm router
<!-- id: st.vi.update | facts: st.update | src: general: firmware updates | aliases: cập nhật router, phần mềm router, firmware, phiên bản mới, có bản cập nhật không, nâng cấp router | say_for: howto,judge | say: Cập nhật phần mềm router giúp vá lỗ hổng bảo mật; nếu nhà cung cấp gửi bản cập nhật, hãy làm theo hướng dẫn của họ. -->
Cập nhật phần mềm router giúp vá lỗ hổng bảo mật và sửa lỗi. Router không tự biết có bản mới khi không có nguồn cập nhật; nếu bạn được nhà cung cấp gửi bản cập nhật, hãy làm theo hướng dẫn của họ. iGate không tự tải hay cài bản cập nhật.
