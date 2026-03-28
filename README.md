# 🌸 UED Calculate Grade!

> **Hệ thống quản lý điểm số thông minh dành cho sinh viên Đại học Đà Nẵng**  
> Quét ảnh bảng điểm tự động · Tính GPA · Mô phỏng "What If" · Gợi ý môn học lại

---

## 📋 Mục lục

- [Tổng quan hệ thống](#-tổng-quan-hệ-thống)
- [Tính năng chính](#-tính-năng-chính)
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
- [Yêu cầu cài đặt](#-yêu-cầu-cài-đặt)
- [Hướng dẫn cài đặt](#-hướng-dẫn-cài-đặt)
- [Cấu hình hệ thống](#-cấu-hình-hệ-thống)
- [Cách sử dụng](#-cách-sử-dụng)
- [API Reference](#-api-reference)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Xử lý lỗi thường gặp](#-xử-lý-lỗi-thường-gặp)

---

## 🎯 Tổng quan hệ thống

**UED Calculate Grade** là ứng dụng web được xây dựng bằng **Flask (Python)**, có khả năng:

1. **Quét ảnh bảng điểm** tự động bằng công nghệ OCR Hybrid (kết hợp Tesseract cục bộ + Google Cloud Vision API)
2. **Tự động nhận diện và khớp tên môn học** từ cơ sở dữ liệu SQL Server
3. **Tính GPA** theo thang hệ 4 và hệ 10
4. **Mô phỏng điểm số** (What-If Simulation) để sinh viên lên kế hoạch học tập
5. **Gợi ý môn học lại** có tác động cao nhất đến GPA

---

## ✨ Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| 📸 **OCR Ảnh Máy Tính** | Dùng Tesseract (Local) để quét ảnh bảng điểm chụp từ cổng thông tin portal |
| ✍️ **OCR Chữ Viết Tay** | Dùng Google Cloud Vision API để quét ảnh bảng điểm viết tay |
| 🔍 **Fuzzy Matching** | Tự động sửa và khớp tên môn học với độ tương đồng OCR |
| 📊 **Tính GPA thời gian thực** | Hiển thị GPA Hiện Tại, GPA Giả Lập và Chênh lệch |
| 🎮 **Mô phỏng "What If"** | Thay đổi điểm số để xem GPA thay đổi như thế nào |
| 🎓 **Tính lộ trình ra trường** | Tính GPA cần đạt cho các tín chỉ còn lại để đạt mục tiêu |
| 📝 **Tính Điểm Rèn Luyện** | Tính ĐRL kỳ 2 cần thiết dựa trên mục tiêu và ĐRL kỳ 1 |
| 💡 **Gợi ý môn học lại** | Xếp hạng các môn có điểm thấp theo mức tác động đến GPA |
| 🔎 **Autocomplete tên môn** | Gợi ý tên môn học từ DB khi nhập thủ công |

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────┐
│                  FRONTEND (Browser)                  │
│  HTML (index.html) + CSS (style.css) + JS (script.js)│
│  - localStorage để lưu bảng điểm phía client         │
│  - Gọi API Flask qua fetch()                          │
└────────────────────┬────────────────────────────────┘
                     │ HTTP Request
┌────────────────────▼────────────────────────────────┐
│               BACKEND (Flask - LocalOCR.py)          │
│  - Route /        → Serve trang HTML chính           │
│  - Route /api/search_subject → Tìm kiếm môn học      │
│  - Route /api/process_ocr    → Xử lý ảnh OCR         │
└──────┬──────────────────────────────────┬────────────┘
       │                                  │
┌──────▼──────┐                  ┌────────▼──────────┐
│  SQL Server │                  │   OCR Engine      │
│  OCR_Grade  │                  │                   │
│  - danh_muc_│                  │ Mode 1: Tesseract  │
│    mon      │                  │  (Ảnh máy tính)   │
│  - ten_mon  │                  │                   │
│  - tin_chi  │                  │ Mode 2: Google    │
└─────────────┘                  │  Cloud Vision API │
                                 │  (Chữ viết tay)   │
                                 └───────────────────┘
```

### Quy trình xử lý OCR

```
Ảnh Upload
    │
    ▼
[Chọn Mode]
    │
    ├── Computer Mode ──→ Tesseract Local OCR
    │                         │
    │                    Preprocessing (OpenCV)
    │                         │
    │                    Grayscale + Resize 2x
    │                         │
    │                    Otsu Thresholding
    │                         │
    │                    Trích xuất từ + tọa độ (x,y)
    │
    └── Handwriting Mode ──→ Google Cloud Vision API
                                  │
                             document_text_detection
                                  │
                             Trích xuất từ + bbox
    │
    ▼
Reconstruct Lines (Gom dòng theo tọa độ Y)
    │
    ▼
Parse Lines (Regex để trích xuất: Tên Môn | Tín Chỉ | Điểm)
    │
    ▼
Fuzzy Matching với DB (SequenceMatcher)
    │
    ▼
Quy đổi điểm Hệ 10 → Hệ 4
    │
    ▼
Trả về JSON → Frontend render vào bảng
```

---

## 📦 Yêu cầu cài đặt

### Phần mềm bắt buộc

| Phần mềm | Phiên bản | Link |
|----------|-----------|------|
| Python | ≥ 3.9 | [python.org](https://python.org) |
| Tesseract OCR | ≥ 5.x | [github.com/UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) |
| SQL Server | 2017+ | [microsoft.com](https://www.microsoft.com/sql-server) |
| ODBC Driver 17 | | [microsoft.com](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |

### Thư viện Python

```bash
pip install flask
pip install werkzeug
pip install pyodbc
pip install opencv-python
pip install pytesseract
pip install numpy
pip install google-cloud-vision
```

> **Lưu ý:** File `LocalOCR.py` là file chính cần chạy. File `app2.py` là phiên bản cũ chỉ dùng Google Vision (không có Tesseract local).

---

## 🚀 Hướng dẫn cài đặt

### Bước 1: Cài Tesseract OCR

1. Tải Tesseract về từ: https://github.com/UB-Mannheim/tesseract/wiki
2. Cài đặt và ghi nhớ đường dẫn cài đặt (mặc định: `C:\Program Files\Tesseract-OCR\tesseract.exe`)
3. **Quan trọng:** Phải cài thêm gói ngôn ngữ `Tiếng Việt (vie)` khi cài đặt

### Bước 2: Cài đặt Python Libraries

```bash
# Tạo môi trường ảo (khuyến nghị)
python -m venv .venv
.venv\Scripts\activate

# Cài đặt thư viện
pip install flask werkzeug pyodbc opencv-python pytesseract numpy google-cloud-vision
```

### Bước 3: Cấu hình SQL Server

1. Mở **SQL Server Management Studio (SSMS)**
2. Tạo database mới tên `OCR_Grade`
3. Tạo bảng `danh_muc_mon` với cấu trúc sau:

```sql
CREATE TABLE danh_muc_mon (
    id        INT IDENTITY(1,1) PRIMARY KEY,
    ten_mon   NVARCHAR(200) NOT NULL,
    tin_chi   INT NOT NULL
);
```

4. Nhập danh sách môn học của trường vào bảng này

### Bước 4: Cấu hình Google Cloud Vision API

1. Truy cập [Google Cloud Console](https://console.cloud.google.com/)
2. Tạo project mới → Bật API **Cloud Vision API**
3. Tạo **Service Account** → Tải file JSON credentials về
4. Đổi tên file thành `key.json` và đặt vào thư mục dự án:
   ```
   D:\Python_Code\AI_Project\App_Python\key.json
   ```

### Bước 5: Khởi động ứng dụng

```bash
# Kích hoạt môi trường ảo (nếu chưa)
.venv\Scripts\activate

# Chạy server Flask
python LocalOCR.py
```

Mở trình duyệt và truy cập: **http://127.0.0.1:5000**

---

## ⚙️ Cấu hình hệ thống

Mở file `LocalOCR.py` và chỉnh sửa các dòng sau:

### 1. Đường dẫn Tesseract

```python
# Dòng 22 - Thay bằng đường dẫn thực tế trên máy bạn
pytesseract.pytesseract.tesseract_cmd = r'D:\OCR\tesseract.exe'

# Ví dụ các đường dẫn phổ biến:
# r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# r'C:\Users\<TenBan>\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
```

### 2. Đường dẫn Google API Key

```python
# Dòng 25 - Thay bằng đường dẫn file key.json của bạn
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"D:\Python_Code\AI_Project\App_Python\key.json"
```

### 3. Thông tin kết nối SQL Server

```python
# Dòng 28 - Thay thông tin database của bạn
DB_CONFIG = {
    'DRIVER': '{ODBC Driver 17 for SQL Server}',
    'SERVER': 'localhost',         # Tên hoặc IP SQL Server
    'DATABASE': 'OCR_Grade',       # Tên database
    'UID': 'sa',                   # Username
    'PWD': '1'                     # Password (⚠️ Thay bằng mật khẩu thực!)
}
```

---

## 📖 Cách sử dụng

### 1. Nhập môn học thủ công

![Nhập thủ công](docs/manual_input.png)

1. Gõ **tên môn học** vào ô "Tên môn học" → Hệ thống tự gợi ý từ database
2. Chọn **số tín chỉ** (1-4)
3. Nhập **điểm hệ 10** → Hệ 4 tự động quy đổi
4. Nhấn nút **`+`** để thêm vào bảng điểm

> 💡 **Mẹo:** Hệ thống tự động gợi ý tên môn và số tín chỉ khi bạn gõ từ 2 ký tự trở lên!

### 2. Quét ảnh bảng điểm bằng OCR

**Chế độ A - Ảnh Portal (Máy tính):**
- Dùng cho ảnh chụp màn hình/chụp lại từ website cổng thông tin sinh viên
- Sử dụng Tesseract OCR (không cần Internet)
- Độ chính xác cao với chữ in ấn rõ ràng

**Chế độ B - Ảnh Viết Tay:**
- Dùng cho ảnh chụp bảng điểm viết tay (phiếu điểm, sổ điểm)
- Sử dụng Google Cloud Vision API (cần Internet + API Key)
- Xử lý tốt chữ viết tay phức tạp

**Các bước thực hiện:**
1. Chọn chế độ OCR phù hợp (`Ảnh Portal` hoặc `Ảnh Viết Tay`)
2. Nhấn **Chọn file** và chọn ảnh bảng điểm
3. Nhấn **⚡ Quét Ngay**
4. Chờ xử lý → Các môn học được nhận diện tự động thêm vào bảng

> ⚠️ **Lưu ý:** Sau khi quét OCR, hãy kiểm tra lại danh sách môn học vì OCR đôi khi có thể đọc sai. Bạn có thể xóa môn sai và thêm lại thủ công.

### 3. Đọc bảng điểm

| Cột | Ý nghĩa |
|-----|---------|
| **Môn học** | Tên môn + badge % độ tương đồng (nếu quét OCR) |
| **TC** | Số tín chỉ |
| **Điểm** | Điểm hệ 4 hiện tại (badge màu sắc) |
| **Giả Lập** | Dropdown chọn điểm giả lập |
| **Xóa** | Xóa môn khỏi bảng |

**Màu sắc badge điểm:**
- 🟢 **A+, A** → Xuất sắc/Giỏi
- 🔵 **B+, B** → Khá
- 🟡 **C+, C** → Trung Bình Khá / Trung Bình
- 🟠 **D+, D** → Yếu
- 🔴 **F** → Không đạt

### 4. Mô phỏng GPA (What-If)

1. Trong cột **Giả Lập**, chọn điểm mong muốn cho bất kỳ môn nào
2. Quan sát thẻ **GPA GIẢ LẬP** cập nhật ngay lập tức
3. Thẻ **ĐỘ CHÊNH LỆCH** hiển thị GPA tăng (xanh) hoặc giảm (đỏ)
4. Nhấn **🔄 Reset Giả lập** để hoàn tác tất cả thay đổi

### 5. Tính lộ trình ra trường

1. Nhập **Tổng tín chỉ quy định** (mặc định: 130 TC cho UED)
2. Chọn **Mục tiêu Xếp loại** (Xuất Sắc/Giỏi/Khá)
3. Nhấn **🚀 Tính toán**
4. Hệ thống tính GPA trung bình cần đạt cho các tín chỉ còn lại

### 6. Tính Điểm Rèn Luyện (ĐRL)

1. Chọn **Mục tiêu cả năm** (Xuất sắc/Tốt/Khá/TB Khá)
2. Nhập **Điểm ĐRL Kỳ 1** đã biết
3. Nhấn **Tính toán ĐRL**
4. Hệ thống tính điểm ĐRL Kỳ 2 cần đạt

> 📌 **Công thức:** `ĐRL_Kỳ2 = (Mục_tiêu × 2) - ĐRL_Kỳ1`

### 7. Gợi ý môn học lại

Ô **"Nên học lại môn nào?"** tự động phân tích:
- Lọc các môn có điểm < B (tức là < 3.0 hệ 4)
- Sắp xếp theo **mức tác động đến GPA** (môn nhiều tín + điểm thấp → ưu tiên cao)
- Nhấn vào một gợi ý để tự động giả lập môn đó lên A+

---

## 🔌 API Reference

### GET `/api/search_subject`

Tìm kiếm môn học trong database theo tên.

**Parameters:**

| Tham số | Kiểu | Mô tả |
|---------|------|-------|
| `q` | string | Từ khóa tìm kiếm (tối thiểu 2 ký tự) |

**Response:**
```json
[
    { "ten_mon": "Cơ sở dữ liệu", "tin_chi": 3 },
    { "ten_mon": "Cơ sở lập trình", "tin_chi": 3 }
]
```

---

### POST `/api/process_ocr`

Xử lý ảnh bảng điểm bằng OCR và trả về danh sách môn học.

**Form Data:**

| Tham số | Kiểu | Mô tả |
|---------|------|-------|
| `file_anh` | file | File ảnh (jpg, png, jpeg, ...) |
| `mode` | string | `"computer"` hoặc `"handwriting"` |

**Response thành công:**
```json
{
    "success": true,
    "data": [
        {
            "raw_name": "Co so du lieu",
            "ten_mon": "Cơ sở dữ liệu",
            "percentage": "87%",
            "tin_chi": 3,
            "diem_he_4": "A"
        }
    ]
}
```

**Response lỗi:**
```json
{
    "success": false,
    "error": "Mô tả lỗi..."
}
```

---

## 📁 Cấu trúc thư mục

```
App_Python/
│
├── LocalOCR.py          ⭐ File chính - Server Flask (Hybrid OCR)
├── app2.py              📦 Phiên bản cũ - Chỉ dùng Google Vision
├── app.py               📦 Phiên bản thử nghiệm cũ
├── key.json             🔑 Google Cloud API Key (KHÔNG share lên git!)
├── water_stock.db       🗃️ File SQLite dự phòng (không dùng chính)
│
├── templates/
│   ├── index.html       🌐 Giao diện chính (Bootstrap 5 + FontAwesome)
│   └── index_ban_cu.html  📄 Phiên bản giao diện cũ
│
├── static/
│   ├── style.css        🎨 CSS tùy chỉnh
│   └── script.js        ⚡ Logic frontend (GPA, OCR, Simulation)
│
├── uploads/             📂 Thư mục lưu ảnh tạm sau khi upload OCR
└── .venv/               🐍 Môi trường Python ảo
```

---

## 🔄 Bảng quy đổi điểm

| Điểm Hệ 10 | Điểm Hệ 4 | Xếp loại |
|------------|-----------|----------|
| ≥ 9.0      | A+ (4.0)  | Xuất Sắc |
| ≥ 8.5      | A  (4.0)  | Giỏi     |
| ≥ 8.0      | B+ (3.5)  | Khá      |
| ≥ 7.0      | B  (3.0)  | Khá      |
| ≥ 6.5      | C+ (2.5)  | TB Khá   |
| ≥ 5.5      | C  (2.0)  | Trung Bình |
| ≥ 5.0      | D+ (1.5)  | Yếu      |
| ≥ 4.0      | D  (1.0)  | Yếu      |
| < 4.0      | F  (0.0)  | Không đạt |

---

## 🐛 Xử lý lỗi thường gặp

### ❌ `LỖI KẾT NỐI DB`
```
❌ LỖI KẾT NỐI DB: [28000] [Microsoft][ODBC Driver 17 for SQL Server]
```
**Nguyên nhân:** SQL Server không chạy hoặc sai thông tin đăng nhập  
**Giải pháp:**
- Kiểm tra SQL Server đang chạy trong Services
- Kiểm tra lại `UID`, `PWD` trong `DB_CONFIG`
- Bật SQL Server Authentication trong SSMS

---

### ❌ `TesseractNotFoundError`
```
pytesseract.pytesseract.TesseractNotFoundError: ...
```
**Nguyên nhân:** Đường dẫn Tesseract sai  
**Giải pháp:** Cập nhật dòng 22 trong `LocalOCR.py` với đường dẫn đúng:
```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

---

### ❌ `google.auth.exceptions.DefaultCredentialsError`
```
Could not automatically determine credentials...
```
**Nguyên nhân:** File `key.json` không tồn tại hoặc đường dẫn sai  
**Giải pháp:**
- Kiểm tra file `key.json` đã được tải về và đặt đúng vị trí
- Kiểm tra đường dẫn trong dòng 25 của `LocalOCR.py`
- Đảm bảo Cloud Vision API đã được bật trong Google Cloud Console

---

### ❌ OCR đọc sai tên môn
**Nguyên nhân:** Ảnh mờ, ánh sáng kém, hoặc font chữ lạ  
**Giải pháp:**
- Sử dụng ảnh có độ phân giải cao (tối thiểu 1080p)
- Đảm bảo ảnh thẳng, không bị nghiêng
- Chụp trong điều kiện ánh sáng tốt
- Sau khi quét, kiểm tra và chỉnh sửa thủ công nếu cần

---

## 💾 Lưu ý về dữ liệu

- **Bảng điểm** được lưu trong **localStorage** của trình duyệt (tự động)
- Dữ liệu **KHÔNG mất** khi đóng trình duyệt
- Dữ liệu **SẼ MẤT** nếu xóa cache/cookie trình duyệt
- Ảnh upload được lưu tạm trong thư mục `uploads/` (an toàn để xóa thủ công)

---

## 👨‍💻 Công nghệ sử dụng

| Layer | Công nghệ |
|-------|-----------|
| **Backend** | Python 3.x + Flask |
| **OCR Engine 1** | Tesseract OCR (Local) + OpenCV |
| **OCR Engine 2** | Google Cloud Vision API |
| **Database** | Microsoft SQL Server 2017+ |
| **DB Connector** | pyodbc (ODBC Driver 17) |
| **Fuzzy Matching** | Python `difflib.SequenceMatcher` |
| **Frontend** | HTML5 + Bootstrap 5 + Font Awesome 6 |
| **Frontend Logic** | Vanilla JavaScript + LocalStorage |
| **Styling** | CSS3 với CSS Variables |

---

*Được xây dựng với ❤️ cho sinh viên Đại học Đà Nẵng*
