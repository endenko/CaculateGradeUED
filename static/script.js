(function () {
    try {
        var raw = localStorage.getItem('ued_profiles_v1');
        if (!raw) {
            var first = {
                active: 'mac-dinh',
                items: [{
                    id: 'mac-dinh',
                    name: 'Mặc định',
                    transcript: JSON.parse(localStorage.getItem('kanna_transcript_v2') || '[]'),
                    table2: JSON.parse(localStorage.getItem('ued_table2') || '[]'),
                    weights: JSON.parse(localStorage.getItem('ued_weights') || 'null'),
                    schedule: JSON.parse(localStorage.getItem('ued_schedule_v1') || 'null'),
                    program: localStorage.getItem('ued_program') || ''
                }]
            };
            localStorage.setItem('ued_profiles_v1', JSON.stringify(first));
        } else {
            var store = JSON.parse(raw);
            var active = (store.items || []).filter(function (item) { return item.id === store.active; })[0] || (store.items || [])[0];
            if (active) {
                localStorage.setItem('kanna_transcript_v2', JSON.stringify(active.transcript || []));
                localStorage.setItem('ued_table2', JSON.stringify(active.table2 || []));
                if (active.weights) localStorage.setItem('ued_weights', JSON.stringify(active.weights));
                if (active.schedule) localStorage.setItem('ued_schedule_v1', JSON.stringify(active.schedule));
                if (active.program != null) localStorage.setItem('ued_program', active.program);
            }
        }
    } catch (err) { /* keep the raw transcript key */ }
})();
var transcriptData = JSON.parse(localStorage.getItem('kanna_transcript_v2')) || [];
const gradeMap = { 'A+': 4.0, 'A': 4.0, 'B+': 3.5, 'B': 3.0, 'C+': 2.5, 'C': 2.0, 'D+': 1.5, 'D': 1.0, 'F': 0.0 };

function saveData() {
    localStorage.setItem('kanna_transcript_v2', JSON.stringify(transcriptData));
    if (window.syncProfile) window.syncProfile();
    renderTable();
    calculateStats();
    if (window.refreshAcademics) window.refreshAcademics();
    if (window.studioRefresh) window.studioRefresh();
}

let debounceTimer;
function searchSubject() {
    const query = document.getElementById('inputName').value;
    if (query.length < 2) { document.getElementById('suggestions').style.display = 'none'; return; }

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        fetch(`/api/search_subject?q=${encodeURIComponent(query)}&khoa=${encodeURIComponent(document.getElementById('khoaFilter').value)}`)
            .then(res => res.json())
            .then(data => {
                const box = document.getElementById('suggestions');
                box.innerHTML = '';
                if (data.length > 0) {
                    box.style.display = 'block';
                    data.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'suggestion-item small';
                        div.innerHTML = `<b>${item.ten_mon}</b> <span class="text-muted float-end">(${item.tin_chi} TC)</span><div class="meta">${item.ma_hp || ''} ${item.khoa ? '· ' + item.khoa : ''}</div>`;
                        div.onclick = () => {
                            document.getElementById('inputName').value = item.ten_mon;
                            document.getElementById('inputCredits').value = item.tin_chi;
                            document.getElementById('inputName').dataset.maHp = item.ma_hp || '';
                            box.style.display = 'none';
                        };
                        box.appendChild(div);
                    });
                } else {
                    box.style.display = 'none';
                }
            });
    }, 300);
}

// Tắt gợi ý khi click ra ngoài
document.addEventListener('click', function (event) {
    const box = document.getElementById('suggestions');
    const input = document.getElementById('inputName');
    if (event.target !== box && event.target !== input) {
        box.style.display = 'none';
    }
});

