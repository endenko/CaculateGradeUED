# 🌸 UED Calculate Grade!

> **Hệ thống quản lý điểm số thông minh dành cho sinh viên Đại học Đà Nẵng**  
> Quét ảnh bảng điểm tự động · Tính GPA · Mô phỏng "What If" · Gợi ý môn học lại

---

## 📋 Mục lục

- [Tổng quan hệ thống](#-tổng-quan-hệ-thống)
- [Tính năng chính](#-tính-năng-chính)
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
- [🚀 Chạy bằng Docker (khuyến nghị)](#-chạy-bằng-docker-khuyến-nghị)
- [Chạy local (không Docker)](#-chạy-local-không-docker)
- [Cấu hình hệ thống](#-cấu-hình-hệ-thống)
- [Cách sử dụng](#-cách-sử-dụng)
- [API Reference](#-api-reference)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Xử lý lỗi thường gặp](#-xử-lý-lỗi-thường-gặp)

---

## 🎯 Tổng quan hệ thống

**UED Calculate Grade** là ứng dụng web được xây dựng bằng **Flask (Python)**, có khả năng:

1. **Quét ảnh bảng điểm** tự động bằng OCR Hybrid: **Tesseract** (ảnh máy tính) + **PaddleOCR Tiếng Việt** (ảnh viết tay)
2. **Tự động nhận diện và khớp tên môn học** từ cơ sở dữ liệu (SQLite — Docker sẵn sàng)
3. **Tính GPA** theo thang hệ 4 và hệ 10
4. **Mô phỏng điểm số** (What-If Simulation) để sinh viên lên kế hoạch học tập
5. **Gợi ý môn học lại** có tác động cao nhất đến GPA

> ✨ **Thay đổi so với bản gốc:** OCR chữ viết tay đã chuyển từ **Google Cloud Vision API** (cần key + internet) sang **PaddleOCR với mô hình Tiếng Việt (`lang='vi'`)** — chạy hoàn toàn offline trong Docker, không cần API key, nhận diện tốt chữ viết tay tiếng Việt (dấu thanh, dấu mũ, ư/ơ...). Tesseract được **giữ nguyên** cho ảnh bảng điểm máy tính. Google Vision vẫn còn lại như engine **tùy chọn** (xem phần Cấu hình).

---

## ✨ Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| 📸 **OCR Ảnh Máy Tính** | Dùng Tesseract (Local) để quét ảnh bảng điểm chụp từ cổng thông tin portal |
| ✍️ **OCR Chữ Viết Tay** | Dùng **PaddleOCR Tiếng Việt** (offline, không cần API key) |
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
│  - Gọi API Flask qua fetch()                         │
└────────────────────┬────────────────────────────────┘
                     │ HTTP Request
┌────────────────────▼────────────────────────────────┐
│               BACKEND (Flask - app.py)               │
│  - Route /        → Serve trang HTML chính           │
│  - Route /api/search_subject → Tìm kiếm môn học      │
│  - Route /api/process_ocr    → Xử lý ảnh OCR         │
│  - Route /health             → Healthcheck Docker    │
└──────┬──────────────────────────────────┬────────────┘
       │                                  │
┌──────▼──────┐                  ┌────────▼──────────┐
│  SQLite DB  │                  │   OCR Engine      │
│  grade.db   │                  │  (ocr/engines.py) │
│  danh_muc_  │                  │                   │
│    mon      │                  │ Mode 1: Tesseract  │
│  ten_mon    │                  │  (Ảnh máy tính)   │
│  tin_chi    │                  │                   │
└─────────────┘                  │ Mode 2: PaddleOCR │
                                 │  lang='vi'        │
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
    └── Handwriting Mode ──→ PaddleOCR (lang='vi')
                                  │
                             Vietnamese text rec
                             (offline, no API key)
                                  │
                             Trích xuất text + bbox
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

## 🚀 Chạy bằng Docker (khuyến nghị)

Ứng dụng đã được Docker hóa hoàn toàn — **không cần cài Python, Tesseract, SQL Server hay bất kỳ API key nào**.

### Yêu cầu

- Docker Engine + Docker Compose (bản mới nhất)

### Các bước

```bash
# 1. Vào thư mục dự án
cd D:\OCRWEBSITE

# 2. Build image + chạy container
docker compose up -d --build

# 3. Mở trình duyệt
#    http://localhost:5000
```

Container sẽ tự động:
- Cài Tesseract + gói ngôn ngữ `vie`
- Cài PaddleOCR + **tải sẵn mô hình Tiếng Việt** (image chạy offline)
- Tạo database SQLite `grade.db` từ `data/danh_muc_mon.csv`

### Lệnh quản lý

```bash
docker compose logs -f        # Xem log
docker compose restart        # Khởi động lại
docker compose down           # Dừng (giữ volume uploads + grade.db)
docker compose down -v        # Dừng và xóa hoàn toàn
```

> **Lưu ý:** Image đầu tiên khá lớn (~2GB) vì chứa PaddleOCR + mô hình Tiếng Việt. Lần build đầu sẽ lâu do tải mô hình.

---

## ☁️ Triển khai miễn phí lên Render.com (Docker)

Ứng dụng chạy được trên **gói miễn phí** của Render (512 MB RAM). Mặc định image dùng
cấu hình `OCR_MODEL_SIZE=hybrid` (det nhẹ + rec bản medium, ~84 MB) — cân bằng giữa độ
chính xác và bộ nhớ.

### Cách 1 — Deploy trực tiếp từ GitHub (nhanh nhất)

1. Push code lên một GitHub repo công khai:
   ```bash
   git push origin main
   ```
2. Vào https://dashboard.render.com → **New → Web Service**
3. Dán URL repo (`https://github.com/<user>/<repo>.git`) — Render có thể đọc repo công khai
   mà không cần kết nối tài khoản GitHub
4. Render tự nhận Dockerfile. Kiểm tra:
   - **Runtime**: `Docker`
   - **Plan**: `Free`
   - **Health Check Path**: `/health`
5. **Create Web Service** — đợi build (~5–10 phút), app mở tại `https://<tên-service>.onrender.com`

### Cách 2 — Blueprint (`render.yaml`)

Repo đã kèm `render.yaml` (service tên **UedCalculateGrade**, plan free). Tại dashboard:
**New → Blueprint** → chọn repo → Render tạo service theo đúng cấu hình.

### Lưu ý khi dùng gói Free

- Instance **ngủ sau 15 phút** không có truy cập; lần mở đầu tiên sau khi ngủ sẽ chậm
  (30–60s do tải mô hình OCR) — mở lại là nhanh.
- Bộ nhớ 512 MB: nếu OCR bị kill (OOM), đổi `OCR_MODEL_SIZE=mobile` trong
  **Dashboard → Service → Environment** rồi Deploy lại.
- `grade.db` được tạo lại mỗi lần khởi động từ `data/danh_muc_mon.csv` — sửa CSV trong
  repo rồi push là dữ liệu môn học được cập nhật.
- Gói miễn phí không hỗ trợ disk bền vững → ảnh upload sẽ mất khi service khởi động lại
  (không ảnh hưởng chức năng chính).

---

## 🖥️ Chạy local (không Docker)

### Yêu cầu

| Phần mềm | Phiên bản | Ghi chú |
|----------|-----------|---------|
| Python | ≥ 3.9 | (khuyến nghị 3.11) |
| Tesseract OCR | ≥ 5.x | [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) — **phải cài gói `vie`** |

### Các bước

```bash
# 1. Tạo môi trường ảo
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

# 2. Cài thư viện
pip install -r requirements.txt

# 3. Tạo database SQLite từ danh sách môn học
python seed_db.py

# 4. Chạy server
python app.py
```

Mở trình duyệt: **http://127.0.0.1:5000**

> 💡 Windows: nếu Tesseract chưa có trong PATH, set biến môi trường:
> ```bash
> set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
> ```

---

## ⚙️ Cấu hình hệ thống

Tất cả cấu hình qua **biến môi trường** (không còn đường dẫn Windows cứng trong code). Xem `.env.example`.

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `OCR_HANDWRITING_ENGINE` | `paddle` | Engine OCR viết tay: `paddle` \| `tesseract` \| `google` |
| `TESSERACT_CMD` | *(PATH)* | Đường dẫn tesseract.exe (Windows local) |
| `DB_PATH` | `grade.db` | Đường dẫn database SQLite |
| `UPLOAD_FOLDER` | `uploads` | Thư mục lưu ảnh upload |
| `PORT` | `5000` | Cổng Flask (chỉ `python app.py`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | *(trống)* | Chỉ khi dùng engine `google` |

### Engine Google Vision (tùy chọn — để so sánh luận văn)

Google Vision **không còn là engine mặc định**. Nếu muốn dùng lại để so sánh:

```bash
pip install -r requirements-google.txt
set OCR_HANDWRITING_ENGINE=google
set GOOGLE_APPLICATION_CREDENTIALS=D:\path\to\key.json
python app.py
```

---

## 📖 Cách sử dụng

### 1. Nhập môn học thủ công

1. Gõ **tên môn học** vào ô "Tên môn học" → Hệ thống tự gợi ý từ database
2. Chọn **số tín chỉ** (1-4)
3. Nhập **điểm hệ 10** → Hệ 4 tự động quy đổi
4. Nhấn nút **`+`** để thêm vào bảng điểm

> 💡 **Mẹo:** Hệ thống tự động gợi ý tên môn và số tín chỉ khi bạn gõ từ 2 ký tự trở lên!

### 2. Quét ảnh bảng điểm bằng OCR

**Chế độ A - Ảnh Portal (Máy tính):**
- Dùng cho ảnh chụp màn hình/chụp lại từ website cổng thông tin sinh viên
- Sử dụng Tesseract OCR (không cần Internet)

**Chế độ B - Ảnh Viết Tay:**
- Dùng cho ảnh chụp bảng điểm viết tay (phiếu điểm, sổ điểm)
- Sử dụng **PaddleOCR Tiếng Việt** (offline, không cần Internet/API key)
- Nhận diện tốt chữ viết tay tiếng Việt (dấu thanh, dấu mũ, ư/ơ/ă/â...)

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
    "engine": "paddle",
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

> `engine` cho biết engine OCR đã dùng: `tesseract` | `paddle` | `google`

**Response lỗi:**
```json
{
    "success": false,
    "error": "Mô tả lỗi..."
}
```

### GET `/health`

Healthcheck cho Docker.

**Response:** `{ "success": true, "status": "ok" }`

---

## ✅ Kết quả kiểm thử OCR (ảnh mẫu trong `uploads/`)

### Chế độ Viết Tay — Vietnamese PaddleOCR (`lang='vi'`)

| Ảnh mẫu | Kết quả OCR | Tên khớp DB | % | TC | Điểm |
|---------|-------------|-------------|----|----|----|
| `2.jpg` (ảnh chụp sổ tay) | `coro'de?lieu` | Cơ sở dữ liệu | 61% | 4 | A |
| `2.jpg` | `Loain +rimh C++` | Lập trình C++ | 100% | 3 | B |
| `2.jpg` | `Toan RoiRac` | Toán rời rạc | 95% | 4 | B+ |
| `Screenshot_2026-03-28_174553.png` | `ln tainh Java` | Lập trình Java | 81% | 3 | B |
| `Screenshot_2026-03-28_174553.png` | `Yai xuat thong'le` | Xác suất thống kê | 72% | 3 | C+ |
| `Screenshot_2026-03-28_174553.png` | `cap trinh web` | Lập trình Web | 92% | 3 | C |
| `Screenshot_2026-03-28_172609.png` | `Toán ri rc` | Toán rời rạc | 90% | 4 | B |
| `Screenshot_2026-03-28_172609.png` | `Lp trình JAVA` | Lập trình Java | 96% | 3 | C |
| `Screenshot_2026-03-28_172609.png` | `Xác xut thng kê` | Xác suất thống kê | 87% | 3 | C+ |

**9/9 dòng viết tay nhận diện đúng** — đọc được cả tên môn (qua fuzzy matching), tín chỉ và điểm hệ 4.

### Chế độ Máy Tính — Tesseract (giữ nguyên bản gốc)

| Ảnh mẫu | Số dòng | Kết quả |
|---------|---------|---------|
| `test.png` | 6 | 6/6 đúng (Lịch sử Đảng, KHGD, PPDH Tin học, PT&TK HTTT, Web, CSDL) |
| `Screenshot_2026-01-31_151043.png` | 6 | 6/6 đúng (XSTK, Giải tích thực & ĐSTT, Scratch, C/C++, TRR, GD học) |
| `ky1nam1.png` | 6 | 6/6 đúng |

**Tesseract không bị thay đổi** — cùng preprocessing (OpenCV), cùng `lang='vie+eng'`, cùng parser.

---

## 📁 Cấu trúc thư mục

```
OCRWEBSITE/
│
├── app.py                  ⭐ File chính - Server Flask (Hybrid OCR)
├── LocalOCR.py             📦 Bản gốc (tham khảo) - SQL Server + Google Vision
├── db.py                   🗄️ Lớp database SQLite (thay SQL Server)
├── seed_db.py              🌱 Tạo grade.db từ danh sách môn học
├── grade.db                🗃️ SQLite database (tự tạo khi seed)
│
├── ocr/
│   └── engines.py          👁️ 3 OCR engines: Tesseract + PaddleOCR(vi) + Google (tùy chọn)
│
├── data/
│   └── danh_muc_mon.csv    📋 Danh sách môn học + tín chỉ (seed)
│
├── templates/
│   ├── index.html          🌐 Giao diện chính (Bootstrap 5 + FontAwesome)
│   └── index_ban_cu.html   📄 Phiên bản giao diện cũ
│
├── static/
│   ├── style.css           🎨 CSS tùy chỉnh
│   └── script.js           ⚡ Logic frontend (GPA, OCR, Simulation)
│
├── uploads/                📂 Thư mục lưu ảnh tạm sau khi upload OCR
│
├── Dockerfile              🐳 Build image (Tesseract + PaddleOCR + mô hình vi)
├── docker-compose.yml      🐳 Chạy 1 lệnh: docker compose up -d --build
├── requirements.txt        📦 Python dependencies (chính)
├── requirements-google.txt 📦 (Tùy chọn) Chỉ khi dùng engine Google Vision
└── .env.example            ⚙️ Mẫu biến môi trường
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

### ❌ `TesseractNotFoundError` (chạy local Windows)
**Nguyên nhân:** Tesseract chưa cài hoặc chưa có trong PATH
**Giải pháp:**
- Cài từ [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) (tích `vie`)
- Hoặc set biến môi trường: `set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`

### ❌ `LỖI KẾT NỐI DB` (bản gốc SQL Server)
**Nguyên nhân:** SQL Server không chạy hoặc sai thông tin đăng nhập
**Giải pháp:** Bản Docker hóa đã chuyển sang **SQLite** — không cần SQL Server. Xóa `grade.db` và chạy lại `python seed_db.py` nếu DB lỗi.

### ❌ PaddleOCR báo lỗi tải mô hình
**Nguyên nhân:** Chưa có internet lần đầu chạy (local) hoặc model cache lỗi
**Giải pháp:**
- Local: chạy `python -c "from ocr.engines import warmup; warmup()"` khi có internet
- Docker: mô hình đã được tải sẵn lúc build image

### ❌ OCR đọc sai tên môn
**Nguyên nhân:** Ảnh mờ, ánh sáng kém, hoặc font chữ lạ
**Giải pháp:**
- Sử dụng ảnh có độ phân giải cao (tối thiểu 1080p)
- Đảm bảo ảnh thẳng, không bị nghiêng
- Chụp trong điều kiện ánh sáng tốt
- Sau khi quét, kiểm tra và chỉnh sửa thủ công nếu cần
- Thêm tên môn chính xác vào `data/danh_muc_mon.csv` → `python seed_db.py` để tăng độ khớp

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
| **Backend** | Python 3.11 + Flask |
| **OCR Engine 1** | Tesseract OCR (Local) + OpenCV — ảnh máy tính |
| **OCR Engine 2** | **PaddleOCR `lang='vi'` — chữ viết tay tiếng Việt (offline)** |
| **OCR Engine 3** | Google Cloud Vision (tùy chọn, để so sánh) |
| **Database** | **SQLite** (thay SQL Server — zero-config) |
| **Fuzzy Matching** | Python `difflib.SequenceMatcher` |
| **Deployment** | **Docker + Docker Compose** (gunicorn, healthcheck) |
| **Frontend** | HTML5 + Bootstrap 5 + Font Awesome 6 |
| **Frontend Logic** | Vanilla JavaScript + LocalStorage |
| **Styling** | CSS3 với CSS Variables |

---

## 💾 Lưu ý về dữ liệu

- **Bảng điểm** được lưu trong **localStorage** của trình duyệt (tự động)
- Dữ liệu **KHÔNG mất** khi đóng trình duyệt
- Dữ liệu **SẼ MẤT** nếu xóa cache/cookie trình duyệt
- Ảnh upload được lưu tạm trong thư mục `uploads/` (an toàn để xóa thủ công)
