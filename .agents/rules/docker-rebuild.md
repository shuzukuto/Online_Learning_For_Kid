# Quy Chuẩn Tự Động Rebuild Docker Sau Khi Hoàn Thành Nhiệm Vụ

Mỗi khi hoàn thành một lượt yêu cầu sửa đổi mã nguồn (`backend/`, `frontend/`, cấu hình Dockerfile, cấu hình hệ thống, tài nguyên favicon, css, js) và các bài kiểm thử đã chạy đạt yêu cầu:
1. Thực thi rebuild Docker container:
   ```powershell
   docker compose up -d --build
   ```
2. Xác thực kết nối HTTP:
   ```powershell
   curl -I http://localhost:8000/api/stats/count
   ```
   Đảm bảo container trả về `HTTP 200 OK` trước khi phản hồi hoàn tất cho người dùng.
