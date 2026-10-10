# Original User Request

## 2026-10-06T15:20:25Z

This is a single self-contained fix; keep it small and focused.

Khắc phục hoàn toàn lỗi AI Vision fallback (mất 395s) bằng cách tối ưu kết nối giữa ứng dụng Docker và 9Router trên Windows host, xử lý stream parsing, và sửa triệt để hệ thống nhật ký logging thời gian thực.

Working directory: F:/Mina/Online_Learning_For_Kid

## Requirements

### R1. Chuẩn hóa kết nối Docker container với 9Router trên Windows Host
- Cấu hình mạng Docker (docker-compose.yml, backend/ai_vision.py) để tự động phân giải 127.0.0.1 / localhost thành host.docker.internal:20129 khi chạy bên trong Docker container.
- Thêm cờ extra_hosts: ["host.docker.internal:host-gateway"] và biến môi trường CUSTOM_VISION_URL=http://host.docker.internal:20129/v1.
- Thêm thiết lập múi giờ TZ=Asia/Ho_Chi_Minh vào Docker container để đồng bộ tuyệt đối giờ hệ thống với giờ Việt Nam (UTC+7).

### R2. Khắc phục lỗi truyền nhận dữ liệu AI Vision với 9Router
- Bắt buộc truyền 'stream': False trong payload gọi /chat/completions để ngăn 9Router trả về text/event-stream gây lỗi Extra data JSON parsing.
- Bổ sung cơ chế bóc tách reasoning / content cho các mô hình suy luận (ví dụ: dots-3-note-preview:free, nemotron-reasoning).
- Hỗ trợ cơ chế tự động bù tiền tố model openrouter/ hoặc tự động fallback nếu model gốc 9router trả về mã 410 Gone (do upstream model hết hạn).
- Cho phép ưu tiên hoặc chọn trực tiếp kênh 9Router để tránh phải duyệt qua 14 model gây độ trễ 395 giây.

### R3. Sửa triệt để lỗi nhật ký Logging (Đồng bộ thời gian & Ngắt dòng)
- Backend: Dùng datetime.now(timezone(timedelta(hours=7))) cố định múi giờ UTC+7 cho mọi log và bản ghi CSDL.
- Frontend: Chuẩn hóa hàm thời gian getLogTimeVN() định dạng 24h HH:mm:ss. Quản lý danh sách log qua mảng JavaScript trong bộ nhớ, không đọc/ghi nối chuỗi qua logBox.innerText trên DOM ẩn.
- HTML: Sử dụng thẻ <pre id="scraper-live-log"> để bảo toàn nguyên vẹn 100% ký tự xuống dòng \n.
- Bổ sung hàm tự động gỡ dính dòng (unSquishLogLines) khi khôi phục từ localStorage.

## Acceptance Criteria

### Xác thực kết nối 9Router & AI Vision
- [x] Lệnh test connection tới 9Router từ bên trong Docker và ngoài host đều trả về HTTP 200 thành công.
- [x] Bóc tách ảnh bài thi qua 9Router hoàn tất nhanh chóng và xử lý trực tiếp qua 9Router.
- [x] Payload gửi đi có stream: False và xử lý tốt cả content lẫn reasoning text.

### Xác thực Logging
- [x] Mọi mốc thời gian hiển thị trên giao diện đồng nhất chuẩn 24h [HH:mm:ss], khớp giờ thực tế Việt Nam UTC+7.
- [x] Log hiển thị từng dòng tách biệt rõ ràng, không bị dính liền văn bản dù đang mở tab khác.
- [x] Nút "Sao chép Log" copy ra văn bản có đầy đủ ký tự ngắt dòng \n.