function convertGrade() {
    let inputEl = document.getElementById('inputGrade10');
    let val = parseFloat(inputEl.value);

    if (val > 10) { val = 10; inputEl.value = 10; }
    else if (val < 0) { val = 0; inputEl.value = 0; }

    let char = '';
    if (!isNaN(val)) {
        const rounded = Math.round(val * 10) / 10;
        if (rounded >= 9.5) char = 'A+';
        else if (rounded >= 8.5) char = 'A';
        else if (rounded >= 8.0) char = 'B+';
        else if (rounded >= 7.0) char = 'B';
        else if (rounded >= 6.5) char = 'C+';
        else if (rounded >= 5.5) char = 'C';
        else if (rounded >= 5.0) char = 'D+';
        else if (rounded >= 4.0) char = 'D';
        else char = 'F';
    }
    document.getElementById('inputGrade4').value = char;
}

function addManualSubject() {
    const name = document.getElementById('inputName').value;
    const credits = parseInt(document.getElementById('inputCredits').value);
    const grade = document.getElementById('inputGrade4').value;

    const score10 = parseFloat(document.getElementById('inputGrade10').value);
    if (name && credits && grade && !isNaN(score10)) {
        transcriptData.push({
            ten_mon: name, tin_chi: credits, diem_he_4: grade, diem_10: score10, sim_grade: null,
            ma_hp: document.getElementById('inputName').dataset.maHp || '',
            nam_hoc: document.getElementById('inputYear').value,
            hoc_ky: document.getElementById('inputTerm').value,
            lan: parseInt(document.getElementById('inputAttempt').value, 10) || 1,
            pass_only: document.getElementById('inputPassOnly').checked
        });
        saveData();
        document.getElementById('inputName').value = '';
        document.getElementById('inputGrade10').value = '';
        document.getElementById('inputGrade4').value = '';
    } else {
        alert("Vui lòng nhập đủ thông tin bạn nhé!");
    }
}

let pendingOCR = [];
let pendingTerm = null;
let pendingScanFile = null;
const NO_TABLE_MSG = 'Không thấy bảng điểm trong ảnh. Hãy cắt vùng có dòng Học kỳ / Năm học, đủ cột điểm và phần tổng ở dưới, rồi quét lại.';

function isHeic(file) {
    return /heic|heif/i.test(file.type || '') || /\.heic$|\.heif$/i.test(file.name || '');
}

function canDecodeImage(file) {
    return new Promise((resolve) => {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => { URL.revokeObjectURL(url); resolve(true); };
        img.onerror = () => { URL.revokeObjectURL(url); resolve(false); };
        img.src = url;
    });
}

function showCropNote(text) {
    const note = document.getElementById('cropNote');
    if (!note) return;
    note.hidden = !text;
    note.textContent = text || '';
}

