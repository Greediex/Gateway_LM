<!-- doc: troubleshooting.vi | topic: troubleshooting | lang: vi | as_of: 2026-10-29 | review: draft -->
# Hướng dẫn kiểm tra không làm thay đổi cấu hình

## Một thiết bị chậm — bước 1: xem sóng của thiết bị đó
<!-- id: ts.vi.slow.s1 | runbook: slow_device | step: s1 | condition: chỉ một thiết bị chậm, các thiết bị khác bình thường | yes: s2 | no: s3 | src: Router_App/router_context_src/kb/src (biên soạn từ metric_glossary) | aliases: một máy chậm, thiết bị chậm, lag, giật, slow device | say_for: howto | say: Khi chỉ một thiết bị chậm, trước hết xem RSSI và tốc độ liên kết của máy đó; nếu RSSI yếu hơn khoảng −75 dBm, thử mang máy lại gần router. -->
Triệu chứng: chỉ một thiết bị chậm trong khi các máy khác vẫn ổn. Dữ kiện cần đọc: RSSI và tốc độ liên kết của thiết bị đó. Nếu RSSI yếu hơn khoảng −75 dBm hoặc tốc độ liên kết thấp hơn hẳn các máy khác, đi tiếp bước 2. Nếu sóng vẫn tốt, chuyển sang bước 3. Đây là hướng dẫn kiểm tra, không phải kết luận nguyên nhân.

## Một thiết bị chậm — bước 2: thử lại gần router
<!-- id: ts.vi.slow.s2 | runbook: slow_device | step: s2 | condition: sóng của thiết bị yếu | yes: s4 | no: s3 | src: Router_App/router_context_src/kb/src | aliases: lại gần router, di chuyển thiết bị, sóng yếu | say_for: howto | say: Mang thiết bị lại gần router hơn hoặc bỏ bớt vật cản, dùng lại vài phút rồi xem sóng có mạnh lên và hết chậm không. -->
Mang thiết bị lại gần router hơn (hoặc bỏ bớt vật cản như tường, tủ kim loại) rồi dùng lại trong vài phút. Quan sát lại: RSSI có mạnh lên và hiện tượng chậm có giảm không. Nếu cải thiện rõ, vị trí đặt là yếu tố đáng chú ý; có thể cân nhắc thiết bị phát sóng thêm. Nếu không cải thiện, chuyển bước 3. Sóng tốt hơn sau khi di chuyển chỉ là quan sát trước/sau, không tự chứng minh nguyên nhân duy nhất.

## Một thiết bị chậm — bước 3: kiểm tra phía thiết bị
<!-- id: ts.vi.slow.s3 | runbook: slow_device | step: s3 | condition: sóng tốt hoặc di chuyển không giúp | yes: s4 | no: s4 | src: Router_App/router_context_src/kb/src | aliases: kiểm tra điện thoại, tắt bật wifi trên máy, cập nhật ứng dụng | say_for: howto | say: Trên thiết bị đó, tắt rồi bật lại Wi-Fi, đóng các ứng dụng đang tải nền và thử ứng dụng khác; nếu chỉ một ứng dụng chậm thì có thể do dịch vụ đó. -->
Trên chính thiết bị đó: tắt rồi bật lại Wi-Fi của thiết bị, đóng các ứng dụng đang tải nền, thử một ứng dụng hoặc trang khác. Nếu chỉ một ứng dụng chậm còn các ứng dụng khác bình thường, vấn đề có thể nằm ở dịch vụ đó chứ không ở mạng nhà. Bước này không thay đổi gì trên router.

## Một thiết bị chậm — bước 4: khi nào cần hỗ trợ
<!-- id: ts.vi.slow.s4 | runbook: slow_device | step: s4 | escalate: 1 | src: Router_App/router_context_src/kb/src | aliases: gọi hỗ trợ, tổng đài, kỹ thuật viên | say_for: howto | say: Nếu vẫn chậm sau các bước trên, hãy liên hệ hỗ trợ kèm tên thiết bị, thời điểm chậm và những gì đã thử; đừng tự đặt lại router. -->
Nếu đã thử các bước trên mà thiết bị vẫn chậm kéo dài, hãy liên hệ bộ phận hỗ trợ và cho biết: tên thiết bị, thời điểm chậm, đã thử những gì và kết quả. Không tự đặt lại (reset) router khi chưa được hướng dẫn, vì sẽ mất cấu hình.

