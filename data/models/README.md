# Thư mục Trọng số Mô hình AI (data/models/)

Thư mục này lưu trữ các tệp trọng số mạng nơ-ron (ONNX weights) cho các động cơ AI chuyên sâu của EduQuest Pro.

## 1. Mô hình VietOCR ONNX (DeepDoc / Transformer Seq2Seq)
- **Tên tệp hỗ trợ**: `vietocr.onnx` hoặc `vietocr_onnx.onnx`
- **Nguồn mô hình**: Xuất từ dự án [pbcquoc/vietocr](https://github.com/pbcquoc/vietocr) hoặc [hoaivannguyen/deepdoc_vietocr](https://github.com/hoaivannguyen/deepdoc_vietocr)
- **Chức năng**: Nhận diện quang học tiếng Việt độ chính xác cao chạy hoàn toàn trên CPU thông qua `onnxruntime` mà không phụ thuộc vào PyTorch hay GPU.
- **Cơ chế Fallback tự động**: Khi chưa đặt tệp `vietocr.onnx` vào thư mục này, hệ thống sẽ tự động sử dụng **RapidOCR (PaddleOCR ONNX)** kết hợp **Bộ sửa lỗi Ngữ nghĩa Tự học (Active Lexicon Learning)**, đảm bảo nhận diện đầy đủ dấu thanh tiếng Việt và công thức toán học.