async function beginScanFile(file) {
    if (!file) return;
    const mode = document.querySelector('input[name="ocrMode"]:checked').value;
    showCropNote('');
    if (mode === 'handwriting') {
        pendingScanFile = file;
        showPreview(file);
        return;
    }
    if (isHeic(file) && !(await canDecodeImage(file))) {
        pendingScanFile = file;
        showCropNote('Trình duyệt không mở được HEIC để cắt. Bấm Quét ngay để gửi ảnh gốc. Nếu máy chủ không đọc được, hãy xuất JPEG.');
        document.getElementById('ocrPreview').style.display = 'none';
        document.getElementById('dropHint').style.display = 'block';
        return;
    }
    try {
        const cropped = await window.openCropper(file);
        if (!cropped) {
            document.getElementById('ocrFile').value = '';
            return;
        }
        pendingScanFile = cropped;
        showPreview(cropped);
        showCropNote('Đã cắt. Xem lại ảnh, rồi bấm Quét ngay.');
    } catch (err) {
        pendingScanFile = file;
        showPreview(file);
        showCropNote('Không cắt được trên máy này. Bấm Quét ngay để gửi ảnh gốc.');
    }
}
function escapeHtml(t) { return String(t).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function downscale(file, maxSide = 2000) {
    return new Promise(resolve => {
        const img = new Image();
        img.onload = () => {
            const k = Math.min(1, maxSide / Math.max(img.width, img.height));
            if (k === 1 && file.size < 3.5e6) return resolve(file);
            const c = document.createElement('canvas');
            c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
            c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
            c.toBlob(b => resolve(new File([b], 'scan.jpg', { type: 'image/jpeg' })), 'image/jpeg', 0.92);
        };
        img.onerror = () => resolve(file);
        img.src = URL.createObjectURL(file);
    });
}

async function uploadOCR() {
    const file = pendingScanFile;
    if (!file) return alert("Vui lòng chọn ảnh và xác nhận vùng cắt trước bạn nhé!");
    const mode = document.querySelector('input[name="ocrMode"]:checked').value;
    const formData = new FormData();
    formData.append('file_anh', await downscale(file));
    formData.append('mode', mode);
    const loading = document.getElementById('ocrLoading');
    const queueBox = document.getElementById('ocrQueue');
    loading.style.display = 'inline-block';
    if (queueBox) { queueBox.hidden = false; queueBox.textContent = 'Đang đưa ảnh vào hàng đợi…'; }
    try {
        const submit = await fetch('/api/ocr/jobs', { method: 'POST', body: formData });
        const ticket = await submit.json();
        if (!submit.ok || ticket.accepted === false) {
            loading.style.display = 'none';
            return alert(ticket.error || 'Không xếp hàng được');
        }
        const result = await pollOcr(ticket.id, queueBox);
        loading.style.display = 'none';
        if (!result || !result.success) return alert('Lỗi OCR: ' + ((result && result.error) || 'không rõ'));
        if (!result.data || !result.data.length) return alert(NO_TABLE_MSG);
        pendingOCR = result.data;
        pendingTerm = result.term || null;
        renderOCRReview(result.engine);
        if (queueBox) queueBox.textContent = 'Xong. Kiểm tra các dòng bên dưới rồi thêm vào bảng.';
    } catch (err) {
        loading.style.display = 'none';
        alert('Lỗi kết nối server!');
    }
}

async function pollOcr(id, queueBox) {
    for (let i = 0; i < 120; i++) {
        const res = await fetch('/api/ocr/jobs/' + id);
        const info = await res.json();
        if (!res.ok || info.found === false) {
            return { success: false, error: 'Phiên quét không còn (máy chủ vừa khởi động lại). Hãy gửi lại ảnh.' };
        }
        if (queueBox) {
            if (info.status === 'queued') {
                queueBox.textContent = `Hàng đợi: vị trí ${info.position}. Ước tính chờ khoảng ${info.eta_seconds} giây (ETA = số việc phía trước × ${info.avg_seconds}s).`;
            } else if (info.status === 'running') {
                queueBox.textContent = `Đang nhận diện ảnh của bạn. Còn khoảng ${info.eta_seconds} giây.`;
            }
        }
        if (info.status === 'done') return info.result;
        if (info.status === 'error') return { success: false, error: info.error };
        await new Promise(r => setTimeout(r, 1000));
    }
    return { success: false, error: 'Quá thời gian chờ hàng đợi' };
}

function renderOCRReview(engine) {
    const box = document.getElementById('ocrReview');
    box.style.display = 'block';
    if (!pendingOCR.length) { box.innerHTML = `<div class="alert alert-warning small mb-0">${NO_TABLE_MSG}</div>`; return; }
    let rows = pendingOCR.map((m, i) => {
        const pct = parseInt(m.percentage) || 0;
        return `<tr class="${pct < 70 ? 'ocr-row-low' : ''}">
            <td><input type="checkbox" class="form-check-input ocr-chk" data-i="${i}" ${pct >= 55 ? 'checked' : ''}></td>
            <td><div class="fw-semibold">${escapeHtml(m.ten_mon)}</div><div class="small text-muted">OCR: ${escapeHtml(m.raw_name)}</div></td>
            <td class="text-center">${m.tin_chi}</td><td class="text-center"><b>${m.in_progress ? '—' : escapeHtml(m.diem_he_4 || '')}</b></td>
            <td class="text-center"><span class="badge ${pct >= 80 ? 'bg-success' : pct >= 60 ? 'badge-gold' : 'bg-danger'}">${m.percentage}</span></td></tr>`;
    }).join('');
    box.innerHTML = `<div class="small text-muted mb-2">Engine: <b>${engine}</b> · Kiểm tra lại trước khi thêm (độ khớp &lt; 55% sẽ bỏ chọn).</div>
        <div class="table-responsive"><table class="table table-sm align-middle ued-table"><thead><tr><th></th><th>Môn (khớp DB)</th><th class="text-center">TC</th><th class="text-center">Điểm</th><th class="text-center">Khớp</th></tr></thead><tbody>${rows}</tbody></table></div>
        <button class="btn btn-ued w-100" onclick="confirmOCR()"><i class="fas fa-check"></i> Thêm các môn đã chọn</button>`;
}

function confirmOCR() {
    if (window.boardsAddOcr) {
        const rows = [];
        document.querySelectorAll('.ocr-chk:checked').forEach(chk => rows.push(pendingOCR[parseInt(chk.dataset.i, 10)]));
        const target = (document.querySelector('input[name="ocrTarget"]:checked') || {}).value || '1';
        window.boardsAddOcr(target, rows, pendingTerm || null);
        const termText = (pendingTerm && pendingTerm.nam_hoc) ? `Học kỳ ${pendingTerm.hoc_ky === 'he' ? 'hè' : pendingTerm.hoc_ky} · ${pendingTerm.nam_hoc}.` : 'Không xác định được kỳ/năm.';
        document.getElementById('ocrReview').innerHTML = `<div class="alert alert-success small mb-0">Đã đưa ${rows.length} môn vào học kỳ (${termText}). Điểm đã có cũng vào Điểm tổng. Môn chưa có điểm chỉ ở Điểm học phần.</div>`;
        return;
    }
    let count = 0;
    document.querySelectorAll('.ocr-chk:checked').forEach(chk => {
        const m = pendingOCR[parseInt(chk.dataset.i)];
        if (!transcriptData.some(s => s.ten_mon === m.ten_mon && s.nam_hoc === (document.getElementById('inputYear') || {}).value && s.hoc_ky === (document.getElementById('inputTerm') || {}).value && s.lan === (parseInt((document.getElementById('inputAttempt') || {}).value, 10) || 1))) {
            transcriptData.push({
                ...m, sim_grade: null,
                nam_hoc: document.getElementById('inputYear').value,
                hoc_ky: document.getElementById('inputTerm').value,
                lan: parseInt(document.getElementById('inputAttempt').value, 10) || 1,
                pass_only: false
            });
            count++;
        }
    });
    saveData();
    document.getElementById('ocrReview').innerHTML = `<div class="alert alert-success small mb-0">Đã thêm ${count} môn vào bảng điểm.</div>`;
}

function showPreview(file) {
    if (!file) return;
    const img = document.getElementById('ocrPreview');
    img.src = URL.createObjectURL(file); img.style.display = 'block';
    document.getElementById('dropHint').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', () => {
    const fi = document.getElementById('ocrFile'), dz = document.getElementById('dropzone');
    fi.addEventListener('change', () => beginScanFile(fi.files[0]));
    ['dragenter', 'dragover'].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.add('drag'); }));
    ['dragleave', 'drop'].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.remove('drag'); }));
    dz.addEventListener('drop', ev => { if (ev.dataTransfer.files.length) beginScanFile(ev.dataTransfer.files[0]); });
    fetch('/api/stats').then(r => r.json()).then(st => {
        document.getElementById('statSubjects').innerText = st.subjects;
        document.getElementById('statFaculties').innerText = st.faculties.length;
        const sel = document.getElementById('khoaFilter');
        const g1 = document.createElement('optgroup'); g1.label = 'Khoa hiện nay (2025)';
        st.faculties.forEach(f => { const o = document.createElement('option'); o.value = f.khoa; o.textContent = `${f.khoa} (${f.so_mon})`; g1.appendChild(o); });
        sel.appendChild(g1);
        if (st.faculties_old && st.faculties_old.length) {
            const g2 = document.createElement('optgroup'); g2.label = 'Khoa trước sáp nhập (≤2024)';
            st.faculties_old.forEach(f => { const o = document.createElement('option'); o.value = f.khoa; o.textContent = `${f.khoa} (${f.so_mon})`; g2.appendChild(o); });
            sel.appendChild(g2);
        }
    }).catch(() => {});
});