## Nhiều thiết bị cùng mất Internet — bước 1: xem trạng thái WAN
<!-- id: ts.vi.offline.s1 | runbook: all_offline | step: s1 | condition: nhiều thiết bị cùng không vào được Internet | yes: s2 | no: s3 | src: Router_App/router_context_src/kb/src | aliases: mất mạng, không vào được internet, cả nhà mất mạng, rớt mạng, offline | say_for: howto | say: Khi nhiều máy cùng mất Internet, trước hết xem trạng thái WAN: WAN mất kết nối thì kiểm tra dây và đèn, WAN có kết nối mà không vào được thì có thể lỗi phía nhà mạng. -->
Triệu chứng: nhiều thiết bị cùng lúc không vào được Internet. Dữ kiện cần đọc: trạng thái WAN và trạng thái Internet của router, cùng độ mới của dữ liệu. Nếu WAN đang down, đi bước 2. Nếu WAN up nhưng Internet lỗi, đi bước 3. Nếu dữ liệu đã cũ thì chưa thể kết luận; cần dữ liệu mới trước.

## Nhiều thiết bị cùng mất Internet — bước 2: kiểm tra dây và đèn
<!-- id: ts.vi.offline.s2 | runbook: all_offline | step: s2 | condition: WAN down | yes: s4 | no: s4 | src: Router_App/router_context_src/kb/src | aliases: dây mạng, cáp quang, đèn router, đèn los | say_for: howto | say: Kiểm tra dây từ thiết bị nhà mạng tới cổng WAN của router đã cắm chắc chưa và đèn trên thiết bị nhà mạng có báo lỗi không, rồi chờ vài phút. -->
Kiểm tra dây nối từ thiết bị của nhà mạng (modem/ONT) tới cổng WAN của router đã cắm chắc chưa, và đèn trên thiết bị nhà mạng có báo lỗi không (ví dụ đèn đỏ). Không tháo cáp quang nếu không được hướng dẫn. Sau khi cắm lại, chờ vài phút rồi xem WAN đã up chưa.

## Nhiều thiết bị cùng mất Internet — bước 3: WAN up nhưng không vào được
<!-- id: ts.vi.offline.s3 | runbook: all_offline | step: s3 | condition: WAN up nhưng Internet lỗi | yes: s4 | no: s4 | src: Router_App/router_context_src/kb/src | aliases: có mạng nhưng không vào được, lỗi dns, không truy cập được | say_for: howto | say: WAN có kết nối mà không vào được Internet thì sự cố có thể ở phía nhà mạng hoặc DNS; thử mở vài trang khác nhau trên hai thiết bị. -->
Khi cổng WAN có kết nối nhưng không ra được Internet, sự cố có thể ở phía nhà mạng hoặc ở phân giải tên miền (DNS). Thử mở vài trang khác nhau trên hai thiết bị. Router không tự đo DNS, nên không thể khẳng định DNS hỏng hay tốt chỉ từ cấu hình. Nếu vẫn lỗi, đi bước 4.

## Nhiều thiết bị cùng mất Internet — bước 4: báo nhà mạng
<!-- id: ts.vi.offline.s4 | runbook: all_offline | step: s4 | escalate: 1 | src: Router_App/router_context_src/kb/src | aliases: báo nhà mạng, tổng đài, hỗ trợ kỹ thuật | say_for: howto | say: Hãy báo nhà mạng thời điểm bắt đầu, WAN đang có kết nối hay không, đèn trên thiết bị nhà mạng và các bước đã thử. -->
Liên hệ nhà mạng và cung cấp: thời điểm bắt đầu, WAN đang up hay down, đèn trên thiết bị nhà mạng, các bước đã thử. Một lần ping tốt hay xấu tới một đích không đủ để kết luận lỗi thuộc về nhà mạng; hãy mô tả đúng điều đã quan sát.

## Wi-Fi chập chờn — bước 1: một máy hay nhiều máy
<!-- id: ts.vi.flaky.s1 | runbook: wifi_flaky | step: s1 | condition: Wi-Fi lúc được lúc mất | yes: s2 | no: s3 | src: Router_App/router_context_src/kb/src | aliases: chập chờn, lúc được lúc mất, rớt wifi, mất kết nối liên tục, flaky | say_for: howto | say: Khi Wi-Fi chập chờn, trước hết xác định chỉ một thiết bị bị hay nhiều thiết bị cùng bị. -->
Triệu chứng: kết nối Wi-Fi lúc có lúc mất. Xác định trước: chỉ một thiết bị bị (đi bước 2) hay nhiều thiết bị cùng bị (đi bước 3). Router chỉ thấy thay đổi qua các lần lấy mẫu, nên số lần mất kết nối nó báo có thể thiếu; đó là số quan sát được, không phải số đếm đầy đủ.

