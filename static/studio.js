/* Hồ sơ, biểu đồ, lộ trình, lịch, xuất file, nền tối, PWA. */
(function () {
    const $ = (id) => document.getElementById(id);
    const DAYS = { 2: 'Thứ 2', 3: 'Thứ 3', 4: 'Thứ 4', 5: 'Thứ 5', 6: 'Thứ 6', 7: 'Thứ 7', 8: 'Chủ nhật' };
    const ICS_DAY = { 2: 'MO', 3: 'TU', 4: 'WE', 5: 'TH', 6: 'FR', 7: 'SA', 8: 'SU' };
    let chart = null;
    let chartTimer = null;

    function readStore() {
        try {
            return JSON.parse(localStorage.getItem('ued_profiles_v1')) || { active: 'mac-dinh', items: [] };
        } catch (err) {
            return { active: 'mac-dinh', items: [] };
        }
    }

    function writeStore(store) {
        localStorage.setItem('ued_profiles_v1', JSON.stringify(store));
    }

    function emptySchedule() {
        return { classes: [], exams: [], start: '' };
    }

    function schedule() {
        try {
            return Object.assign(emptySchedule(), JSON.parse(localStorage.getItem('ued_schedule_v1') || 'null') || {});
        } catch (err) {
            return emptySchedule();
        }
    }

    function saveSchedule(data) {
        localStorage.setItem('ued_schedule_v1', JSON.stringify(data));
        if (window.syncProfile) window.syncProfile();
        paintSchedule();
    }

    window.scheduleSnapshot = function () {
        return schedule();
    };

    window.syncProfile = function () {
        const store = readStore();
        const item = (store.items || []).find(row => row.id === store.active);
        if (!item) return;
        item.transcript = window.transcriptData || [];
        item.table2 = window.boardsSnapshot ? window.boardsSnapshot() : JSON.parse(localStorage.getItem('ued_table2') || '[]');
        try { item.weights = JSON.parse(localStorage.getItem('ued_weights') || 'null'); } catch (err) { item.weights = null; }
        item.schedule = schedule();
        item.program = localStorage.getItem('ued_program') || '';
        writeStore(store);
        const stamp = $('saveStamp');
        if (stamp) stamp.textContent = 'Đã lưu trên máy';
    };

    function paintProfiles() {
        const sel = $('profileSelect');
        if (!sel) return;
        const store = readStore();
        sel.innerHTML = '';
        (store.items || []).forEach(item => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.name || 'Hồ sơ';
            sel.appendChild(opt);
        });
        sel.value = store.active;
        const del = $('btnProfileDelete');
        if (del) del.disabled = (store.items || []).length < 2;
        const current = (store.items || []).find(item => item.id === store.active);
        if ($('profileName') && current && document.activeElement !== $('profileName')) $('profileName').value = current.name || '';
    }

    function applyProfile(id, skipSave) {
        if (!skipSave && window.syncProfile) window.syncProfile();
        const store = readStore();
        const item = (store.items || []).find(row => row.id === id);
        if (!item) return;
        store.active = id;
        writeStore(store);
        window.transcriptData = item.transcript || [];
        localStorage.setItem('kanna_transcript_v2', JSON.stringify(window.transcriptData));
        localStorage.setItem('ued_table2', JSON.stringify(item.table2 || []));
        if (item.weights) localStorage.setItem('ued_weights', JSON.stringify(item.weights));
        localStorage.setItem('ued_schedule_v1', JSON.stringify(item.schedule || emptySchedule()));
        localStorage.setItem('ued_program', item.program || '');
        if (window.boardsReplace) window.boardsReplace(item.table2 || []);
        if (typeof renderTable === 'function') renderTable();
        if (typeof calculateStats === 'function') calculateStats();
        paintProfiles();
        paintSchedule();
        const program = $('programSelect');
        if (program && item.program) program.value = item.program;
        loadRoadmap();
        refreshChart();
    }

    function addProfile() {
        const name = ($('profileName').value || '').trim();
        if (!name) { $('profileName').focus(); return; }
        if (window.syncProfile) window.syncProfile();
        const store = readStore();
        const id = 'p' + Date.now().toString(36);
        store.items.push({ id, name, transcript: [], table2: [], weights: null, schedule: emptySchedule(), program: '' });
        store.active = id;
        writeStore(store);
        applyProfile(id, true);
    }

    function renameProfile() {
        const name = ($('profileName').value || '').trim();
        if (!name) return;
        const store = readStore();
        const item = store.items.find(row => row.id === store.active);
        if (!item) return;
        item.name = name;
        writeStore(store);
        paintProfiles();
    }

    function deleteProfile() {
        const store = readStore();
        if ((store.items || []).length < 2) return;
        if (!confirm('Xóa hồ sơ đang mở? Bảng điểm của hồ sơ này sẽ mất trên máy.')) return;
        store.items = store.items.filter(row => row.id !== store.active);
        store.active = store.items[0].id;
        writeStore(store);
        applyProfile(store.active, true);
    }

    function esc(value) {
        return String(value == null ? '' : value).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
    }

    async function refreshChart() {
        const canvas = $('gpaChart');
        if (!canvas || !window.Chart) return;
        const courses = (window.transcriptData || []).map(course => ({
            ten_mon: course.ten_mon,
            tin_chi: course.tin_chi,
            diem_he_4: course.sim_grade || course.diem_he_4,
            diem_10: course.sim_grade ? null : course.diem_10,
            nam_hoc: course.nam_hoc,
            hoc_ky: course.hoc_ky,
            lan: course.lan || 1,
            pass_only: !!course.pass_only,
        }));
        let semesters = [];
        try {
            const res = await fetch('/api/gpa_series', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    courses,
                    program_credits: parseFloat(($('targetCredits') || {}).value) || 130,
                }),
            });
            const data = await res.json();
            semesters = (data.semesters || []).filter(item => item.gpa != null || item.cumulative_gpa != null);
        } catch (err) {
            semesters = [];
        }
        const empty = $('chartEmpty');
        if (empty) empty.hidden = semesters.length > 0;
        const dark = document.documentElement.getAttribute('data-theme') === 'dark';
        const text = dark ? '#d6e4ff' : '#1d2a3a';
        const grid = dark ? 'rgba(214,228,255,.14)' : 'rgba(11,78,162,.12)';
        if (chart) chart.destroy();
        chart = new Chart(canvas, {
            data: {
                labels: semesters.map(item => `${item.nam_hoc || ''} · HK${item.hoc_ky === 'he' ? ' hè' : item.hoc_ky}`),
                datasets: [
                    { type: 'bar', label: 'GPA học kỳ', data: semesters.map(item => item.gpa), backgroundColor: dark ? 'rgba(142,182,240,.8)' : 'rgba(11,78,162,.8)', borderRadius: 6, order: 2 },
                    { type: 'line', label: 'CPA tích lũy', data: semesters.map(item => item.cumulative_gpa), borderColor: '#f5b800', backgroundColor: '#f5b800', pointBackgroundColor: '#f5b800', tension: 0.25, spanGaps: true, order: 1 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { labels: { color: text, boxWidth: 12 } } },
                scales: {
                    y: { min: 0, max: 4, ticks: { color: text }, grid: { color: grid } },
                    x: { ticks: { color: text, maxRotation: 0, autoSkip: true }, grid: { display: false } },
                },
            },
        });
    }

    window.studioRefresh = function () {
        clearTimeout(chartTimer);
        chartTimer = setTimeout(refreshChart, 200);
        if ($('panel-lotrinh') && !$('panel-lotrinh').hidden) loadRoadmap();
        if (window.adviseRefresh) window.adviseRefresh();
    };

    async function loadPrograms() {
        const sel = $('programSelect');
        if (!sel || sel.dataset.ready === '1') return;
        const res = await fetch('/api/programs');
        const programs = await res.json();
        sel.innerHTML = '<option value="">Chọn chương trình</option>';
        let khoa = '';
        programs.forEach(item => {
            if (item.khoa !== khoa) {
                khoa = item.khoa;
                const group = document.createElement('optgroup');
                group.label = khoa || 'Khác';
                group.dataset.khoa = khoa;
                sel.appendChild(group);
            }
            const opt = document.createElement('option');
            opt.value = item.nganh;
            opt.textContent = `${item.nganh} · ${item.tin_chi} TC`;
            sel.querySelector(`optgroup[data-khoa="${CSS.escape(khoa)}"]`).appendChild(opt);
        });
        sel.dataset.ready = '1';
        const saved = localStorage.getItem('ued_program') || '';
        if (saved) sel.value = saved;
    }

    async function loadRoadmap() {
        const sel = $('programSelect');
        const box = $('roadSummary');
        if (!sel || !box) return;
        if (!sel.value) {
            box.innerHTML = '<p class="small text-muted mb-0">Chọn ngành để xem môn đã có và môn còn thiếu.</p>';
            $('roadDone').innerHTML = '';
            $('roadMiss').innerHTML = '';
            $('roadNote').textContent = '';
            return;
        }
        localStorage.setItem('ued_program', sel.value);
        if (window.syncProfile) window.syncProfile();
        const res = await fetch('/api/roadmap', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nganh: sel.value, courses: window.transcriptData || [] }),
        });
        const data = await res.json();
        if (!data.found) {
            box.innerHTML = `<p class="text-danger small mb-0">${esc(data.error || 'Không thấy chương trình')}</p>`;
            return;
        }
        box.innerHTML = `
            <div class="d-flex flex-wrap justify-content-between gap-2 mb-1">
                <strong>${esc(data.nganh)}</strong>
                <span>${data.percent}% · còn ${data.remaining_credits} TC</span>
            </div>
            <div class="progress mb-1"><div class="progress-bar" style="width:${data.percent}%">${data.percent}%</div></div>
            <p class="small mb-0">${data.done_count}/${data.required_count} học phần · ${data.done_credits}/${data.required_credits} tín chỉ trong file CTĐT.</p>`;
        const how = { ma_hp: 'mã', ten: 'tên', fuzzy: 'gần đúng' };
        $('roadDone').innerHTML = data.done.length
            ? data.done.map(item => `<tr><td>${esc(item.ten_mon)}</td><td class="text-center">${item.tin_chi}</td><td class="small">${how[item.how] || ''}</td></tr>`).join('')
            : '<tr><td colspan="3" class="text-muted small">Chưa khớp môn nào.</td></tr>';
        $('roadMiss').innerHTML = data.missing.length
            ? data.missing.map(item => `<tr><td>${esc(item.ten_mon)}</td><td class="text-center">${item.tin_chi}</td><td class="small">${esc(item.ma_hp)}</td></tr>`).join('')
            : '<tr><td colspan="3" class="text-success small">Đã khớp hết danh sách.</td></tr>';
        const extra = (data.extra || []).filter(Boolean);
        $('roadNote').textContent = (data.note || '') + (extra.length ? ` Môn đạt nhưng không nằm trong CTĐT này: ${extra.join(', ')}.` : '');
    }

    function paintSchedule() {
        const data = schedule();
        const body = $('ttBody');
        if (body) {
            const rows = data.classes.slice().sort((a, b) => a.day - b.day || a.start.localeCompare(b.start));
            body.innerHTML = rows.length ? rows.map(item => `
                <tr>
                    <td>${esc(item.name)}</td>
                    <td>${DAYS[item.day] || ''}</td>
                    <td>${esc(item.start)}–${esc(item.end)}</td>
                    <td>${esc(item.room)}</td>
                    <td class="text-center"><button type="button" class="btn btn-sm btn-link text-danger p-0" data-del-class="${esc(item.id)}">Xóa</button></td>
                </tr>`).join('') : '<tr><td colspan="5" class="text-muted small">Chưa có tiết nào.</td></tr>';
        }
        const list = $('exList');
        if (list) {
            const now = Date.now();
            const exams = data.exams.slice().sort((a, b) => String(a.at).localeCompare(String(b.at)));
            list.innerHTML = exams.length ? exams.map(item => {
                const when = new Date(item.at);
                const diff = when.getTime() - now;
                let count = 'Đã thi';
                if (!Number.isNaN(when.getTime()) && diff > 0) {
                    const days = Math.floor(diff / 86400000);
                    const hours = Math.floor((diff % 86400000) / 3600000);
                    count = days > 0 ? `Còn ${days} ngày ${hours} giờ` : `Còn ${hours} giờ`;
                } else if (!Number.isNaN(when.getTime()) && diff > -3600000) {
                    count = 'Đang đến giờ thi';
                }
                const label = Number.isNaN(when.getTime()) ? item.at : when.toLocaleString('vi-VN', { hour12: false });
                return `<div class="exam-row">
                    <div><b>${esc(item.name)}</b><div class="small text-muted">${esc(label)}${item.room ? ' · ' + esc(item.room) : ''}</div></div>
                    <div class="text-end"><div class="exam-count">${count}</div><button type="button" class="btn btn-sm btn-link text-danger p-0" data-del-exam="${esc(item.id)}">Xóa</button></div>
                </div>`;
            }).join('') : '<p class="small text-muted mb-0">Chưa có lịch thi.</p>';
        }
        if ($('ttStartDate') && data.start && !$('ttStartDate').value) $('ttStartDate').value = data.start;
    }

    function addClass() {
        const name = ($('ttName').value || '').trim();
        if (!name) { $('ttName').focus(); return; }
        const data = schedule();
        data.classes.push({
            id: 'c' + Date.now().toString(36),
            name,
            day: parseInt($('ttDay').value, 10),
            start: $('ttStart').value || '07:00',
            end: $('ttEnd').value || '08:50',
            room: ($('ttRoom').value || '').trim(),
        });
        $('ttName').value = '';
        saveSchedule(data);
    }

    function addExam() {
        const name = ($('exName').value || '').trim();
        const at = $('exWhen').value;
        if (!name || !at) return;
        const data = schedule();
        data.exams.push({ id: 'e' + Date.now().toString(36), name, at, room: ($('exRoom').value || '').trim() });
        $('exName').value = '';
        saveSchedule(data);
    }

    function icsEscape(value) {
        return String(value || '').replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;');
    }

    function icsStamp(date) {
        const pad = (n) => String(n).padStart(2, '0');
        return date.getFullYear() + pad(date.getMonth() + 1) + pad(date.getDate()) + 'T' + pad(date.getHours()) + pad(date.getMinutes()) + '00';
    }

    function nextWeekday(start, day) {
        const date = new Date(start.getFullYear(), start.getMonth(), start.getDate());
        const want = day === 8 ? 0 : day - 1;
        const delta = (want - date.getDay() + 7) % 7;
        date.setDate(date.getDate() + delta);
        return date;
    }

    function exportIcs() {
        const data = schedule();
        const startValue = $('ttStartDate').value;
        data.start = startValue;
        localStorage.setItem('ued_schedule_v1', JSON.stringify(data));
        if (window.syncProfile) window.syncProfile();
        const start = startValue ? new Date(startValue + 'T00:00:00') : new Date();
        const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//UED//Tinh diem//VI', 'CALSCALE:GREGORIAN'];
        data.classes.forEach(item => {
            const day = nextWeekday(start, item.day);
            const [sh, sm] = (item.start || '07:00').split(':').map(Number);
            const [eh, em] = (item.end || '08:50').split(':').map(Number);
            const begin = new Date(day.getFullYear(), day.getMonth(), day.getDate(), sh || 0, sm || 0);
            const end = new Date(day.getFullYear(), day.getMonth(), day.getDate(), eh || 0, em || 0);
            lines.push(
                'BEGIN:VEVENT',
                'UID:' + item.id + '@ued-tinh-diem',
                'SUMMARY:' + icsEscape(item.name),
                'LOCATION:' + icsEscape(item.room),
                'DTSTART:' + icsStamp(begin),
                'DTEND:' + icsStamp(end),
                'RRULE:FREQ=WEEKLY;COUNT=15;BYDAY=' + (ICS_DAY[item.day] || 'MO'),
                'END:VEVENT',
            );
        });
        data.exams.forEach(item => {
            const when = new Date(item.at);
            if (Number.isNaN(when.getTime())) return;
            const end = new Date(when.getTime() + 90 * 60000);
            lines.push(
                'BEGIN:VEVENT',
                'UID:' + item.id + '@ued-tinh-diem',
                'SUMMARY:' + icsEscape('Thi ' + item.name),
                'LOCATION:' + icsEscape(item.room),
                'DTSTART:' + icsStamp(when),
                'DTEND:' + icsStamp(end),
                'END:VEVENT',
            );
        });
        lines.push('END:VCALENDAR');
        const blob = new Blob([lines.join('\r\n')], { type: 'text/calendar' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'lich-ued.ics';
        link.click();
        URL.revokeObjectURL(link.href);
    }

    function summaryNumbers() {
        return {
            cpa: ($('displayGPA') || {}).textContent || '',
            gpa_gia_lap: ($('simulatedGPA') || {}).textContent || '',
            chenh_lech: ($('diffGPA') || {}).textContent || '',
            tin_chi_dat: ((window.transcriptData || []).reduce((sum, course) => {
                const points = { 'A+': 4, A: 4, 'B+': 3.5, B: 3, 'C+': 2.5, C: 2, 'D+': 1.5, D: 1, F: 0 }[course.diem_he_4];
                return sum + ((points > 0 || course.pass_only) ? (course.tin_chi || 0) : 0);
            }, 0)),
            tin_chi_muc_tieu: parseInt(($('targetCredits') || {}).value, 10) || 130,
        };
    }

    function fillPrintPack() {
        const pack = $('printPack');
        if (!pack) return;
        const summary = summaryNumbers();
        const rows = (items, cells) => items.map(item => '<tr>' + cells(item).map(cell => `<td>${esc(cell)}</td>`).join('') + '</tr>').join('');
        const bang2 = window.boardsSnapshot ? window.boardsSnapshot() : [];
        pack.innerHTML = `
            <h1>Bảng điểm — Trường Đại học Sư phạm, Đại học Đà Nẵng</h1>
            <p>CPA ${esc(summary.cpa)} · GPA giả lập ${esc(summary.gpa_gia_lap)} · Chênh lệch ${esc(summary.chenh_lech)} · ${summary.tin_chi_dat} / ${summary.tin_chi_muc_tieu} tín chỉ đã đạt</p>
            <h2>Điểm tổng</h2>
            <table><thead><tr><th>Môn</th><th>TC</th><th>Chữ</th><th>Hệ 10</th><th>Năm</th><th>Kỳ</th><th>Lần</th></tr></thead><tbody>
            ${rows(window.transcriptData || [], item => [item.ten_mon, item.tin_chi, item.diem_he_4 || '', item.diem_10 ?? '', item.nam_hoc || '', item.hoc_ky || '', item.lan || ''])}
            </tbody></table>
            <h2>Điểm học phần</h2>
            <table><thead><tr><th>Môn</th><th>TC</th><th>BP</th><th>GK</th><th>CK</th><th>Điểm</th><th>Chữ</th><th>Hệ 4</th></tr></thead><tbody>
            ${rows(bang2, item => [item.ten_mon, item.tin_chi, item.bp ?? '', item.gk ?? '', item.ck ?? '', item.score10 ?? '', item.letter || '', item.points ?? ''])}
            </tbody></table>`;
    }

    async function exportXlsx() {
        const bang2 = window.boardsSnapshot ? window.boardsSnapshot() : [];
        const res = await fetch('/api/export.xlsx', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                bang1: window.transcriptData || [],
                bang2,
                summary: summaryNumbers(),
            }),
        });
        if (!res.ok) return;
        const blob = await res.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'bang-diem-ued.xlsx';
        link.click();
        URL.revokeObjectURL(link.href);
    }

    function applyTheme(mode) {
        const dark = mode === 'dark';
        if (dark) document.documentElement.setAttribute('data-theme', 'dark');
        else document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('ued_theme', mode);
        const icon = $('themeBtn') && $('themeBtn').querySelector('i');
        if (icon) icon.className = dark ? 'fas fa-sun' : 'fas fa-moon';
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute('content', dark ? '#0c1726' : '#0b4ea2');
        refreshChart();
    }

    function initTheme() {
        const saved = localStorage.getItem('ued_theme');
        const mode = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        applyTheme(mode);
        if (!saved) localStorage.removeItem('ued_theme');
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (event) => {
            if (!localStorage.getItem('ued_theme')) applyTheme(event.matches ? 'dark' : 'light');
        });
    }

    $('profileSelect')?.addEventListener('change', () => applyProfile($('profileSelect').value));
    $('btnProfileAdd')?.addEventListener('click', addProfile);
    $('btnProfileRename')?.addEventListener('click', renameProfile);
    $('btnProfileDelete')?.addEventListener('click', deleteProfile);
    $('btnPdf')?.addEventListener('click', () => { fillPrintPack(); window.print(); });
    $('btnXlsx')?.addEventListener('click', exportXlsx);
    $('programSelect')?.addEventListener('change', loadRoadmap);
    $('btnAddClass')?.addEventListener('click', addClass);
    $('btnAddExam')?.addEventListener('click', addExam);
    $('btnIcs')?.addEventListener('click', exportIcs);
    $('ttBody')?.addEventListener('click', (event) => {
        const id = event.target.getAttribute('data-del-class');
        if (!id) return;
        const data = schedule();
        data.classes = data.classes.filter(item => item.id !== id);
        saveSchedule(data);
    });
    $('exList')?.addEventListener('click', (event) => {
        const id = event.target.getAttribute('data-del-exam');
        if (!id) return;
        const data = schedule();
        data.exams = data.exams.filter(item => item.id !== id);
        saveSchedule(data);
    });
    document.querySelectorAll('[data-panel="lotrinh"]').forEach(btn => btn.addEventListener('click', () => {
        loadPrograms().then(loadRoadmap).catch(() => {});
    }));
    document.querySelectorAll('[data-panel="lich"]').forEach(btn => btn.addEventListener('click', paintSchedule));
    $('themeBtn')?.addEventListener('click', () => {
        const dark = document.documentElement.getAttribute('data-theme') === 'dark';
        applyTheme(dark ? 'light' : 'dark');
    });

    initTheme();
    paintProfiles();
    paintSchedule();
    loadPrograms().catch(() => {});
    refreshChart();
    setInterval(paintSchedule, 60000);
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
})();