function renderTable() {
    const tbody = document.getElementById('transcriptTable');
    if (!tbody || tbody.closest('[hidden]')) return;
    tbody.innerHTML = '';

    transcriptData.forEach((item, index) => {
        let badgeClass = 'bg-F';
        let d = item.diem_he_4 || '';
        if (d.includes('A+')) badgeClass = 'bg-A-plus';
        else if (d.includes('A')) badgeClass = 'bg-A';
        else if (d.includes('B')) badgeClass = 'bg-B';
        else if (d.includes('C')) badgeClass = 'bg-C';
        else if (d.includes('D')) badgeClass = 'bg-D';

        let rowClass = "";
        let selectVal = "";
        if (item.sim_grade) {
            selectVal = item.sim_grade;
            rowClass = "table-warning";
        }
        const lowLetter = ['C', 'D+', 'D', 'F'].includes(item.diem_he_4);
        if ((item.tin_chi || 0) >= 3 && lowLetter) rowClass += ' row-low';

        let displayName = item.ten_mon;
        if (item.percentage) {
            displayName = `${item.ten_mon} <span class="text-success badge bg-light text-dark border ms-1" style="font-size: 0.7rem;">${item.percentage} giống</span>`;
        }

        const tr = document.createElement('tr');
        tr.className = rowClass;
        tr.innerHTML = `
            <td>${displayName}</td>
            <td class="text-center fw-bold">${item.tin_chi}</td>
            <td class="text-center"><span class="badge-grade ${badgeClass}">${item.diem_he_4}</span>${item.diem_10 != null ? `<div class="small text-muted">${item.diem_10}</div>` : ''}</td>
            <td class="text-center small">${item.term_unknown ? '<span class="text-muted">Không xác định được kỳ/năm</span>' : (item.nam_hoc ? `${item.nam_hoc}<br>HK${item.hoc_ky === 'he' ? ' hè' : item.hoc_ky} · lần ${item.lan || 1}` : '<span class="text-muted">chưa gắn kỳ</span>')}</td>
            <td class="text-center">
                <select class="form-select form-select-sm" onchange="updateSim(${index}, this.value)">
                    <option value="" ${selectVal == "" ? "selected" : ""}>— Giữ —</option>
                    <option value="A+" ${selectVal == "A+" ? "selected" : ""}>A+</option>
                    <option value="A" ${selectVal == "A" ? "selected" : ""}>A</option>
                    <option value="B+" ${selectVal == "B+" ? "selected" : ""}>B+</option>
                    <option value="B" ${selectVal == "B" ? "selected" : ""}>B</option>
                    <option value="C+" ${selectVal == "C+" ? "selected" : ""}>C+</option>
                    <option value="C" ${selectVal == "C" ? "selected" : ""}>C</option>
                    <option value="D+" ${selectVal == "D+" ? "selected" : ""}>D+</option>
                    <option value="D" ${selectVal == "D" ? "selected" : ""}>D</option>
                </select>
            </td>
            <td class="text-center"><i class="fas fa-times text-danger" style="cursor:pointer" onclick="removeSubject(${index})"></i></td>
        `;
        tbody.appendChild(tr);
    });

    generateSuggestions();
}