## Wi-Fi chập chờn — bước 2: một thiết bị
<!-- id: ts.vi.flaky.s2 | runbook: wifi_flaky | step: s2 | condition: chỉ một thiết bị chập chờn | yes: s4 | no: s4 | src: Router_App/router_context_src/kb/src | aliases: một máy rớt wifi, quên mạng, kết nối lại | say_for: howto | say: Nếu chỉ một thiết bị chập chờn, xem RSSI và SNR của máy đó, thử dùng gần router hơn hoặc quên mạng rồi kết nối lại. -->
Xem RSSI và SNR của thiết bị đó. Nếu sóng yếu, thử dùng gần router hơn. Trên thiết bị, có thể chọn "quên mạng" rồi kết nối lại bằng đúng mật khẩu. Ghi lại thời điểm bị mất để so với lịch sử của router.

## Wi-Fi chập chờn — bước 3: nhiều thiết bị
<!-- id: ts.vi.flaky.s3 | runbook: wifi_flaky | step: s3 | condition: nhiều thiết bị cùng chập chờn | yes: s4 | no: s4 | src: Router_App/router_context_src/kb/src | aliases: nhiều máy rớt wifi, nhiễu, kênh wifi | say_for: howto | say: Nếu nhiều máy cùng chập chờn, ghi lại thời điểm bị và xem số thiết bị trên mỗi băng tần. -->
Xem mức nhiễu của các băng tần và số thiết bị trên mỗi băng. Nếu nhiều máy cùng bị vào cùng một thời điểm, ghi lại thời điểm đó. Router hiện không đo mức chiếm dụng kênh hay số lần truyền lại, nên không thể khẳng định nguyên nhân là nhiễu từ hàng xóm.

## Wi-Fi chập chờn — bước 4: khi nào cần hỗ trợ
<!-- id: ts.vi.flaky.s4 | runbook: wifi_flaky | step: s4 | escalate: 1 | src: Router_App/router_context_src/kb/src | aliases: hỗ trợ, kỹ thuật viên | say_for: howto | say: Nếu vẫn chập chờn, liên hệ hỗ trợ kèm các thời điểm bị mất, thiết bị nào bị và những gì đã thử; đừng tự đổi kênh hay đặt lại router. -->
Nếu chập chờn vẫn tiếp diễn, liên hệ hỗ trợ kèm: các thời điểm bị mất, thiết bị nào bị, đã thử gì. Không tự đổi kênh hoặc đặt lại router khi chưa được hướng dẫn.

## Mạng khách — bước 1: mạng khách có đang bật không
<!-- id: ts.vi.guest.s1 | runbook: guest_network | step: s1 | condition: khách không kết nối được mạng khách | yes: s2 | no: s3 | src: docs/router_snapshot_yaml.md §6 (network guest) | aliases: mạng khách, wifi khách, guest, khách không vào được | say_for: howto | say: Trước hết xem mạng khách đang bật hay tắt; nếu đang tắt, chủ nhà có thể bật lại trên màn hình router. -->
Dữ kiện cần đọc: SSID nào là mạng khách (mạng có network là guest) và nó đang bật hay tắt. Nếu đang bật, đi bước 2. Nếu đang tắt, chủ nhà có thể bật lại qua ứng dụng hoặc màn hình của router (bước 3). Mật khẩu mạng khách không được đọc ra từ dữ liệu chung; dùng mã QR hoặc kênh mà chủ nhà cho phép.

## Mạng khách — bước 2: kiểm tra phía khách
<!-- id: ts.vi.guest.s2 | runbook: guest_network | step: s2 | condition: mạng khách đang bật | yes: s3 | no: s3 | src: Router_App/router_context_src/kb/src | aliases: nhập mật khẩu, quét mã qr, kết nối mạng khách | say_for: howto | say: Nhờ khách chọn đúng tên mạng khách, nhập lại mật khẩu hoặc quét mã QR của chủ nhà, và thử ở gần router. -->
Nhờ khách chọn đúng tên mạng khách, nhập lại mật khẩu (hoặc quét mã QR do chủ nhà cung cấp) và thử ở gần router. Nếu thiết bị cũ không hỗ trợ kiểu bảo mật của mạng, có thể không kết nối được; không tự hạ mức bảo mật để khắc phục.

## Mạng khách — bước 3: chủ nhà xử lý
<!-- id: ts.vi.guest.s3 | runbook: guest_network | step: s3 | escalate: 1 | src: Router_App/router_context_src/kb/src | aliases: chủ nhà, bật mạng khách | say_for: - | say: Bật, tắt mạng khách hay đổi mật khẩu là việc của chủ nhà và cần xác nhận; trợ lý chỉ hướng dẫn. -->
Việc bật/tắt mạng khách hoặc đổi mật khẩu là thao tác của chủ nhà và cần xác nhận. Trợ lý chỉ hướng dẫn; nó không tự bật mạng khách hay gửi mật khẩu cho người khác.
