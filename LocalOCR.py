import os
import io
import re
import pyodbc
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from difflib import SequenceMatcher
import cv2
import pytesseract
import numpy as np
from google.cloud import vision

app = Flask(__name__)

# --- CẤU HÌNH ---
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 🎯 ĐƯỜNG DẪN TESSERACT LOCAL (Cho Ảnh Máy Tính)
# Sensei kiểm tra lại đúng đường dẫn máy mình chưa nhé!
pytesseract.pytesseract.tesseract_cmd = r'D:\OCR\tesseract.exe'

# 🎯 ĐƯỜNG DẪN GOOGLE API (Cho Ảnh Viết Tay)
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"D:\Python_Code\AI_Project\App_Python\key.json"

# --- KẾT NỐI SQL ---
DB_CONFIG = { 'DRIVER': '{ODBC Driver 17 for SQL Server}', 'SERVER': 'localhost', 'DATABASE': 'OCR_Grade', 'UID': 'sa', 'PWD': '1' }

def get_db_connection():
    try:
        conn_str = f"DRIVER={DB_CONFIG['DRIVER']};SERVER={DB_CONFIG['SERVER']};DATABASE={DB_CONFIG['DATABASE']};UID={DB_CONFIG['UID']};PWD={DB_CONFIG['PWD']};TrustServerCertificate=yes;"
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"❌ LỖI KẾT NỐI DB: {e}"); return None

# ========================================================
# 👁️ LÕI THỊ GIÁC HYBRID (LAI GIỮA LOCAL VÀ CLOUD)
# ========================================================