function removeSubject(index) {
    if (confirm("Xóa môn này nhé?")) {
        transcriptData.splice(index, 1);
        saveData();
    }
}

function clearAllData() {
    transcriptData = [];
    saveData();
}

function updateSim(index, val) {
    transcriptData[index].sim_grade = val === "" ? null : val;
    saveData();
}

function resetSimulation() {
    transcriptData.forEach(m => m.sim_grade = null);
    saveData();
}

function calculateStats() {
    let totalTin = 0;
    let totalRealScore = 0;
    let totalSimScore = 0;

    transcriptData.forEach(m => {
        if (m.pass_only || gradeMap[m.diem_he_4] == null) return;
        let realScore = gradeMap[m.diem_he_4];
        let simScore = m.sim_grade && gradeMap[m.sim_grade] != null ? gradeMap[m.sim_grade] : realScore;

        totalTin += m.tin_chi;
        totalRealScore += realScore * m.tin_chi;
        totalSimScore += simScore * m.tin_chi;
    });

    const curGPA = totalTin > 0 ? (totalRealScore / totalTin).toFixed(2) : "0.00";
    const simGPA = totalTin > 0 ? (totalSimScore / totalTin).toFixed(2) : "0.00";
    const diff = (simGPA - curGPA).toFixed(2);

    document.getElementById('displayGPA').innerText = curGPA;
    document.getElementById('simulatedGPA').innerText = simGPA;
    const diffEl = document.getElementById('diffGPA');
    diffEl.innerText = (diff > 0 ? "+" : "") + diff;

    if (diff > 0) diffEl.parentElement.className = 'card score-box up';
    else if (diff < 0) diffEl.parentElement.className = 'card score-box down';
    else diffEl.parentElement.className = 'card score-box diff';

    const targetEl = document.getElementById('targetCredits');
    const target = targetEl ? (parseInt(targetEl.value, 10) || 130) : 130;
    const passed = transcriptData.reduce((s, m) => s + ((gradeMap[m.diem_he_4] > 0 || m.pass_only) ? m.tin_chi : 0), 0);
    const percent = Math.min(100, Math.round((passed / target) * 100));
    const bar = document.getElementById('gradProgressBar');
    bar.style.width = percent + "%";
    bar.innerText = percent + "%";
    document.getElementById('progressText').innerText = `${passed} / ${target} TC đã đạt`;
}

