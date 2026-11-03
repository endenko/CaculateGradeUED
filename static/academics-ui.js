/* Giao diện GPA, điểm thành phần, điểm rèn luyện, bảng tin. Logic điểm nằm ở /api. */
(function () {
    const $ = (id) => document.getElementById(id);
    let newsCache = null;
    let newsFilter = 'all';
    let timer = null;

    const PRESET_1586 = [
        { name: 'Đánh giá quá trình', weight: 0.2, exam: false },
        { name: 'Kiểm tra giữa kỳ', weight: 0.3, exam: false },
        { name: 'Thi kết thúc học phần', weight: 0.5, exam: true },
    ];
    const PRESET_1473 = [
        { name: 'Bộ phận 1 (chuyên cần, bài tập…)', weight: 0.1, exam: false },
        { name: 'Bộ phận 2 (tiểu luận, thực hành…)', weight: 0.1, exam: false },
        { name: 'Kiểm tra giữa kỳ', weight: 0.3, exam: false },
        { name: 'Thi kết thúc học phần', weight: 0.5, exam: true },
    ];

    function showPanel(name) {
        document.querySelectorAll('.tool-panel').forEach(el => { el.hidden = el.id !== 'panel-' + name; });
        document.querySelectorAll('.site-menu [data-panel], .site-top [data-panel]').forEach(btn => btn.classList.toggle('active', btn.dataset.panel === name));
        document.getElementById('siteMenu')?.classList.remove('open');
        const menuBtn = document.getElementById('menuBtn');
        if (menuBtn) menuBtn.setAttribute('aria-expanded', 'false');
        if (name === 'tintuc' && !newsCache) loadNews();
    }

    document.querySelectorAll('[data-panel]').forEach(btn => {
        btn.addEventListener('click', () => {
            showPanel(btn.dataset.panel);
            if (!btn.dataset.guide) return;
            const item = document.getElementById('guide-' + btn.dataset.guide);
            if (!item) return;
            item.open = true;
            item.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    });
    const guideHint = document.getElementById('guideHint');
    if (guideHint && localStorage.getItem('ued_guide_hint') !== 'off') guideHint.hidden = false;
    document.getElementById('dismissGuideHint')?.addEventListener('click', () => {
        localStorage.setItem('ued_guide_hint', 'off');
        if (guideHint) guideHint.hidden = true;
    });
    document.getElementById('menuBtn')?.addEventListener('click', () => {
        const menu = document.getElementById('siteMenu');
        const open = menu.classList.toggle('open');
        document.getElementById('menuBtn').setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    function payload() {
        return {
            rule: $('ruleSelect').value,
            program_credits: parseFloat($('targetCredits').value) || 130,
            discipline_canh_cao: $('disciplineFlag').checked,
            courses: (window.transcriptData || []).map(c => ({
                ten_mon: c.ten_mon,
                tin_chi: c.tin_chi,
                diem_10: c.diem_10 != null && c.diem_10 !== '' ? c.diem_10 : null,
                diem_he_4: c.diem_he_4,
                nam_hoc: c.nam_hoc || '',
                hoc_ky: c.hoc_ky || '',
                lan: c.lan || 1,
                pass_only: !!c.pass_only,
                sim_grade: c.sim_grade || null,
            })),
        };
    }

    async function refreshAcademics() {
        if (window.boardsOwnGpa) return;
        const box = $('sideSummary');
        if (!box) return;
        try {
            const res = await fetch('/api/academics', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload()) });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Lỗi tính điểm');
            renderSummary(data);
        } catch (err) {
            box.innerHTML = `<div class="text-danger">${escape(err.message)}</div>`;
        }
    }
    window.refreshAcademics = function () {
        clearTimeout(timer);
        timer = setTimeout(refreshAcademics, 120);
    };

    function renderSummary(data) {
        const c = data.cumulative;
        $('displayGPA').textContent = c.gpa == null ? '—' : Number(c.gpa).toFixed(2);
        const sim = data.simulated && data.simulated.gpa != null ? Number(data.simulated.gpa).toFixed(2) : '—';
        $('simulatedGPA').textContent = sim;
        const real = c.gpa == null ? null : Number(c.gpa);
        const simN = data.simulated && data.simulated.gpa != null ? Number(data.simulated.gpa) : null;
        const diffEl = $('diffGPA');
        if (real == null || simN == null) {
            diffEl.textContent = '—';
        } else {
            const d = (simN - real).toFixed(2);
            diffEl.textContent = (d > 0 ? '+' : '') + d;
        }
        const hang = c.downgraded ? `${c.hang_sau_ha_bac} (hạ từ ${c.hang_tot_nghiep})` : (c.hang_tot_nghiep || c.hoc_luc || 'chưa đủ điểm');
        $('sideSummary').innerHTML = `
            <div>Học lực tích lũy: <b>${escape(c.hoc_luc || '—')}</b></div>
            <div>Hạng tốt nghiệp nếu xét hôm nay: <b>${escape(hang)}</b></div>
            <div>Tín chỉ đã đạt: <b>${c.passed_credits || 0}</b>${c.pass_only_credits ? ` + ${c.pass_only_credits} TC loại P` : ''}</div>
            <div>Còn thiếu khoảng: <b>${data.remaining_credits}</b> TC</div>
            <div>Tín chỉ đang nợ (F): <b>${data.debt_credits}</b></div>`;
        const warns = (data.semesters || []).filter(s => s.warning);
        $('sideWarn').innerHTML = warns.length
            ? warns.map(s => `<div class="warn-chip"><b>${termLabel(s)}</b> — lần cảnh báo thứ ${s.warnings_so_far}<ul>${s.warning_reasons.map(r => `<li>${escape(r)}</li>`).join('')}</ul></div>`).join('')
            : '<div class="text-success">Không thấy căn cứ cảnh báo trên các học kỳ chính đã nhập.</div>'
            + (data.dismissal_note ? `<div class="mt-2">${escape(data.dismissal_note)}</div>` : '');
        if (c.downgrade_reasons && c.downgrade_reasons.length) {
            $('sideWarn').innerHTML += `<div class="mt-2"><b>Hạ bậc tốt nghiệp:</b><ul>${c.downgrade_reasons.map(r => `<li>${escape(r)}</li>`).join('')}</ul></div>`;
        }
        const gpaBox = $('gpaDetail');
        if (gpaBox) {
            const semRows = (data.semesters || []).map(s => `<tr><td>${termLabel(s)}</td><td class="text-center">${fmt(s.gpa)}</td><td class="text-center">${s.credits}</td><td class="text-center">${fmt(s.cumulative_gpa)}</td><td>${s.warning ? 'Cảnh báo' : '—'}</td></tr>`).join('');
            const yearRows = (data.years || []).map(y => `<tr><td>${escape(y.nam_hoc)}</td><td class="text-center">${fmt(y.gpa)}</td><td class="text-center">${y.credits}</td></tr>`).join('');
            const unver = (data.unverified || []).map(u => `<li>${escape(u.ten_mon || '')}: ${escape(u.reason || '')}</li>`).join('');
            gpaBox.innerHTML = `
                <div class="table-responsive"><table class="table table-sm ued-table"><thead><tr><th>Học kỳ</th><th class="text-center">GPA kỳ</th><th class="text-center">TC tính</th><th class="text-center">GPA tích lũy sau kỳ</th><th>Cảnh báo</th></tr></thead><tbody>${semRows || '<tr><td colspan="5">Chưa có môn gắn học kỳ.</td></tr>'}</tbody></table></div>
                <h6 class="mt-3 text-ued">Theo năm học</h6>
                <table class="table table-sm"><thead><tr><th>Năm</th><th class="text-center">GPA năm</th><th class="text-center">TC</th></tr></thead><tbody>${yearRows || '<tr><td colspan="3">—</td></tr>'}</tbody></table>
                ${unver ? `<div class="small"><b>Chưa đưa vào GPA:</b><ul>${unver}</ul></div>` : ''}
                <ul class="small text-muted mb-0">${(data.notes || []).map(n => `<li>${escape(n)}</li>`).join('')}</ul>`;
        }
        const goals = $('goalDetail');
        if (goals) {
            goals.innerHTML = (data.goals || []).map(g => {
                let msg;
                if (g.reached) msg = 'Đã đạt trên phần đã có.';
                else if (g.needed == null) msg = g.reached ? 'Đã đạt.' : 'Chưa đạt và không còn tín chỉ trống trong ô tổng.';
                else if (g.already) msg = 'Đã đủ điểm chất lượng, kể cả nếu phần còn lại điểm 0.';
                else if (!g.possible) msg = `Cần trung bình ${g.needed} — cao hơn 4,0.`;
                else msg = `Cần trung bình hệ 4 là ${g.needed} trên ${data.remaining_credits} tín chỉ còn lại.`;
                return `<div class="goal-row"><b>${escape(g.label)}</b> (từ ${g.target})<div class="small">${msg}</div></div>`;
            }).join('');
        }
        const target = parseFloat($('targetCredits').value) || 130;
        const passed = (c.passed_credits || 0) + (c.pass_only_credits || 0);
        const percent = Math.min(100, Math.round((passed / target) * 100));
        const bar = $('gradProgressBar');
        bar.style.width = percent + '%';
        bar.textContent = percent + '%';
        $('progressText').textContent = `${passed} / ${target} TC đã đạt`;
    }

    function termLabel(s) {
        const ky = s.hoc_ky === 'he' ? 'Hè' : 'HK' + s.hoc_ky;
        return `${ky} ${s.nam_hoc}`;
    }
    function fmt(v) { return v == null ? '—' : Number(v).toFixed(2); }
    function escape(t) { return String(t == null ? '' : t).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

    function partEditor(rows) {
        $('partRows').innerHTML = rows.map((p, i) => `
            <div class="row g-2 align-items-end mb-2 part-row">
                <div class="col-md-5"><label class="form-label small">Tên cột</label><input class="form-control form-control-sm part-name" value="${escape(p.name)}"></div>
                <div class="col-4 col-md-2"><label class="form-label small">Trọng số</label><input class="form-control form-control-sm part-w" type="number" step="0.05" min="0" max="1" value="${p.weight}"></div>
                <div class="col-4 col-md-2"><label class="form-label small">Điểm</label><input class="form-control form-control-sm part-s" type="number" step="0.1" min="0" max="10" placeholder="0–10"></div>
                <div class="col-4 col-md-3"><div class="form-check"><input class="form-check-input part-exam" type="radio" name="examCol" ${p.exam ? 'checked' : ''}><label class="form-check-label small">Là điểm thi</label></div></div>
            </div>`).join('');
    }
    if ($('btnPreset1586') && $('partRows')) {
    $('btnPreset1586').addEventListener('click', () => partEditor(PRESET_1586));
    $('btnPreset1473').addEventListener('click', () => partEditor(PRESET_1473));
    $('btnPresetBlank').addEventListener('click', () => partEditor([
        { name: 'Chuyên cần', weight: 0, exam: false },
        { name: 'Giữa kỳ', weight: 0, exam: false },
        { name: 'Cuối kỳ', weight: 0, exam: true },
    ]));
    partEditor(PRESET_1586);

    $('btnComponent').addEventListener('click', async () => {
        const rows = [...document.querySelectorAll('.part-row')];
        const parts = rows.map(row => ({
            name: row.querySelector('.part-name').value,
            weight: parseFloat(row.querySelector('.part-w').value),
            score: row.querySelector('.part-s').value === '' ? null : parseFloat(row.querySelector('.part-s').value),
            exam: row.querySelector('.part-exam').checked,
        }));
        const out = $('componentOut');
        try {
            const res = await fetch('/api/components', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ parts }) });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Không tính được');
            const cur = data.current ? `Điểm học phần làm tròn <b>${data.current.rounded}</b> → <b>${data.current.letter}</b> (${data.current.points} điểm hệ 4).` : 'Chưa nhập điểm thi — bảng dưới là điểm thi cần đạt.';
            const lines = data.needed.map(n => `<tr><td>${n.letter}</td><td>${n.min_course_score}</td><td>${n.points}</td><td>${n.exam_score == null ? 'Không đạt được' : n.exam_score.toFixed(1)}</td></tr>`).join('');
            out.innerHTML = `<div class="mb-2">${cur}</div><table class="table table-sm ued-table"><thead><tr><th>Chữ</th><th>Điểm học phần tối thiểu</th><th>Hệ 4</th><th>Điểm thi cần</th></tr></thead><tbody>${lines}</tbody></table>`;
        } catch (err) {
            out.innerHTML = `<div class="text-danger small">${escape(err.message)}</div>`;
        }
    });
    }

    const DRL_GROUPS = [
        ['hoc_tap', 'I. Ý thức học tập (20)', [['Đi học chuyên cần, đúng giờ, đủ điều kiện dự thi', 4], ['Câu lạc bộ học thuật, ngoại khóa', 2], ['NCKH hoặc thi sinh viên giỏi', 2], ['Không vi phạm quy chế thi, kiểm tra', 6], ['Lớp công nhận tinh thần vượt khó', 2]]],
        ['noi_quy', 'II. Chấp hành nội quy, quy chế (25)', [['Chấp hành văn bản chỉ đạo của ngành và ĐHĐN', 6], ['Sinh hoạt chính trị, cuộc vận động', 4], ['Nội quy, quy chế nhà trường', 10], ['Đóng học phí đúng hạn', 5]]],
        ['hoat_dong', 'III. Hoạt động chính trị, xã hội, văn hóa, thể thao (20)', [['Tuần sinh hoạt công dân', 10], ['Hoạt động do trường và ĐHĐN điều động', 6], ['Công ích, tình nguyện', 2], ['Tuyên truyền phòng chống tệ nạn', 2]]],
        ['cong_dan', 'IV. Ý thức công dân (25)', [['Chủ trương, chính sách, pháp luật', 4], ['Bảo hiểm y tế bắt buộc', 10], ['An toàn và văn hóa giao thông', 5], ['Hoạt động được khen thưởng', 4], ['Giúp người gặp khó khăn', 2]]],
        ['can_bo', 'V. Cán bộ lớp, đoàn thể hoặc thành tích (10)', [['Hoàn thành nhiệm vụ quản lý lớp, Đoàn, Hội', 3], ['Kỹ năng tổ chức', 2], ['Hỗ trợ hoạt động chung', 3], ['Bằng khen, giấy khen, thư khen', 2]]],
    ];
    $('drlFields').innerHTML = DRL_GROUPS.map(([key, title, items]) => `
        <div class="col-12"><div class="fw-semibold small text-ued">${title}</div>
        ${items.map(([name, max]) => `<label class="d-flex justify-content-between gap-2 small py-1"><span>${name}</span><input class="form-control form-control-sm drl-item" data-group="${key}" data-max="${max}" type="number" min="0" max="${max}" value="0" style="width:4.5rem"></label>`).join('')}
        ${key === 'hoc_tap' ? `<label class="d-flex justify-content-between gap-2 small py-1"><span>ĐTBCHK (chỉ một mức)</span><select class="form-select form-select-sm drl-item" data-group="hoc_tap" data-max="4" style="width:8rem"><option value="0">Dưới 2,0 → 0</option><option value="2">2,0–3,19 → 2</option><option value="4">3,2–4,0 → 4</option></select></label>` : ''}
        </div>`).join('') + `<div class="col-md-6"><label class="form-label small">Kỷ luật đang chịu (Điều 10)</label>
                <select id="drlDiscipline" class="form-select">
                    <option value="none">Không</option>
                    <option value="khien_trach">Khiển trách — không xếp quá Khá</option>
                    <option value="canh_cao">Cảnh cáo — không xếp quá Trung bình</option>
                    <option value="dinh_chi">Đình chỉ học tập — không đánh giá</option>
                    <option value="buoc_thoi_hoc">Buộc thôi học — không đánh giá</option>
                </select></div>`;

    $('btnDrl').addEventListener('click', async () => {
        const scores = { hoc_tap: 0, noi_quy: 0, hoat_dong: 0, cong_dan: 0, can_bo: 0 };
        document.querySelectorAll('.drl-item').forEach(el => {
            const n = parseInt(el.value, 10) || 0;
            const cap = parseInt(el.dataset.max, 10);
            scores[el.dataset.group] += Math.max(0, Math.min(cap, n));
        });
        const out = $('drlOut');
        try {
            const res = await fetch('/api/drl', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scores, discipline: $('drlDiscipline').value }) });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Không xếp loại được');
            out.innerHTML = `<div class="drl-score">${data.total}<span>/100</span></div><div>Xếp loại: <b>${escape(data.band || 'Không đánh giá')}</b>${data.raw_band && data.band && data.raw_band !== data.band ? ` (điểm thô thuộc loại ${escape(data.raw_band)})` : ''}</div>${data.note ? `<div class="small mt-1">${escape(data.note)}</div>` : ''}`;
        } catch (err) {
            out.innerHTML = `<div class="text-danger small">${escape(err.message)}</div>`;
        }
    });

    const TABS = [['all', 'Tất cả'], ['thac_si', 'Thạc sĩ / Sau đại học'], ['hoc_tap', 'Học tập / Đào tạo'], ['tieng_anh', 'Tiếng Anh'], ['quoc_phong', 'Quốc phòng'], ['hoc_bong', 'Học bổng'], ['khac', 'Khác']];

    function renderNews() {
        const tabs = $('newsTabs');
        tabs.innerHTML = TABS.map(([k, label]) => `<button type="button" class="nav-pill ${newsFilter === k ? 'active' : ''}" data-cat="${k}">${label}</button>`).join('');
        tabs.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => { newsFilter = btn.dataset.cat; renderNews(); }));
        const posts = (newsCache.posts || []).filter(p => newsFilter === 'all' || p.category === newsFilter);
        $('newsList').innerHTML = posts.length ? posts.map(p => `
            <article class="news-item">
                <div class="small text-muted">${escape(p.date)} · ${escape(p.category_label)}</div>
                <a href="${escape(p.url)}" target="_blank" rel="noopener">${escape(p.title)}</a>
                <p class="small mb-0">${escape(p.excerpt)}</p>
            </article>`).join('') : '<p class="small text-muted">Không có bài trong mục này.</p>';
        const cal = newsCache.calendar || [];
        $('newsCal').innerHTML = cal.length ? cal.map(e => `
            <div class="cal-item"><b>${escape(e.date)}</b> <span class="badge ${e.kind === 'han' ? 'badge-gold' : 'bg-secondary'}">${escape(e.label)}</span>
            <div class="small"><a href="${escape(e.url)}" target="_blank" rel="noopener">${escape(e.title)}</a></div>
            <div class="small text-muted">${escape(e.snippet)}</div></div>`).join('') : '<p class="small text-muted">Chưa thấy ngày đủ dd/mm/yyyy trong các bài vừa tải.</p>';
        const when = newsCache.fetched_at ? new Date(newsCache.fetched_at * 1000).toLocaleString('vi-VN') : '';
        $('newsMeta').textContent = `Nguồn ${newsCache.source || ''} · cache ${newsCache.cache || ''}${newsCache.stale ? ' (bản cũ, lần tải mới lỗi)' : ''} · ${when}`;
    }

    async function loadNews() {
        $('newsList').innerHTML = '<p class="small">Đang tải bài từ ued.udn.vn…</p>';
        try {
            const res = await fetch('/api/news');
            newsCache = await res.json();
            renderNews();
        } catch (err) {
            $('newsList').innerHTML = `<p class="text-danger small">${escape(err.message)}</p>`;
        }
    }
    $('btnReloadNews').addEventListener('click', () => { newsCache = null; loadNews(); });

    ['ruleSelect', 'targetCredits', 'disciplineFlag'].forEach(id => {
        const el = $(id);
        if (el) el.addEventListener('change', () => window.refreshAcademics());
    });
    window.refreshAcademics();
})();