# 1. Quét Local bằng Tesseract (Dùng cho Ảnh Máy Tính)
def perform_local_ocr_computer(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    processed_img = cv2.threshold(img_resized, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

    config = '--oem 3 --psm 6'
    data = pytesseract.image_to_data(processed_img, lang='vie+eng', config=config, output_type=pytesseract.Output.DICT)
    
    word_list = []
    for i in range(len(data['text'])):
        if int(data['conf'][i]) > 10: 
            text = data['text'][i].strip()
            text = re.sub(r'[^\w\s\+\-\*,\.]', '', text) 
            if text:
                x = (data['left'][i] + data['width'][i] / 2) / 2
                y = (data['top'][i] + data['height'][i] / 2) / 2
                word_list.append({'text': text, 'x': x, 'y': y})
    return word_list

# 2. Quét Cloud bằng Google Vision (Dùng cho Ảnh Viết Tay)
def perform_cloud_ocr_handwriting(image_path):
    client = vision.ImageAnnotatorClient()
    with io.open(image_path, 'rb') as image_file: content = image_file.read()
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    
    if not response.text_annotations: return []
    words = response.text_annotations[1:]
    word_list = []
    for w in words:
        word_list.append({
            'text': w.description, 
            'x': sum([v.x for v in w.bounding_poly.vertices])/4,
            'y': sum([v.y for v in w.bounding_poly.vertices])/4
        })
    return word_list

# ========================================================
# 🧠 THUẬT TOÁN GOM DÒNG TỌA ĐỘ
# ========================================================
def reconstruct_lines(word_list, mode):
    if not word_list: return []
    word_list.sort(key=lambda k: k['y'])
    y_tolerance = 15 if mode == 'computer' else 40
    lines = []; current_line = []; current_y = -100
    for w in word_list:
        if abs(w['y'] - current_y) > y_tolerance: 
            if current_line:
                current_line.sort(key=lambda k: k['x'])
                lines.append(" ".join([item['text'] for item in current_line]))
            current_line = [w]; current_y = w['y']
        else: current_line.append(w)
    if current_line:
        current_line.sort(key=lambda k: k['x'])
        lines.append(" ".join([item['text'] for item in current_line]))
    return lines

# ========================================================
# 🛡️ TRUNG TÂM SỬA TÊN & QUY ĐỔI ĐIỂM
# ========================================================
def no_accent_vietnamese(s):
    s = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', s); s = re.sub(r'[ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴ]', 'A', s)
    s = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', s); s = re.sub(r'[ÈÉẸẺẼÊỀẾỆỂỄ]', 'E', s)
    s = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', s); s = re.sub(r'[ÒÓỌỎÕÔỒỐỘỔNƠỜỚỢỞỠ]', 'O', s)
    s = re.sub(r'[ìíịỉĩ]', 'i', s); s = re.sub(r'[ÌÍỊỈĨ]', 'I', s)
    s = re.sub(r'[ùúụủũưừứựửữ]', 'u', s); s = re.sub(r'[ÙÚỤỦŨƯỪỨỰỬỮ]', 'U', s)
    s = re.sub(r'[ỳýỵỷỹ]', 'y', s); s = re.sub(r'[ỲÝỴỶỸ]', 'Y', s)
    s = re.sub(r'[đ]', 'd', s); s = re.sub(r'[Đ]', 'D', s)
    return s

def quy_doi_chuan(diem_so):
    try:
        clean = re.sub(r"[^\d,\.]", "", str(diem_so))
        d = float(clean.replace(',', '.'))
        if d >= 9.0: return 'A+'
        if d >= 8.5: return 'A'
        if d >= 8.0: return 'B+'
        if d >= 7.0: return 'B'
        if d >= 6.5: return 'C+'
        if d >= 5.5: return 'C'
        if d >= 5.0: return 'D+'
        if d >= 4.0: return 'D'
        return 'F'
    except: return 'F'

def auto_correct_universal(raw_name, mode):
    conn = get_db_connection()
    if not conn: return raw_name, "0%"
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT ten_mon FROM danh_muc_mon")
        db_subjects = [row[0] for row in cursor.fetchall()]
        
        best_match = raw_name; highest_ratio = 0.0
        
        raw_lower = raw_name.lower()
        if 'c++' in raw_lower or 'cet' in raw_lower or 'ctt' in raw_lower or 'c t' in raw_lower:
            return "Lập trình C++", "100%"

        clean_raw = re.sub(r'www\.\S+', '', raw_name) 
        clean_raw = re.sub(r'[^\w\s\+#]', '', clean_raw).lower().strip()

        for subject in db_subjects:
            clean_sub = re.sub(r'[^\w\s\+#]', '', subject).lower()
            ratio = SequenceMatcher(None, clean_raw, clean_sub).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio; best_match = subject
        
        similarity_string = f"{int(highest_ratio * 100)}%"
        
        # 🚨 HẠ NGƯỠNG MÁY TÍNH XUỐNG 60% ĐỂ CỨU MÔN "MẠNG MÁY TÍNH" (70%)
        threshold = 0.60 if mode == 'computer' else 0.25
        
        if highest_ratio >= threshold: return best_match, similarity_string
        else: return raw_name, similarity_string 

    except Exception as e: print("Lỗi SQL:", e)
    finally:
        if conn: conn.close()
    return raw_name, "0%"

# ========================================================
# 💻 PARSER MÁY TÍNH (TESSERACT LOCAL)
# ========================================================
def parse_computer(lines):
    results = []
    pat_A = re.compile(r"(.+?)\s+(\d{2}[-.\s]\d{4})\s*(\d)\b")
    pat_B = re.compile(r"(.+?)\s+(\d)\s+(\d+[\.,]\d+)")

    for line in lines:
        match = None; mode = "A"
        match = pat_A.search(line)
        if not match: mode = "B"; match = pat_B.search(line)
        
        if match:
            raw_name = match.group(1).strip()
            tin_chi_ocr = match.group(3) if mode == "A" else match.group(2)
            end_pos = match.end()

            # 🚨 SIẾT LƯỚI LỌC MÃ HỌC PHẦN ĐẦU DÒNG (Chống OCR đọc sai số)
            raw_name = re.sub(r'^\d+\s+\d{5,10}\s+', '', raw_name) # Xóa dạng "5 31231456 "
            raw_name = re.sub(r'^\d{5,10}\s+', '', raw_name)       # Xóa dạng "3123145 " (Mất STT)
            raw_name = re.sub(r'^\d+\s+', '', raw_name).strip()    # Xóa STT mồ côi

            name_check = no_accent_vietnamese(raw_name).lower()
            blacklist = ["trung binh", "tich luy", "ren luyen", "tong so", "he 10", "he 4", "giao duc the chat", "quoc phong"]
            if any(kw in name_check for kw in blacklist): continue

            phan_duoi = line[end_pos:] 
            diem_10_float = -1.0
            match_diem_so = re.findall(r"(\d+[\.,]\d+)", phan_duoi)
            if match_diem_so:
                try: diem_10_float = float(match_diem_so[-1].replace(',', '.'))
                except: pass

            match_diem_chu = re.search(r"([A-DF]\s*\+?|F)(?=\s|$|\*|\d)", phan_duoi, re.IGNORECASE)
            diem_chu_ocr = match_diem_chu.group(1).upper().replace(" ", "") if match_diem_chu else 'F'

            if diem_10_float != -1.0:
                diem_chuan = quy_doi_chuan(diem_10_float)
                if diem_chuan[0] != diem_chu_ocr[0]: diem_chu = diem_chuan
                elif len(diem_chuan) > len(diem_chu_ocr): diem_chu = diem_chuan
                else: diem_chu = diem_chu_ocr
            else: diem_chu = diem_chu_ocr

            ten_mon_chuan, similarity_pct = auto_correct_universal(raw_name, 'computer')
            if len(ten_mon_chuan) < 2: continue
            
            results.append({
                "raw_name": raw_name,
                "ten_mon": ten_mon_chuan,
                "percentage": similarity_pct,
                "tin_chi": int(tin_chi_ocr), 
                "diem_he_4": diem_chu
            })
    return results

# ========================================================
# ✍️ PARSER VIẾT TAY (GOOGLE VISION API)
# ========================================================
def parse_handwriting(lines):
    results = []
    pattern = re.compile(r"(.+?)\s+(\d+)\s+(\d+[\.,]?\d*)(.*)")

    for line in lines:
        line = line.strip()
        match = pattern.search(line)
        if match:
            raw_name_ocr = match.group(1).strip()
            tin_chi_ocr = match.group(2)
            diem_10_str = match.group(3)
            phan_duoi = match.group(4) or "" 
            
            diem_chu_ocr = None
            match_chu = re.search(r"([A-DF])\s*([\+\-tTyY\*]?)", phan_duoi, re.IGNORECASE)
            if match_chu:
                chu_cai = match_chu.group(1).upper()
                dau_kem_theo = match_chu.group(2).upper()
                if dau_kem_theo in ['T', 'Y', '*']: dau_kem_theo = '+'
                diem_chu_ocr = chu_cai + dau_kem_theo

            ten_mon_chuan, similarity_pct = auto_correct_universal(raw_name_ocr, 'handwriting')
            
            if diem_chu_ocr: final_diem_he_4 = diem_chu_ocr 
            else:
                try: diem_10 = float(diem_10_str.replace(',', '.'))
                except: diem_10 = 0.0
                final_diem_he_4 = quy_doi_chuan(diem_10)
            
            if len(ten_mon_chuan) < 2: continue
            
            results.append({
                "raw_name": raw_name_ocr,
                "ten_mon": ten_mon_chuan,      
                "percentage": similarity_pct,  
                "tin_chi": int(tin_chi_ocr), 
                "diem_he_4": final_diem_he_4   
            })
    return results

# ========================================================
# 🚀 API ENDPOINTS
# ========================================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/search_subject', methods=['GET'])
def search_subject():
    query = request.args.get('q', '')
    if not query: return jsonify([])
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        sql = "SELECT ten_mon, tin_chi FROM danh_muc_mon WHERE ten_mon LIKE ?"
        cursor.execute(sql, (f'%{query}%')) 
        rows = cursor.fetchall()
        results = [{'ten_mon': r[0], 'tin_chi': r[1]} for r in rows]
        conn.close()
        return jsonify(results)
    return jsonify([])

@app.route('/api/process_ocr', methods=['POST'])
def process_ocr():
    if 'file_anh' not in request.files: return jsonify({"success": False, "error": "Chưa chọn file"})
    file = request.files['file_anh']
    mode = request.form.get('mode', 'computer')
    
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        try:
            if mode == 'handwriting':
                print("📝 Gọi GOOGLE VISION cho chữ Viết tay!")
                word_list = perform_cloud_ocr_handwriting(path)
                lines = reconstruct_lines(word_list, mode)
                extracted_data = parse_handwriting(lines) 
            else:
                print("💻 Gọi TESSERACT LOCAL cho chữ Máy tính!")
                word_list = perform_local_ocr_computer(path)
                lines = reconstruct_lines(word_list, mode)
                extracted_data = parse_computer(lines)
            
            return jsonify({"success": True, "data": extracted_data})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}) 
    return jsonify({"success": False, "error": "File không hợp lệ"})

if __name__ == '__main__':
    app.run(debug=True)