function generateSuggestions() {
    const list = document.getElementById('suggestionList');
    list.innerHTML = "";
    let candidates = transcriptData.filter(m => (gradeMap[m.diem_he_4] || 0) < 3.0);

    candidates.sort((a, b) => {
        let impactA = (4.0 - (gradeMap[a.diem_he_4] || 0)) * a.tin_chi;
        let impactB = (4.0 - (gradeMap[b.diem_he_4] || 0)) * b.tin_chi;
        return impactB - impactA;
    });

    if (candidates.length === 0 && transcriptData.length > 0) {
        list.innerHTML = "<div class='text-center text-success mt-2'>🎉 Tuyệt vời! Bảng điểm đẹp, không cần học lại!</div>";
    } else {
        candidates.slice(0, 5).forEach(m => {
            let current = gradeMap[m.diem_he_4];
            let gain = ((4.0 - current) * m.tin_chi) / Math.max(1, transcriptData.reduce((s, x) => s + x.tin_chi, 0));

            list.innerHTML += `
        <div class="suggestion-alert p-2 rounded small mb-2" onclick="fillSim('${m.ten_mon}')">
            <div class="fw-bold">${m.ten_mon} (${m.tin_chi} TC)</div>
            <div class="d-flex justify-content-between text-muted">
                <span>Điểm: <b class="text-danger">${m.diem_he_4}</b></span>
                <span class="text-success fw-bold">GPA +${gain.toFixed(2)} 🚀</span>
            </div>
        </div>`;
        });
    }
}

