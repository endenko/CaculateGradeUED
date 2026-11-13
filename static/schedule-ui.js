/* Quét lịch thi / thời khoá biểu và đăng ký Google Calendar. */
(function () {
    const $ = (id) => document.getElementById(id);

    function esc(value) {
        return String(value == null ? '' : value).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
    }

    async function poll(id) {
        const deadline = Date.now() + 110000;
        while (Date.now() < deadline) {
            const info = await fetch('/api/ocr/jobs/' + id).then((res) => res.json());
            if (info.status === 'done') return info.result;
            if (info.status === 'error') throw new Error(info.error || 'OCR lỗi');
            await new Promise((resolve) => setTimeout(resolve, 800));
        }
        throw new Error('OCR quá thời gian chờ');
    }

    async function scan(mode, file) {
        const box = $('scheduleReview');
        box.hidden = false;
        box.innerHTML = '<p class="small">Đang đọc ảnh…</p>';
        const body = new FormData();
        body.append('file_anh', file);
        body.append('mode', mode);
        const ticket = await fetch('/api/ocr/jobs', { method: 'POST', body }).then((res) => res.json());
        if (!ticket.id) throw new Error(ticket.error || 'Không gửi được ảnh');
        const result = await poll(ticket.id);
        if (!result || !result.success) throw new Error((result && result.error) || 'Không đọc được bảng');
        paintReview(mode, result);
    }

    function paintReview(mode, result) {
        const rows = result.rows || [];
        const box = $('scheduleReview');
        if (!rows.length) {
            box.innerHTML = '<p class="text-danger small">Không thấy dòng lịch trong ảnh. Chụp đủ hàng tiêu đề và các cột.</p>';
            return;
        }
        const head = mode === 'exam'
            ? '<tr><th>Mã</th><th>Môn</th><th>Ngày</th><th>Giờ</th><th>Phòng</th><th>Hình thức</th></tr>'
            : '<tr><th>Mã</th><th>Môn</th><th>Thứ</th><th>Tiết</th><th>Tuần</th><th>Phòng</th></tr>';
        const body = rows.map((row, index) => mode === 'exam'
            ? `<tr data-i="${index}">
                <td><input class="form-control form-control-sm" data-k="ma_hp" value="${esc(row.ma_hp)}"></td>
                <td><input class="form-control form-control-sm" data-k="ten_mon" value="${esc(row.ten_mon)}"></td>
                <td><input class="form-control form-control-sm" data-k="ngay" value="${esc(row.ngay)}"></td>
                <td><input class="form-control form-control-sm" data-k="gio" value="${esc(row.gio)}"></td>
                <td><input class="form-control form-control-sm" data-k="phong" value="${esc(row.phong)}"></td>
                <td><input class="form-control form-control-sm" data-k="hinh_thuc" value="${esc(row.hinh_thuc)}"></td>
               </tr>`
            : `<tr data-i="${index}">
                <td><input class="form-control form-control-sm" data-k="ma_hp" value="${esc(row.ma_hp)}"></td>
                <td><input class="form-control form-control-sm" data-k="ten_mon" value="${esc(row.ten_mon)}"></td>
                <td><input class="form-control form-control-sm" data-k="thu" value="${esc(row.thu || '')}"></td>
                <td><input class="form-control form-control-sm" data-k="tiet" value="${esc((row.tiet || []).join(','))}"></td>
                <td><input class="form-control form-control-sm" data-k="tuan" value="${esc((row.tuan || []).join(','))}"></td>
                <td><input class="form-control form-control-sm" data-k="phong" value="${esc(row.phong)}"></td>
               </tr>`).join('');
        box.innerHTML = `<p class="small text-muted">${mode === 'exam' ? 'Lịch thi' : 'Thời khoá biểu'} ${esc((result.meta && result.meta.nam_hoc) || '')} ${esc((result.meta && result.meta.hoc_ky) || '')}. Giờ tiết là mặc định, sửa trước khi lưu.</p>
            <div class="table-scroll"><table class="table table-sm ued-table">${head}<tbody>${body}</tbody></table></div>
            <button type="button" class="btn btn-sm btn-ued" id="btnSaveScan">Lưu vào lịch</button>`;
        box.dataset.mode = mode;
        box.dataset.meta = JSON.stringify(result.meta || {});
        box.dataset.rows = JSON.stringify(rows);
        $('btnSaveScan').onclick = saveScan;
    }

    function saveScan() {
        const box = $('scheduleReview');
        const mode = box.dataset.mode;
        const meta = JSON.parse(box.dataset.meta || '{}');
        const original = JSON.parse(box.dataset.rows || '[]');
        const data = window.scheduleSnapshot ? window.scheduleSnapshot() : { classes: [], exams: [], start: '' };
        box.querySelectorAll('tbody tr').forEach((tr) => {
            const index = Number(tr.dataset.i);
            const row = Object.assign({}, original[index]);
            tr.querySelectorAll('input').forEach((input) => {
                const key = input.dataset.k;
                if (key === 'tiet' || key === 'tuan') row[key] = input.value.split(',').map((n) => Number(n)).filter(Boolean);
                else if (key === 'thu') row.thu = Number(input.value);
                else row[key] = input.value.trim();
            });
            if (mode === 'exam') {
                const [d, m, y] = (row.ngay || '').split('-');
                const at = y ? `${y}-${m}-${d}T${row.gio || '07:30'}` : '';
                data.exams.push({
                    id: 'e' + Date.now().toString(36) + index,
                    name: row.ten_mon,
                    ma_hp: row.ma_hp,
                    at,
                    room: row.phong,
                    hinh_thuc: row.hinh_thuc,
                    buoi: row.buoi,
                    nhom: row.nhom,
                    nhom_thi: row.nhom_thi,
                });
            } else if (row.start || (row.tiet || []).length) {
                data.classes.push({
                    id: 'c' + Date.now().toString(36) + index,
                    name: row.ten_mon,
                    ma_hp: row.ma_hp,
                    day: row.thu || 2,
                    start: row.start,
                    end: row.end,
                    room: row.phong,
                    lecturer: row.giang_vien,
                    nhom: row.nhom,
                    weeks: row.tuan || [],
                    periods: row.tiet || [],
                    buoi: row.buoi,
                    week_start: meta.week_start || data.week_start || '',
                });
                if (meta.week_start) data.week_start = meta.week_start;
            }
        });
        localStorage.setItem('ued_schedule_v1', JSON.stringify(data));
        if (window.syncProfile) window.syncProfile();
        box.innerHTML = '<p class="small text-success">Đã lưu. Nhắc trên trang dùng các lịch thi vừa thêm.</p>';
    }

    async function makeFeed() {
        const schedule = window.scheduleSnapshot ? window.scheduleSnapshot() : {};
        schedule.week_start = schedule.week_start || ($('ttStartDate') && $('ttStartDate').value) || '';
        const previous = localStorage.getItem('ued_cal_token') || '';
        const res = await fetch('/api/calendar/feed', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ schedule, previous }),
        });
        const data = await res.json();
        if (!data.token) return;
        localStorage.setItem('ued_cal_token', data.token);
        $('calFeedUrl').value = data.https;
        $('calFeedHelp').textContent = 'Google Calendar → Thêm lịch khác → Từ URL, dán liên kết https. Trên điện thoại mở ' + data.webcal;
    }

    async function revokeFeed() {
        const token = localStorage.getItem('ued_cal_token') || '';
        if (!token) return;
        await fetch('/api/calendar/feed/revoke', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token }),
        });
        localStorage.removeItem('ued_cal_token');
        $('calFeedUrl').value = '';
    }

    $('fileExam')?.addEventListener('change', (event) => {
        const file = event.target.files && event.target.files[0];
        if (file) scan('exam', file).catch((err) => { $('scheduleReview').hidden = false; $('scheduleReview').innerHTML = `<p class="text-danger small">${esc(err.message)}</p>`; });
    });
    $('fileTimetable')?.addEventListener('change', (event) => {
        const file = event.target.files && event.target.files[0];
        if (file) scan('timetable', file).catch((err) => { $('scheduleReview').hidden = false; $('scheduleReview').innerHTML = `<p class="text-danger small">${esc(err.message)}</p>`; });
    });
    $('btnCalFeed')?.addEventListener('click', () => makeFeed().catch(() => {}));
    $('btnCalRevoke')?.addEventListener('click', () => revokeFeed().catch(() => {}));
    fetch('/api/calendar/google/status').then((res) => res.json()).then((data) => {
        if (data.enabled && $('btnGoogleSync')) $('btnGoogleSync').hidden = false;
    }).catch(() => {});
})();
