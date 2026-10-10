# Quy Tắc Dự Án EduQuest Pro (Workspace Rules)

## 1. Tự Động Rebuild Docker Sau Khi Hoàn Thành Nhiệm Vụ (Post-Task Docker Rebuild)
- **Bắt buộc**: Mỗi khi hoàn tất một yêu cầu từ người dùng (thay đổi mã nguồn trong `frontend/`, `backend/`, chỉnh sửa tài nguyên tĩnh, sửa cấu hình hoặc cập nhật giao diện) và các bài kiểm thử đã vượt qua thành công:
  - Kiểm tra trạng thái Docker: Nếu container `eduquest-pro` đang chạy, AI **BẮT BUỘC** phải thực thi lệnh:
    ```powershell
    docker compose up -d --build
    ```
  - **Xác thực kết nối sau khi rebuild**: Kiểm tra `curl -I http://localhost:8000/api/stats/count` để đảm bảo container khởi động thành công (HTTP 200 OK) trước khi báo cáo hoàn thành cho User.