function fillSim(name) {
    let idx = transcriptData.findIndex(m => m.ten_mon === name);
    if (idx !== -1) {
        updateSim(idx, "A");
        document.querySelectorAll('#transcriptTable tr')[idx].scrollIntoView({ behavior: "smooth", block: "center" });
    }
}

function exportTranscript() {
    const blob = new Blob([JSON.stringify({ savedAt: new Date().toISOString(), courses: transcriptData }, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'bang-diem-ued.json';
    a.click();
    URL.revokeObjectURL(a.href);
}

function calculateGraduationPath() {
    const targetGPA = parseFloat(document.getElementById('goalGPA').value);
    const remCredits = parseInt(document.getElementById('remainingCredits').value);
    const curGPA = parseFloat(document.getElementById('simulatedGPA').innerText);

    let totalTin = transcriptData.reduce((s, m) => s + m.tin_chi, 0);
    let currentTotalScore = curGPA * totalTin;

    if (remCredits <= 0) {
        document.getElementById('gradResult').style.display = 'block';
        document.getElementById('gradResult').className = "bg-warning text-dark";
        document.getElementById('gradResult').innerHTML = "Đã đủ tín chỉ rồi! Kết quả hiện tại là chốt hạ.";
        return;
    }

    const totalTargetCredits = totalTin + remCredits;
    const requiredTotalScore = targetGPA * totalTargetCredits;
    const neededScoreFromRemaining = requiredTotalScore - currentTotalScore;
    const neededGPA = neededScoreFromRemaining / remCredits;

    const resDiv = document.getElementById('gradResult');
    resDiv.style.display = 'block';

    if (neededGPA > 4.0) {
        resDiv.className = "bg-danger text-white";
        resDiv.innerHTML = `❌ <b>Khó quá!</b><br>Cần đạt trung bình <b>${neededGPA.toFixed(2)}</b> (Hơn cả 4.0).`;
    } else if (neededGPA < 0) {
        resDiv.className = "bg-success text-white";
        resDiv.innerHTML = `🎉 <b>Dư sức!</b><br>Đã tích lũy đủ điểm để đạt mục tiêu.`;
    } else {
        resDiv.className = "bg-info text-white";
        resDiv.innerHTML = `🎯 <b>Mục tiêu:</b><br>Cần đạt GPA trung bình <b>${neededGPA.toFixed(2)}</b> cho ${remCredits} tín chỉ cuối.`;
    }
}

function calcDRL() {
    const target = parseInt(document.getElementById('drlTarget').value);
    const sem1 = parseFloat(document.getElementById('drlSem1').value);
    const resBox = document.getElementById('drlResult');

    resBox.style.display = 'block';

    if (isNaN(sem1)) {
        resBox.innerHTML = `🎯 Để đạt <b>${target}</b> cả năm, mỗi kỳ bạn cần phấn đấu đạt trung bình <b>${target}</b> điểm nhé!`;
    } else {
        const needed = (target * 2) - sem1;

        if (needed > 100) {
            resBox.className = "alert alert-danger border text-center small p-1";
            resBox.innerHTML = `😱 <b>Nguy hiểm!</b> Cần <b>${needed}</b> điểm. (Max 100).`;
        } else if (needed <= 50) {
            resBox.className = "alert alert-success border text-center small p-1";
            resBox.innerHTML = `😎 <b>Dễ ợt!</b> Chỉ cần <b>${Math.max(0, needed)}</b> điểm.`;
        } else {
            resBox.className = "alert alert-info border text-center small p-1";
            resBox.innerHTML = `🔥 <b>Chiến lược:</b> Kỳ 2 cần đạt <b>${needed}</b> điểm ĐRL.`;
        }
    }
}

renderTable();
calculateStats();