# Quy Tắc Dự Án EduQuest Pro (Workspace Rules)

## 1. Tự Động Rebuild Docker Sau Khi Hoàn Thành Nhiệm Vụ (Post-Task Docker Rebuild)
- **Bắt buộc**: Mỗi khi hoàn tất một yêu cầu từ người dùng (thay đổi mã nguồn trong `frontend/`, `backend/`, chỉnh sửa tài nguyên tĩnh, sửa cấu hình hoặc cập nhật giao diện) và các bài kiểm thử đã vượt qua thành công:
  - Kiểm tra trạng thái Docker: Nếu container `eduquest-pro` đang chạy, AI **BẮT BUỘC** phải thực thi lệnh:
    ```powershell
    docker compose up -d --build
    ```
  - **Xác thực kết nối sau khi rebuild**: Kiểm tra `curl -I http://localhost:8000/api/stats/count` để đảm bảo container khởi động thành công (HTTP 200 OK) trước khi báo cáo hoàn thành cho User.

## 2. Quy Tắc Đánh Số Phiên Bản Chuẩn Quốc Tế (Semantic Versioning 2.0.0)

Mỗi khi thay đổi mã nguồn trong dự án (sửa lỗi, thêm tính năng, tái cấu trúc), AI **BẮT BUỘC** phải nâng số phiên bản theo chuẩn SemVer (`MAJOR.MINOR.PATCH`) trước khi rebuild Docker:

### 2.1. Phân định mức tăng phiên bản (SemVer Rules):
1. **Tăng số PATCH (`x.y.Z`)** (ví dụ: `1.2.3` ➔ `1.2.4`):
   - Áp dụng khi: Sửa lỗi (bug fix), vá lỗi cú pháp, chỉnh sửa giao diện nhỏ, cải thiện độ ổn định hoặc tối ưu hóa mà không làm thay đổi tính năng hay cấu trúc API.
2. **Tăng số MINOR (`x.Y.0`)** (ví dụ: `1.2.4` ➔ `1.3.0`):
   - Áp dụng khi: Bổ sung tính năng mới, tạo thêm module/công cụ mới, thêm endpoint API mới hoặc mở rộng chức năng mà vẫn đảm bảo tương thích ngược (backwards-compatible). Số PATCH được reset về `0`.
3. **Tăng số MAJOR (`X.0.0`)** (ví dụ: `1.3.0` ➔ `2.0.0`):
   - Áp dụng khi: Có thay đổi phá vỡ tương thích (breaking changes), thay đổi lớn về kiến trúc hệ thống, thay đổi API/Schema database không tương thích ngược. Cả số MINOR và PATCH được reset về `0`.

### 2.2. Các tệp bắt buộc đồng bộ phiên bản (Single Source of Truth):
- **Web Application (Backend & Frontend)**:
  - Cập nhật số phiên bản tại `backend/version.py`: `APP_VERSION`, `APP_VERSION_NUMBER`, `CACHE_BUSTER`.
  - Cập nhật tham số query cache-buster cho toàn bộ các script tại `frontend/index.html` (`<script src="js/...js?v=X.Y.Z"></script>`).
- **Chrome Extension**:
  - Khi có thay đổi mã nguồn trong thư mục `extension/`:
    - Cập nhật `"version": "X.Y.Z"` trong `extension/manifest.json`.
    - Cập nhật `EXT_VERSION` và `EXT_VERSION_NUMBER` trong `backend/version.py`.

## 3. Tự Động Git Commit & Push Sau Khi Hoàn Thành Nhiệm Vụ (Post-Task Git Commit & Push)
- **Bắt buộc**: Mỗi khi hoàn tất một yêu cầu từ người dùng, sau khi:
  1. Tất cả bài kiểm thử (`pytest`) đã vượt qua 100%.
  2. Số phiên bản đã được nâng chuẩn SemVer và đồng bộ qua tất cả các file liên quan.
  3. Container Docker `eduquest-pro` đã được rebuild và xác thực kết nối HTTP 200 OK.
- AI **BẮT BUỘC** phải tự động thực hiện chuỗi lệnh Git:
  ```powershell
  git add .
  git commit -m "<type>(<scope>): <mô tả ngắn gọn công việc> (vX.Y.Z / ext vA.B.C)"
  git push origin main
  ```
- **Quy chuẩn thông điệp commit (Conventional Commits)**:
  - `feat`: Thêm tính năng mới hoặc bộ cào mới (ví dụ: `feat(facebook): cào đề thi & ảnh Facebook qua extension (v1.2.5/ext 1.3.23)`).
  - `fix`: Sửa lỗi, vá giao diện, vá logic (ví dụ: `fix(auth): sửa lỗi đăng nhập và đồng bộ cache (v1.2.6)`).
  - `refactor`: Tái cấu trúc mã nguồn mà không đổi tính năng (ví dụ: `refactor(router): tách app.py thành modular routers`).
- Báo cáo kết quả mã băm commit (Commit SHA) và trạng thái push thành công cho User.

