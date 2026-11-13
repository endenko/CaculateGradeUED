/* Nhắc lịch, học lại, học bổng, cảnh báo, chia sẻ, tra cứu. */
(function () {
    const $ = (id) => document.getElementById(id);
    const LEADS = { '1d': 24 * 3600000, '1h': 3600000 };

    function esc(value) {
        return String(value == null ? '' : value).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
    }

    function reminders() {
        try {
            return Object.assign({ leads: ['1d', '1h'], deadlines: [], enabled: false }, JSON.parse(localStorage.getItem('ued_reminders_v1') || 'null') || {});
        } catch (err) {
            return { leads: ['1d', '1h'], deadlines: [], enabled: false };
        }
    }

    function saveReminders(data) {
        localStorage.setItem('ued_reminders_v1', JSON.stringify(data));
        paintDeadlines();
        pushReminders();
    }

    function showBanner(text) {
        const banner = $('reminderBanner');
        if (!banner) return;
        banner.hidden = false;
        banner.innerHTML = `${esc(text)} <button type="button" id="bannerClose">Đóng</button>`;
        $('bannerClose').onclick = () => { banner.hidden = true; };
    }

    function upcoming() {
        const data = reminders();
        const leads = data.leads.map((key) => LEADS[key]).filter(Boolean);
        const events = [];
        (window.scheduleSnapshot ? window.scheduleSnapshot().exams : []).forEach((exam) => {
            const at = new Date(exam.at).getTime();
            if (!Number.isNaN(at)) events.push({ id: 'exam-' + exam.id, title: 'Sắp thi ' + exam.name, at, room: exam.room || '' });
        });
        data.deadlines.forEach((item) => {
            const at = new Date(item.at).getTime();
            if (!Number.isNaN(at)) events.push({ id: 'due-' + item.id, title: item.title, at, room: '' });
        });
        const items = [];
        events.forEach((event) => {
            leads.forEach((lead) => {
                items.push({
                    id: event.id + '-' + lead,
                    title: event.title,
                    body: (event.room ? event.room + ' · ' : '') + 'Nhắc trước ' + (lead >= LEADS['1d'] ? '1 ngày' : '1 giờ') + '. Chỉ chạy khi trang hoặc service worker đang mở.',
                    at: event.at,
                    lead,
                });
            });
        });
        return items;
    }

    function pushReminders() {
        const items = upcoming();
        if (!('serviceWorker' in navigator)) return;
        navigator.serviceWorker.ready.then((reg) => {
            if (reg.active) reg.active.postMessage({ type: 'reminders', items });
        }).catch(() => {});
    }

    function checkReminders() {
        const now = Date.now();
        upcoming().forEach((item) => {
            const due = item.at - item.lead;
            if (due > now || now - due > 120000) return;
            const key = 'ued_fired_' + item.id;
            if (sessionStorage.getItem(key)) return;
            sessionStorage.setItem(key, '1');
            showBanner(item.title + '. ' + item.body);
            if (window.Notification && Notification.permission === 'granted') {
                try { new Notification(item.title, { body: item.body, icon: '/static/ued-logo.png' }); } catch (err) {}
            }
        });
    }

    async function enableReminders() {
        const data = reminders();
        data.enabled = true;
        data.leads = [];
        if ($('leadDay').checked) data.leads.push('1d');
        if ($('leadHour').checked) data.leads.push('1h');
        saveReminders(data);
        if (!window.Notification) {
            showBanner('Trình duyệt này không có thông báo. Nhắc vẫn hiện trên trang khi bạn đang mở.');
            return;
        }
        let perm = Notification.permission;
        if (perm === 'default') perm = await Notification.requestPermission();
        if (perm !== 'granted') {
            showBanner('Bạn chưa cho phép thông báo. Nhắc sẽ hiện trên trang này khi trình duyệt đang mở.');
        }
        checkReminders();
    }

    function paintDeadlines() {
        const box = $('deadlineList');
        if (!box) return;
        const data = reminders();
        if ($('leadDay')) $('leadDay').checked = data.leads.includes('1d');
        if ($('leadHour')) $('leadHour').checked = data.leads.includes('1h');
        box.innerHTML = data.deadlines.length ? data.deadlines.map((item) => `
            <div class="d-flex justify-content-between gap-2 py-1">
                <span>${esc(item.title)} · ${esc(item.at.replace('T', ' '))}</span>
                <button type="button" class="btn btn-sm btn-link text-danger p-0" data-del-due="${esc(item.id)}">Xóa</button>
            </div>`).join('') : '<p class="text-muted mb-0">Chưa có hạn đăng ký.</p>';
    }

    function addDeadline() {
        const title = ($('deadlineTitle').value || '').trim();
        const at = $('deadlineWhen').value;
        if (!title || !at) return;
        const data = reminders();
        data.deadlines.push({ id: 'd' + Date.now().toString(36), title, at });
        $('deadlineTitle').value = '';
        saveReminders(data);
    }

    async function refreshAdvise() {
        if (!$('retakeOut')) return;
        const courses = (window.transcriptData || []).map((course) => ({
            ten_mon: course.ten_mon,
            tin_chi: course.tin_chi,
            diem_he_4: course.diem_he_4,
            diem_10: course.diem_10,
            nam_hoc: course.nam_hoc,
            hoc_ky: course.hoc_ky,
            lan: course.lan || 1,
            pass_only: !!course.pass_only,
        }));
        let data = null;
        try {
            const res = await fetch('/api/advise', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    courses,
                    target: ($('retakeTarget') || {}).value || 'A',
                    drl: ($('scholarDrl') || {}).value,
                    discipline: !!($('scholarDiscipline') || {}).checked,
                    program_credits: parseFloat(($('targetCredits') || {}).value) || 130,
                }),
            });
            data = await res.json();
        } catch (err) {
            return;
        }
        if (!data || !data.success) return;
        const retake = data.retake;
        const singles = (retake.singles || []).map((item) =>
            `<div class="goal-row"><b>${esc(item.ten_mon)}</b> · ${item.tin_chi} TC<br>CPA sau học lại: <b>${Number(item.cpa_after).toFixed(2)}</b> (+${Number(item.gain).toFixed(2)})</div>`
        ).join('');
        const pairs = (retake.pairs || []).map((item) =>
            `<div class="goal-row">${esc(item.courses.join(' + '))}<br>CPA: <b>${Number(item.cpa_after).toFixed(2)}</b> (+${Number(item.gain).toFixed(2)})</div>`
        ).join('');
        $('retakeOut').innerHTML = `<p class="mb-1">CPA theo quy chế: <b>${retake.cpa_now == null ? '—' : Number(retake.cpa_now).toFixed(2)}</b> <span class="text-muted">(F đang nợ không tính)</span></p>`
            + (singles || '<p class="text-muted">Chưa có môn học lại làm CPA tăng với điểm mục tiêu này.</p>')
            + (pairs ? '<p class="mt-2 mb-1 fw-bold">Tổ hợp</p>' + pairs : '')
            + `<p class="text-muted mt-2 mb-0">${esc(retake.rule)}</p>`;
        const scholar = data.scholarship;
        const rows = (scholar.semesters || []).map((sem) => {
            const label = sem.tier ? `Đạt mức ${sem.tier}` : 'Chưa đủ';
            const why = (sem.reasons || []).join(' ');
            return `<div class="goal-row"><b>${esc(sem.nam_hoc)} · HK${esc(sem.hoc_ky)}</b> · GPA ${sem.gpa == null ? '—' : Number(sem.gpa).toFixed(2)}<br>${esc(label)}${why ? ' — ' + esc(why) : ''}</div>`;
        }).join('');
        const tiers = (scholar.tiers || []).map((tier) => `${tier.name}: GPA ≥ ${tier.gpa}, rèn luyện ≥ ${tier.drl} (${tier.drl_label})`).join('; ');
        $('scholarOut').innerHTML = (rows || '<p class="text-muted">Chưa có học kỳ chính trong bảng điểm.</p>')
            + `<p class="text-muted mt-2 mb-0">${esc(scholar.label)}. ${esc(tiers)}. Tối thiểu ${scholar.min_credits} tín chỉ, không có môn không đạt. ${esc(scholar.cite)}</p>`;
        const warn = data.warning;
        const sems = (warn.semesters || []).filter((sem) => sem.warning).map((sem) =>
            `<div class="warn-chip">${esc(sem.nam_hoc)} HK${esc(sem.hoc_ky)}: ${esc((sem.warning_reasons || []).join(' '))}</div>`
        ).join('');
        $('warningOut').innerHTML = `<p class="fw-bold mb-1">${esc(warn.label)}</p>`
            + (sems || '<p class="text-muted">Không có học kỳ đang cảnh báo.</p>')
            + (warn.exit_steps || []).map((step) => `<p class="mb-1">${esc(step)}</p>`).join('')
            + `<p class="text-muted mb-0">${esc(warn.cite)}</p>`;
    }

    window.adviseRefresh = function () {
        clearTimeout(window.adviseRefresh._t);
        window.adviseRefresh._t = setTimeout(refreshAdvise, 250);
    };

    function openLookup() {
        $('lookupModal').hidden = false;
        $('lookupInput').focus();
    }

    function closeLookup() { $('lookupModal').hidden = true; }

    let lookupTimer = null;
    async function runLookup() {
        const q = $('lookupInput').value.trim();
        const box = $('lookupResults');
        if (q.length < 2) { box.innerHTML = ''; return; }
        const res = await fetch('/api/lookup?q=' + encodeURIComponent(q));
        const rows = await res.json();
        box.innerHTML = rows.length ? rows.map((row) => `
            <div class="lookup-hit">
                <b>${esc(row.ten_mon)}</b>
                <div class="small text-muted">${esc(row.ma_hp)} · ${row.tin_chi || '—'} TC · ${esc(row.khoa)}</div>
                <div class="small">${esc((row.programs || []).slice(0, 3).join(' · '))}${row.program_count > 3 ? ' · +' + (row.program_count - 3) : ''}</div>
            </div>`).join('') : '<p class="small text-muted mb-0">Không thấy môn.</p>';
        if (!res.ok && rows.error) box.innerHTML = `<p class="small text-danger">${esc(rows.error)}</p>`;
    }

    function b64url(bytes) {
        let text = '';
        bytes.forEach((byte) => { text += String.fromCharCode(byte); });
        return btoa(text).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
    }

    function b64urlDecode(text) {
        const pad = text.length % 4 === 0 ? '' : '='.repeat(4 - (text.length % 4));
        const bin = atob(text.replace(/-/g, '+').replace(/_/g, '/') + pad);
        return Uint8Array.from(bin, (ch) => ch.charCodeAt(0));
    }

    async function encodeShare(obj) {
        const raw = new TextEncoder().encode(JSON.stringify(obj));
        if (typeof CompressionStream === 'undefined') return '0.' + b64url(raw);
        const stream = new Blob([raw]).stream().pipeThrough(new CompressionStream('deflate'));
        const packed = new Uint8Array(await new Response(stream).arrayBuffer());
        return '1.' + b64url(packed);
    }

    async function decodeShare(token) {
        const kind = token.slice(0, 2);
        const bytes = b64urlDecode(token.slice(2));
        let json;
        if (kind === '1.' && typeof DecompressionStream !== 'undefined') {
            const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate'));
            json = await new Response(stream).text();
        } else {
            json = new TextDecoder().decode(bytes);
        }
        return JSON.parse(json);
    }

    async function openShare() {
        const payload = {
            v: 1,
            name: ($('profileName') || {}).value || 'Bảng điểm',
            courses: (window.transcriptData || []).map((course) => ({
                ten_mon: course.ten_mon, tin_chi: course.tin_chi, diem_he_4: course.diem_he_4,
                diem_10: course.diem_10, nam_hoc: course.nam_hoc, hoc_ky: course.hoc_ky, lan: course.lan || 1,
            })),
        };
        const token = await encodeShare(payload);
        const url = location.origin + location.pathname + '#share=' + token;
        $('shareLink').value = url;
        $('shareQr').innerHTML = '';
        if (window.qrcode) {
            const qr = qrcode(0, 'M');
            qr.addData(url);
            qr.make();
            $('shareQr').innerHTML = qr.createSvgTag(4, 2);
        }
        $('shareModal').hidden = false;
    }

    async function showShared() {
        const hash = location.hash || '';
        if (!hash.startsWith('#share=')) {
            $('shareView').hidden = true;
            return;
        }
        let data;
        try {
            data = await decodeShare(decodeURIComponent(hash.slice('#share='.length)));
        } catch (err) {
            $('shareBody').innerHTML = '<p class="text-danger">Không đọc được liên kết này.</p>';
            $('shareView').hidden = false;
            return;
        }
        const rows = (data.courses || []).map((course) =>
            `<tr><td>${esc(course.ten_mon)}</td><td class="text-center">${esc(course.tin_chi)}</td><td class="text-center">${esc(course.diem_he_4 || '')}</td><td>${esc(course.nam_hoc || '')} ${course.hoc_ky ? 'HK' + esc(course.hoc_ky) : ''}</td></tr>`
        ).join('');
        $('shareBody').innerHTML = `<p class="fw-bold">${esc(data.name || 'Bảng điểm')}</p>
            <div class="table-scroll"><table class="table table-sm ued-table"><thead><tr><th>Môn</th><th>TC</th><th>Điểm</th><th>Kỳ</th></tr></thead><tbody>${rows || '<tr><td colspan="4">Trống</td></tr>'}</tbody></table></div>`;
        $('shareView').hidden = false;
        $('shareView').scrollIntoView({ block: 'start' });
    }

    $('btnLookup')?.addEventListener('click', openLookup);
    $('btnLookupMenu')?.addEventListener('click', () => {
        document.getElementById('siteMenu')?.classList.remove('open');
        openLookup();
    });
    $('lookupClose')?.addEventListener('click', closeLookup);
    $('lookupModal')?.addEventListener('click', (event) => { if (event.target === $('lookupModal')) closeLookup(); });
    $('lookupInput')?.addEventListener('input', () => {
        clearTimeout(lookupTimer);
        lookupTimer = setTimeout(runLookup, 200);
    });
    document.addEventListener('keydown', (event) => {
        const tag = (document.activeElement && document.activeElement.tagName) || '';
        if (event.key === '/' && !event.ctrlKey && !event.metaKey && !['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) {
            event.preventDefault();
            openLookup();
        }
        if (event.key === 'Escape') { closeLookup(); $('shareModal').hidden = true; }
    });
    $('btnShare')?.addEventListener('click', () => openShare().catch(() => showBanner('Không tạo được liên kết trên trình duyệt này.')));
    $('shareClose')?.addEventListener('click', () => { $('shareModal').hidden = true; });
    $('shareCopy')?.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText($('shareLink').value); } catch (err) { $('shareLink').select(); }
    });
    $('btnCloseShare')?.addEventListener('click', () => { history.pushState('', document.title, location.pathname); showShared(); });
    $('btnAddDeadline')?.addEventListener('click', addDeadline);
    $('btnRemind')?.addEventListener('click', () => enableReminders().catch(() => showBanner('Không bật được nhắc.')));
    $('deadlineList')?.addEventListener('click', (event) => {
        const id = event.target.getAttribute('data-del-due');
        if (!id) return;
        const data = reminders();
        data.deadlines = data.deadlines.filter((item) => item.id !== id);
        saveReminders(data);
    });
    function saveLeadChoices() {
        const data = reminders();
        data.leads = [];
        if ($('leadDay')?.checked) data.leads.push('1d');
        if ($('leadHour')?.checked) data.leads.push('1h');
        saveReminders(data);
    }
    $('leadDay')?.addEventListener('change', saveLeadChoices);
    $('leadHour')?.addEventListener('change', saveLeadChoices);
    $('retakeTarget')?.addEventListener('change', refreshAdvise);
    $('scholarDrl')?.addEventListener('change', refreshAdvise);
    $('scholarDiscipline')?.addEventListener('change', refreshAdvise);
    window.addEventListener('hashchange', showShared);
    paintDeadlines();
    pushReminders();
    checkReminders();
    setInterval(checkReminders, 20000);
    refreshAdvise();
    showShared();
})();
