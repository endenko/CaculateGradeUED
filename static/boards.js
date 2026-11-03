/* Điểm học phần: một bảng học kỳ, sửa từng môn, tối đa 5 phương án mục tiêu. */
(function () {
    const PLAN = [
        ['A+', 9.5, 4], ['A', 8.5, 4], ['B+', 8.0, 3.5], ['B', 7.0, 3],
        ['C+', 6.5, 2.5], ['C', 5.5, 2], ['D+', 5.0, 1.5], ['D', 4.0, 1]
    ];
    const POINTS = { 'A+': 4, 'A': 4, 'B+': 3.5, 'B': 3, 'C+': 2.5, 'C': 2, 'D+': 1.5, 'D': 1, 'F': 0 };
    const LOW = { C: 1, 'D+': 1, D: 1, F: 1 };
    let t2 = JSON.parse(localStorage.getItem('ued_table2') || 'null') || [];
    let editingId = null;
    let picked = null;
    let optionReq = 0;
    window.boardsOwnGpa = true;

    const $ = (id) => document.getElementById(id);
    function uid() { return Math.random().toString(36).slice(2, 10); }
    function esc(t) { return String(t ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
    function round1(x) { return Math.round((x + Number.EPSILON) * 10) / 10; }
    function round2(x) { return Math.round((x + Number.EPSILON) * 100) / 100; }
    function weights() {
        const b = num('wBp', 20), g = num('wGk', 30), c = num('wCk', 50);
        const s = b + g + c;
        return s ? [b / s, g / s, c / s] : [0.2, 0.3, 0.5];
    }
    function num(id, fallback) {
        const el = $(id);
        const n = el ? parseFloat(el.value) : NaN;
        return Number.isFinite(n) ? n : fallback;
    }
    function letterOf(score) {
        const s = round1(score);
        if (s >= 9.5) return ['A+', 4];
        if (s >= 8.5) return ['A', 4];
        if (s >= 8.0) return ['B+', 3.5];
        if (s >= 7.0) return ['B', 3];
        if (s >= 6.5) return ['C+', 2.5];
        if (s >= 5.5) return ['C', 2];
        if (s >= 5.0) return ['D+', 1.5];
        if (s >= 4.0) return ['D', 1];
        return ['F', 0];
    }
    function minCk(bp, gk, minScore, w) {
        const [wb, wg, wc] = w;
        if (!(wc > 0)) return null;
        for (let ck = 0; ck <= 10.001; ck = Math.round((ck + 0.1) * 10) / 10) {
            if (round1(bp * wb + gk * wg + ck * wc) >= minScore - 1e-9) return ck;
        }
        return null;
    }
    function badge(letter) {
        let cls = 'bg-F';
        const d = letter || '';
        if (d.includes('A+')) cls = 'bg-A-plus';
        else if (d.includes('A')) cls = 'bg-A';
        else if (d.includes('B')) cls = 'bg-B';
        else if (d.includes('C')) cls = 'bg-C';
        else if (d.includes('D')) cls = 'bg-D';
        return `<span class="badge-grade ${cls}">${esc(letter)}</span>`;
    }
    function semKey(c) {
        if (!c || c.term_unknown || !c.nam_hoc || !c.hoc_ky) return 'unknown';
        return c.nam_hoc + '|' + c.hoc_ky;
    }
    function semLabel(key) {
        if (!key || key === 'unknown') return 'Không xác định được kỳ/năm';
        const [year, ky] = key.split('|');
        return `${year} · Học kỳ ${ky === 'he' ? 'hè' : ky}`;
    }
    function currentKey() {
        return ($('semSelect') && $('semSelect').value) || 'unknown';
    }
    function visible() {
        const key = currentKey();
        return t2.filter(c => semKey(c) === key);
    }
    function save() { localStorage.setItem('ued_table2', JSON.stringify(t2)); }
    function blank(partial) {
        return Object.assign({
            id: uid(), ten_mon: '', tin_chi: 3, letter: null, points: null, score10: null,
            bp: null, gk: null, ck: null, nam_hoc: null, hoc_ky: null, term_unknown: true,
            lan: 1, in_progress: true, from_ocr: false,
        }, partial);
    }

    function fillSemSelect() {
        const sel = $('semSelect');
        if (!sel) return;
        const prev = sel.value;
        const keys = [];
        t2.forEach(c => { const k = semKey(c); if (!keys.includes(k)) keys.push(k); });
        if (!keys.length) keys.push('unknown');
        keys.sort((a, b) => (a === 'unknown') - (b === 'unknown') || (a < b ? 1 : -1));
        sel.innerHTML = keys.map(k => `<option value="${esc(k)}">${esc(semLabel(k))}</option>`).join('');
        if (keys.includes(prev)) sel.value = prev;
        else if (keys.includes('unknown') && keys.length === 1) sel.value = 'unknown';
        else sel.value = keys.find(k => k !== 'unknown') || keys[0];
    }

    function renderBody() {
        const body = $('hpBody');
        if (!body) return;
        const rows = visible();
        if (!rows.length) {
            body.innerHTML = '<tr><td colspan="6" class="small text-muted">Chưa có môn trong kỳ này. Tìm trong cơ sở dữ liệu hoặc quét ảnh portal.</td></tr>';
            return;
        }
        body.innerHTML = rows.map(c => {
            const low = c.tin_chi >= 3 && LOW[c.letter];
            const score = c.letter ? badge(c.letter) + (c.score10 != null ? `<div class="small text-muted">${c.score10}</div>` : '') : '<span class="text-muted">Đang học</span>';
            const term = semKey(c) === 'unknown' ? 'Không xác định được kỳ/năm' : `${esc(c.nam_hoc)}<br>HK${c.hoc_ky === 'he' ? ' hè' : esc(c.hoc_ky)} · lần ${c.lan || 1}`;
            return `<tr class="${low ? 'row-low' : ''}" data-row="${c.id}">
                <td>${esc(c.ten_mon)}</td>
                <td class="text-center fw-bold">${c.tin_chi}</td>
                <td class="text-center">${score}</td>
                <td class="text-center small hp-term">${term}</td>
                <td class="text-center"><button type="button" class="btn-sua" data-edit="${c.id}">Sửa</button></td>
                <td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger" data-del="${c.id}">×</button></td>
            </tr>`;
        }).join('');
        body.querySelectorAll('[data-edit]').forEach(btn => btn.addEventListener('click', () => openEditor(btn.dataset.edit)));
        body.querySelectorAll('[data-del]').forEach(btn => btn.addEventListener('click', () => {
            t2 = t2.filter(c => c.id !== btn.dataset.del);
            if (editingId === btn.dataset.del) closeEditor();
            save(); fillSemSelect(); renderBody(); renderOptions();
        }));
    }

    function openEditor(id) {
        editingId = id;
        const box = $('courseEditor');
        if (box) box.hidden = false;
        renderEditor();
    }
    function closeEditor() {
        editingId = null;
        const box = $('courseEditor');
        if (box) box.hidden = true;
    }
    function editing() { return t2.find(c => c.id === editingId) || null; }

    function readEditorInputs() {
        const row = editing();
        if (!row) return;
        ['bp', 'gk', 'ck'].forEach(k => {
            const el = $('ed' + (k === 'bp' ? 'Bp' : k === 'gk' ? 'Gk' : 'Ck'));
            if (!el) return;
            if (el.value === '') row[k] = null;
            else {
                const v = Math.min(10, Math.max(0, parseFloat(el.value)));
                row[k] = Number.isFinite(v) ? v : null;
            }
        });
        if (row.bp != null && row.gk != null && row.ck != null) {
            const w = weights();
            const score = round1(row.bp * w[0] + row.gk * w[1] + row.ck * w[2]);
            const [letter, pts] = letterOf(score);
            row.score10 = score; row.letter = letter; row.points = pts; row.in_progress = false;
        } else if (row.ck == null && !row.from_ocr) {
            row.letter = null; row.points = null; row.score10 = null; row.in_progress = true;
        }
        save();
    }

    function renderEditor() {
        const row = editing();
        const box = $('courseEditor');
        if (!box) return;
        if (!row) { box.hidden = true; return; }
        box.hidden = false;
        $('edTitle').textContent = row.ten_mon;
        $('edMeta').textContent = semKey(row) === 'unknown' ? 'Không xác định được kỳ/năm' : semLabel(semKey(row)) + (row.lan > 1 ? ' · lần ' + row.lan : '');
        $('edTc').textContent = row.tin_chi + ' tín chỉ';
        $('edBp').value = row.bp ?? '';
        $('edGk').value = row.gk ?? '';
        $('edCk').value = row.ck ?? '';
        const cur = $('edCurrent');
        if (row.letter && row.ck != null) {
            cur.innerHTML = `<div class="fw-bold">Kết quả: ${badge(row.letter)} ${row.score10 != null ? row.score10 : ''} · hệ 4: ${row.points}</div>`;
        } else if (row.from_ocr && row.letter) {
            cur.innerHTML = `<div class="fw-bold">Đã có điểm tổng kết ${badge(row.letter)}${row.score10 != null ? ' (' + row.score10 + ')' : ''}. Có thể nhập thành phần nếu muốn tính lại.</div>`;
        } else if (row.in_progress) {
            cur.innerHTML = '<div class="text-muted">Môn đang học — nhập bộ phận và giữa kỳ, để trống cuối kỳ để xem điểm cuối kỳ cần đạt.</div>';
        } else cur.innerHTML = '';
        renderNeeded(row);
    }

    function renderNeeded(row) {
        const host = $('edNeeded');
        if (!host) return;
        if (row.bp == null || row.gk == null || row.ck != null) { host.innerHTML = ''; return; }
        const w = weights();
        const cells = PLAN.map(([letter, minimum]) => {
            const ck = minCk(row.bp, row.gk, minimum, w);
            const over = ck == null || ck > 10;
            return `<div class="ck-cell ${over ? 'over' : ''}"><b>${letter}</b>${over ? 'không đạt (&gt;10)' : 'CK ≥ ' + ck.toFixed(1)}</div>`;
        }).join('');
        host.innerHTML = `<div class="small fw-bold mb-1">Cuối kỳ tối thiểu (thang 10) để được từng chữ</div><div class="ck-grid">${cells}</div>`;
    }

    function renderOptions() {
        const host = $('semOptions');
        if (!host) return;
        const target = parseFloat(($('semTarget') || {}).value || '3.2');
        const rows = visible();
        const req = ++optionReq;
        const payload = {
            target,
            weights: weights(),
            table2: rows.map(c => ({
                id: c.id, ten_mon: c.ten_mon, credits: c.tin_chi,
                bp: c.bp, gk: c.gk, ck: c.ck, letter: c.letter, points: c.points,
            })),
        };
        fetch('/api/semester_options', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
        }).then(r => r.json()).then(data => {
            if (req !== optionReq) return;
            const options = (data.options || []).slice(0, 5);
            if (!options.length) { host.innerHTML = '<div class="text-muted">Chưa có phương án.</div>'; return; }
            host.innerHTML = options.map((opt, i) => {
                const lines = (opt.courses || []).map(c => {
                    const ck = c.ck_over || c.min_ck == null ? 'CK &gt; 10' : 'CK ' + Number(c.min_ck).toFixed(1);
                    return `${esc(c.ten_mon)} <b>${esc(c.letter)}</b> (${ck})`;
                }).join(', ');
                const head = opt.courses && opt.courses.length ? lines : esc(opt.summary || '');
                const gpa = opt.gpa == null ? '—' : Number(opt.gpa).toFixed(2);
                return `<div class="sem-option"><span class="tag">${i + 1}. GPA ${gpa}</span> · ${esc(opt.label || '')}<div>${head}</div></div>`;
            }).join('');
        }).catch(() => {
            if (req === optionReq) host.innerHTML = '<div class="text-danger">Không tính được phương án.</div>';
        });
    }

    function cpa(rows) {
        let cr = 0, q = 0;
        rows.forEach(r => { cr += r.credits; q += r.points * r.credits; });
        return cr ? round2(q / cr) : null;
    }
    function renderOverall() {
        const out = $('solveOut');
        if (!out) return;
        const target = parseFloat(($('solveTarget') || {}).value || '3.2');
        const w = weights();
        const fixed = [];
        const variable = [];
        (window.transcriptData || []).forEach(c => {
            const letter = c.sim_grade || c.diem_he_4;
            if (POINTS[letter] == null) return;
            fixed.push({ id: 't1-' + c.ten_mon, ten_mon: c.ten_mon, credits: c.tin_chi, points: POINTS[letter], letter });
        });
        visible().forEach(c => {
            if (c.bp != null && c.gk != null && c.ck == null) variable.push(c);
            else if (c.points != null) fixed.push({ id: c.id, ten_mon: c.ten_mon, credits: c.tin_chi, points: c.points, letter: c.letter });
        });
        let assignment = null;
        const order = [['D', 4, 1], ['D+', 5, 1.5], ['C', 5.5, 2], ['C+', 6.5, 2.5], ['B', 7, 3], ['B+', 8, 3.5], ['A', 8.5, 4]];
        function bestUnder(course, cap) {
            let chosen = null;
            for (const [letter, minimum, points] of order) {
                const ck = minCk(course.bp, course.gk, minimum, w);
                if (ck == null || ck > cap + 1e-9) continue;
                chosen = { letter, points, ck, minimum };
            }
            return chosen;
        }
        function gpaOf(asg) {
            const rows = fixed.map(r => ({ credits: r.credits, points: r.points }));
            variable.forEach(c => rows.push({ credits: c.tin_chi, points: asg[c.id].points }));
            return cpa(rows);
        }
        if (!variable.length) {
            const now = cpa(fixed.map(r => ({ credits: r.credits, points: r.points })));
            const ok = now != null && now + 1e-9 >= target;
            out.innerHTML = `<b class="${ok ? 'text-success' : 'text-danger'}">${ok ? 'Đã đạt mốc' : 'Chưa đạt mốc'}</b> — CPA hiện ${now == null ? '—' : now.toFixed(2)}.`;
            return;
        }
        for (let cap = 0; cap <= 10.001; cap = Math.round((cap + 0.1) * 10) / 10) {
            const trial = {};
            let ok = true;
            for (const course of variable) {
                const plan = bestUnder(course, cap);
                if (!plan) { ok = false; break; }
                trial[course.id] = plan;
            }
            if (ok && gpaOf(trial) + 1e-9 >= target) { assignment = trial; break; }
        }
        const impossible = !assignment;
        if (impossible) {
            assignment = {};
            variable.forEach(c => { assignment[c.id] = { letter: 'A', points: 4, ck: minCk(c.bp, c.gk, 8.5, w), minimum: 8.5 }; });
        }
        const lines = variable.map(c => {
            const p = assignment[c.id];
            const ck = p.ck == null || p.ck > 10 ? 'CK &gt; 10' : p.ck.toFixed(1);
            return `<li><b>${esc(c.ten_mon)}</b>: ${p.letter}, CK tối thiểu ${ck}</li>`;
        }).join('');
        const achieved = gpaOf(assignment);
        out.innerHTML = `<div class="fw-bold">${impossible ? 'Bất khả thi trong kỳ này' : 'Có phương án'}</div>
            <div>CPA sau phân bổ: <b>${achieved == null ? '—' : achieved.toFixed(2)}</b> (mốc ${target})</div><ul>${lines}</ul>`;
    }

    function bind() {
        const storedW = JSON.parse(localStorage.getItem('ued_weights') || 'null');
        if (storedW) { $('wBp').value = storedW[0]; $('wGk').value = storedW[1]; $('wCk').value = storedW[2]; }
        $('semSelect').addEventListener('change', () => { renderBody(); renderOptions(); if (editing()) renderEditor(); });
        $('semTarget').addEventListener('change', () => renderOptions());
        $('btnAssignTerm').addEventListener('click', () => {
            const year = $('assignYear').value, ky = $('assignTerm').value;
            visible().forEach(c => { c.nam_hoc = year; c.hoc_ky = ky; c.term_unknown = false; });
            save(); fillSemSelect(); $('semSelect').value = year + '|' + ky; renderBody(); renderEditor(); renderOptions();
        });
        let timer;
        $('hpSearch').addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(suggest, 250);
        });
        $('btnAddHp').addEventListener('click', addPicked);
        ['wBp', 'wGk', 'wCk'].forEach(id => $(id).addEventListener('change', () => {
            localStorage.setItem('ued_weights', JSON.stringify([num('wBp', 20), num('wGk', 30), num('wCk', 50)]));
            t2.forEach(row => {
                if (row.bp != null && row.gk != null && row.ck != null) {
                    const w = weights();
                    const score = round1(row.bp * w[0] + row.gk * w[1] + row.ck * w[2]);
                    const [letter, pts] = letterOf(score);
                    row.score10 = score; row.letter = letter; row.points = pts;
                }
            });
            save(); renderBody(); renderEditor(); renderOptions();
        }));
        ['edBp', 'edGk', 'edCk'].forEach(id => $(id).addEventListener('input', () => {
            readEditorInputs(); renderNeeded(editing() || {}); renderBody(); renderOptions();
        }));
        $('edResult').addEventListener('click', () => { readEditorInputs(); renderEditor(); renderBody(); renderOptions(); });
        $('edClear').addEventListener('click', () => {
            const row = editing();
            if (!row) return;
            row.bp = row.gk = row.ck = null;
            if (!row.from_ocr) { row.letter = null; row.points = null; row.score10 = null; row.in_progress = true; }
            save(); renderEditor(); renderBody(); renderOptions();
        });
        const solve = $('btnSolve');
        if (solve) solve.addEventListener('click', renderOverall);
    }

    function suggest() {
        const input = $('hpSearch');
        const box = $('hpSug');
        const q = input.value.trim();
        if (q.length < 2) { box.style.display = 'none'; return; }
        fetch('/api/search_subject?q=' + encodeURIComponent(q)).then(r => r.json()).then(data => {
            box.innerHTML = (data || []).slice(0, 8).map(item => `<div class="suggestion-item small"><b>${esc(item.ten_mon)}</b> <span class="float-end">${item.tin_chi} TC</span></div>`).join('');
            box.style.display = data.length ? 'block' : 'none';
            [...box.children].forEach((el, i) => el.addEventListener('click', () => {
                picked = data[i];
                input.value = data[i].ten_mon;
                box.style.display = 'none';
            }));
        });
    }
    function addPicked() {
        if (!picked) return alert('Hãy chọn một môn trong danh sách gợi ý.');
        const key = currentKey();
        const unknown = key === 'unknown';
        const [year, ky] = unknown ? [null, null] : key.split('|');
        t2.push(blank({
            ten_mon: picked.ten_mon, tin_chi: picked.tin_chi,
            nam_hoc: year, hoc_ky: ky, term_unknown: unknown, in_progress: true,
        }));
        picked = null;
        $('hpSearch').value = '';
        save(); renderBody(); renderOptions();
    }

    window.boardsAddOcr = function (target, rows, term) {
        const known = term && term.nam_hoc && term.hoc_ky;
        rows.forEach(m => {
            if (String(target) === '1') {
                const letter = m.in_progress ? null : (POINTS[m.diem_he_4] != null ? m.diem_he_4 : (m.diem_10 != null ? letterOf(m.diem_10)[0] : null));
                if (!letter) return;
                if (!window.transcriptData.some(s => s.ten_mon === m.ten_mon && s.nam_hoc === (known ? term.nam_hoc : '') && s.hoc_ky === (known ? term.hoc_ky : ''))) {
                    window.transcriptData.push({
                        ...m, diem_he_4: letter, sim_grade: null,
                        nam_hoc: known ? term.nam_hoc : '',
                        hoc_ky: known ? term.hoc_ky : '',
                        lan: m.lan || 1,
                        term_unknown: !known,
                        pass_only: false,
                    });
                }
            } else if (!m.in_progress && (m.diem_10 != null || POINTS[m.diem_he_4] != null)) {
                const [letter, points] = m.diem_10 != null ? letterOf(m.diem_10) : [m.diem_he_4, POINTS[m.diem_he_4]];
                t2.push(blank({
                    ten_mon: m.ten_mon, tin_chi: m.tin_chi, letter, points, score10: m.diem_10,
                    in_progress: false, from_ocr: true, lan: m.lan || 1,
                    nam_hoc: known ? term.nam_hoc : null, hoc_ky: known ? term.hoc_ky : null, term_unknown: !known,
                }));
            } else {
                t2.push(blank({
                    ten_mon: m.ten_mon, tin_chi: m.tin_chi, in_progress: true, lan: m.lan || 1,
                    nam_hoc: known ? term.nam_hoc : null, hoc_ky: known ? term.hoc_ky : null, term_unknown: !known,
                }));
            }
        });
        save();
        if (String(target) === '1' && typeof saveData === 'function') saveData();
        fillSemSelect();
        if (String(target) !== '1') {
            const key = known ? term.nam_hoc + '|' + term.hoc_ky : 'unknown';
            if ([...$('semSelect').options].some(o => o.value === key)) $('semSelect').value = key;
            if (known) { $('assignYear').value = term.nam_hoc; $('assignTerm').value = term.hoc_ky; }
            renderBody(); renderOptions();
            const tab = document.querySelector('.site-menu [data-panel="diemhp"]');
            if (tab) tab.click();
        }
    };

    if ($('hpBody')) {
        bind();
        fillSemSelect();
        renderBody();
        renderOptions();
    }
})();
