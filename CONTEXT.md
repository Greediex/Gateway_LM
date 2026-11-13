# Gateway LM — Ngôn ngữ miền

Các khái niệm dùng khi thảo luận nền tảng lệnh và chẩn đoán mạng. Phân biệt khả năng thiết kế với khả năng thực sự được phép dùng trên một thiết bị.

## Language

**Feature**:
Tính năng người dùng sử dụng để giải quyết một nhu cầu mạng, có thể dựa trên nhiều năng lực và phép đo.
_Avoid_: Dùng Feature đồng nghĩa với một lệnh hoặc một Agent riêng.

**Workflow**:
Quy trình gắn các mục tiêu đo và điều kiện kết luận với một nhu cầu của người dùng.
_Avoid_: Dùng Workflow đồng nghĩa với mọi kế hoạch thực thi động.

**Skill**:
Nhóm năng lực nghiệp vụ có thể sử dụng nhiều Function và phục vụ nhiều Feature.
_Avoid_: Gọi Skill là một lệnh thiết bị.

**Function**:
Phép đo hoặc thao tác có hợp đồng input/output, phạm vi mục tiêu và điều kiện thực thi rõ ràng.
_Avoid_: Dùng Function đồng nghĩa với một shell command hoặc một output Port.

**Port**:
Hợp đồng cho một loại dữ liệu quan sát được tiêu thụ hoặc sinh ra bởi Function.
_Avoid_: Dùng Port đồng nghĩa với cổng TCP/UDP trong thảo luận contract.

**Adapter Binding**:
Ánh xạ một hợp đồng Function với triển khai backend trong phạm vi thiết bị đã xác định.
_Avoid_: Coi binding đã khai báo là bằng chứng backend hoạt động.

**Command Catalog**:
Tập khai báo các hợp đồng, quan hệ và triển khai ứng viên có thể dùng để tạo tập lệnh cho một ngữ cảnh vận hành.
_Avoid_: Gọi mọi mục trong catalog là lệnh thực thi được.

**Registry Snapshot**:
Tập hợp đồng đã chọn phiên bản và quan hệ nhất quán cho một ngữ cảnh vận hành.
_Avoid_: Dùng Catalog và Registry Snapshot thay thế cho nhau.

**Capability**:
Khả năng thực thi một Function được xác nhận cho backend và thiết bị trong ngữ cảnh cụ thể.
_Avoid_: Suy capability từ lifecycle IMPLEMENTED hoặc metadata VERIFIED toàn cục.

**Observation**:
Kết quả thu nhận từ một phép đo, còn cần kiểm tra trước khi dùng làm bằng chứng.
_Avoid_: Coi raw payload là Fact đã xác minh.

**Verified Fact**:
Dữ liệu đã qua kiểm tra hợp đồng, nguồn, mục tiêu và thời hạn để được sử dụng trong ngữ cảnh hiện tại.
_Avoid_: Coi một Fact còn đúng vô hạn hoặc đúng cho mọi thiết bị.

**Hypothesis**:
Giải thích ứng viên cần thêm bằng chứng để kiểm tra.
_Avoid_: Dùng hypothesis như root cause đã chứng minh.

**Claim**:
Mệnh đề cần được đánh giá theo điều kiện và bằng chứng đã xác minh để cho phép một kết luận.
_Avoid_: Coi hoàn thành phép đo là đã xác định nguyên nhân hoặc sửa xong sự cố.
