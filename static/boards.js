/* Hai bảng điểm + giải mục tiêu. Cùng công thức với solver.py (QĐ 1586). */
(function () {
    const PLAN = [
        ['D', 4.0, 1], ['D+', 5.0, 1.5], ['C', 5.5, 2], ['C+', 6.5, 2.5],
        ['B', 7.0, 3], ['B+', 8.0, 3.5], ['A', 8.5, 4]
    ];
    const LETTERS = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F'];
    const POINTS = { 'A+': 4, 'A': 4, 'B+': 3.5, 'B': 3, 'C+': 2.5, 'C': 2, 'D+': 1.5, 'D': 1, 'F': 0 };
    const LOW = { C: 1, 'D+': 1, D: 1, F: 1 };
    let t1 = JSON.parse(localStorage.getItem('ued_table1') || 'null');
    let t2 = JSON.parse(localStorage.getItem('ued_table2') || 'null');
    if (!t1) {
        t1 = (window.transcriptData || []).filter(c => c.diem_he_4).map(fromLegacy);
        t2 = [];
    }
    window.boardsOwnGpa = true;

    function fromLegacy(c) {
        return {
            id: uid(), ten_mon: c.ten_mon, tin_chi: c.tin_chi,
            letter: c.diem_he_4, points: POINTS[c.diem_he_4] ?? null,
            sim: false, sim_letter: 'A'
        };
    }
    function uid() { return Math.random().toString(36).slice(2, 10); }
    function round1(x) { return Math.round((x + Number.EPSILON) * 10) / 10; }
    function round2(x) { return Math.round((x + Number.EPSILON) * 100) / 100; }
    function esc(t) { return String(t ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
    function weights() {
        const b = num('wBp', 20), g = num('wGk', 30), c = num('wCk', 50);
        const s = b + g + c;
        return s ? [b / s, g / s, c / s] : [0.2, 0.3, 0.5];
    }
    function num(id, fallback) {
        const el = document.getElementById(id);
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
        if (wc <= 0) return null;
        for (let ck = 0; ck <= 10.001; ck = Math.round((ck + 0.1) * 10) / 10) {
            if (round1(bp * wb + gk * wg + ck * wc) >= minScore - 1e-9) return ck;
        }
        return null;
    }
    function cpa(rows) {
        let cr = 0, q = 0;
        rows.forEach(r => { cr += r.credits; q += r.points * r.credits; });
        return cr ? round2(q / cr) : null;
    }
    function effective1(c) {
        const sim = c.sim && POINTS[c.sim_letter] != null;
        return { points: sim ? POINTS[c.sim_letter] : c.points, letter: sim ? c.sim_letter : c.letter, credits: c.tin_chi };
    }
    function save() {
        localStorage.setItem('ued_table1', JSON.stringify(t1));
        localStorage.setItem('ued_table2', JSON.stringify(t2));
    }

    function paint() {
        const mount = document.getElementById('bang2Mount');
        if (!mount) return;
        const keepTarget = (document.getElementById('solveTarget') || {}).value;
        const keepScope = (document.getElementById('solveScope') || {}).value;
        const w = weights();
        const empty2 = '<tr><td colspan="4" class="small text-muted">Chưa có môn. Tìm trong cơ sở dữ liệu hoặc quét ảnh và chọn Bảng 2.</td></tr>';
        mount.innerHTML = `
        <div class="row g-3 align-items-start">
          <div class="col-lg-5">
            <div class="card p-3 mb-0">
              <h5 class="section-title">Bảng 2 — học kỳ hiện tại</h5>
              ${searchBox(2)}
              <div class="table-responsive"><table class="table table-sm align-middle ued-table mb-0">
                <thead><tr><th>Môn</th><th class="text-center">TC</th><th class="text-center">Chữ</th><th></th></tr></thead>
                <tbody>${t2.map(row2List).join('') || empty2}</tbody>
              </table></div>
            </div>
          </div>
          <div class="col-lg-7">
            <div class="card p-3 mb-0">
              <h5 class="section-title">Điểm học phần</h5>
              <div class="row g-2 mb-2 small">
                <div class="col-4"><label class="form-label small mb-1">BP / chuyên cần %</label><input id="wBp" class="form-control form-control-sm" type="number" min="0" max="100" value="${esc(savedWeight('wBp', 20))}"></div>
                <div class="col-4"><label class="form-label small mb-1">GK %</label><input id="wGk" class="form-control form-control-sm" type="number" min="0" max="100" value="${esc(savedWeight('wGk', 30))}"></div>
                <div class="col-4"><label class="form-label small mb-1">CK %</label><input id="wCk" class="form-control form-control-sm" type="number" min="0" max="100" value="${esc(savedWeight('wCk', 50))}"></div>
              </div>
              <p class="small text-muted mb-2">Điểm học phần = BP×${w[0].toFixed(2)} + GK×${w[1].toFixed(2)} + CK×${w[2].toFixed(2)}, làm tròn 1 số rồi xếp chữ theo QĐ 1586.</p>
              <div class="table-responsive"><table class="table table-sm align-middle ued-table mb-0">
                <thead><tr><th>Môn</th><th>BP</th><th>GK</th><th>CK</th><th class="text-center">Điểm</th><th class="text-center">Chữ</th><th class="text-center">Hệ 4</th></tr></thead>
                <tbody>${t2.map(row2Parts).join('') || '<tr><td colspan="7" class="small text-muted">Thêm môn ở Bảng 2 để nhập điểm thành phần.</td></tr>'}</tbody>
              </table></div>
            </div>
          </div>
        </div>
        <div class="card p-3 mt-3" id="solverCard">
          <h5 class="section-title">Mục tiêu điểm</h5>
          <div class="row g-2 align-items-end">
            <div class="col-md-4"><label class="form-label small">Mốc</label>
              <select id="solveTarget" class="form-select form-select-sm">
                <option value="3.6">Xuất sắc 3,6</option>
                <option value="3.2" selected>Giỏi 3,2</option>
                <option value="2.5">Khá 2,5</option>
              </select></div>
            <div class="col-md-4"><label class="form-label small">Phạm vi</label>
              <select id="solveScope" class="form-select form-select-sm">
                <option value="overall">CPA cả hai bảng</option>
                <option value="semester">GPA học kỳ này</option>
              </select></div>
            <div class="col-md-4"><button type="button" class="btn btn-ued btn-sm w-100" id="btnSolve">Tính điểm cần đạt</button></div>
          </div>
          <div id="solveOut" class="small mt-3"></div>
        </div>`;
        bind(mount);
        if (keepTarget && document.getElementById('solveTarget')) document.getElementById('solveTarget').value = keepTarget;
        if (keepScope && document.getElementById('solveScope')) document.getElementById('solveScope').value = keepScope;
    }
    function savedWeight(key, fallback) {
        return localStorage.getItem(key) || fallback;
    }
    function searchBox(which) {
        return `<div class="position-relative mb-2">
            <input class="form-control form-control-sm board-search" data-which="${which}" placeholder="${which === 1 ? 'Tìm môn trong CSDL, ví dụ Lập trình Java' : 'Tìm môn học kỳ này'}">
            <div class="suggestions-box" data-sug="${which}"></div>
            ${which === 1 ? `<div class="input-group input-group-sm mt-1"><input class="form-control grade-for-new" data-which="1" placeholder="Điểm chữ hoặc hệ 10"><button class="btn btn-ued" type="button" data-add="1">Thêm vào bảng 1</button></div>` : `<button class="btn btn-sm btn-outline-ued mt-1" type="button" data-add="2">Thêm vào bảng 2 (chưa có điểm)</button>`}
        </div>`;
    }
    function row1(c) {
        const low = c.tin_chi >= 3 && LOW[c.letter];
        const opts = LETTERS.map(L => `<option ${c.sim_letter === L ? 'selected' : ''}>${L}</option>`).join('');
        return `<tr class="${low ? 'row-low' : ''}"><td>${esc(c.ten_mon)}</td><td>${c.tin_chi}</td><td><b>${esc(c.letter || '')}</b></td>
            <td><label class="small"><input type="checkbox" data-sim="${c.id}" ${c.sim ? 'checked' : ''}> Giả lập</label>
            <select class="form-select form-select-sm mt-1" data-simletter="${c.id}">${opts}</select></td>
            <td><button class="btn btn-sm btn-outline-danger" data-del1="${c.id}">×</button></td></tr>`;
    }
    function row2List(c) {
        const shown = c.letter ? `<b>${esc(c.letter)}</b>` : '<span class="text-muted">—</span>';
        return `<tr><td>${esc(c.ten_mon)}</td><td class="text-center">${c.tin_chi}</td><td class="text-center">${shown}</td>
            <td class="text-end"><button class="btn btn-sm btn-outline-danger" data-del2="${c.id}" type="button">×</button></td></tr>`;
    }
    function row2Parts(c) {
        const inputs = ['bp', 'gk', 'ck'].map(k => `<td style="width:4.5rem"><input class="form-control form-control-sm" data-part="${k}" data-id="${c.id}" type="number" min="0" max="10" step="0.1" value="${c[k] ?? ''}"></td>`).join('');
        return `<tr><td>${esc(c.ten_mon)}</td>${inputs}
            <td class="text-center">${c.score10 != null ? c.score10 : '—'}</td>
            <td class="text-center">${c.letter ? `<b>${esc(c.letter)}</b>` : '—'}</td>
            <td class="text-center">${c.points != null ? c.points : '—'}</td></tr>`;
    }
    function bind(mount) {
        mount.querySelectorAll('.board-tabs button').forEach(btn => btn.addEventListener('click', () => {
            mount.querySelectorAll('.board-tabs button').forEach(b => b.classList.toggle('active', b === btn));
            mount.querySelectorAll('.board-col').forEach(col => col.classList.toggle('active', col.dataset.board === btn.dataset.board));
        }));
        mount.querySelectorAll('.board-search').forEach(input => {
            let timer;
            input.addEventListener('input', () => {
                clearTimeout(timer);
                timer = setTimeout(() => suggest(input), 250);
            });
        });
        mount.querySelectorAll('[data-add]').forEach(btn => btn.addEventListener('click', () => addManual(btn.dataset.add)));
        mount.querySelectorAll('[data-sim]').forEach(el => el.addEventListener('change', () => {
            const row = t1.find(c => c.id === el.dataset.sim); if (row) row.sim = el.checked; save(); paint();
        }));
        mount.querySelectorAll('[data-simletter]').forEach(el => el.addEventListener('change', () => {
            const row = t1.find(c => c.id === el.dataset.simletter); if (row) row.sim_letter = el.value; save(); paint();
        }));
        mount.querySelectorAll('[data-del1]').forEach(el => el.addEventListener('click', () => { t1 = t1.filter(c => c.id !== el.dataset.del1); save(); paint(); }));
        mount.querySelectorAll('[data-del2]').forEach(el => el.addEventListener('click', () => { t2 = t2.filter(c => c.id !== el.dataset.del2); save(); paint(); }));
        mount.querySelectorAll('[data-part]').forEach(el => el.addEventListener('change', () => {
            const row = t2.find(c => c.id === el.dataset.id); if (!row) return;
            const v = el.value === '' ? null : Math.min(10, Math.max(0, parseFloat(el.value)));
            row[el.dataset.part] = Number.isFinite(v) ? v : null;
            recomputeRow(row);
            save(); paint();
        }));
        ['wBp', 'wGk', 'wCk'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', () => { localStorage.setItem(id, el.value); t2.forEach(recomputeRow); save(); paint(); });
        });
        document.getElementById('btnSolve').addEventListener('click', () => {
            document.getElementById('solveOut').innerHTML = renderSolve();
        });
    }
    function recomputeRow(row) {
        if (row.bp == null || row.gk == null || row.ck == null) {
            if (row.ck == null && !(row.bp != null && row.gk != null)) return;
            if (row.bp != null && row.gk != null && row.ck == null) { row.letter = null; row.points = null; return; }
        }
        if (row.bp != null && row.gk != null && row.ck != null) {
            const w = weights();
            const score = round1(row.bp * w[0] + row.gk * w[1] + row.ck * w[2]);
            const [letter, pts] = letterOf(score);
            row.letter = letter; row.points = pts; row.score10 = score;
        }
    }
    let picked = { 1: null, 2: null };
    function suggest(input) {
        const which = input.dataset.which;
        const box = input.parentElement.querySelector('[data-sug]');
        const q = input.value.trim();
        if (q.length < 2) { box.style.display = 'none'; return; }
        fetch('/api/search_subject?q=' + encodeURIComponent(q)).then(r => r.json()).then(data => {
            box.innerHTML = data.slice(0, 8).map(item => `<div class="suggestion-item small"><b>${esc(item.ten_mon)}</b> <span class="float-end">${item.tin_chi} TC</span></div>`).join('');
            box.style.display = data.length ? 'block' : 'none';
            [...box.children].forEach((el, i) => el.addEventListener('click', () => {
                picked[which] = data[i];
                input.value = data[i].ten_mon;
                box.style.display = 'none';
            }));
        });
    }
    function addManual(which) {
        const item = picked[which];
        if (!item) return alert('Hãy chọn một môn trong danh sách gợi ý.');
        if (which === '1') {
            const raw = (document.querySelector('.grade-for-new') || {}).value || '';
            let letter, points;
            if (POINTS[raw.trim().toUpperCase()] != null) {
                letter = raw.trim().toUpperCase(); points = POINTS[letter];
            } else if (raw !== '' && !isNaN(parseFloat(raw))) {
                [letter, points] = letterOf(parseFloat(raw));
            } else return alert('Nhập điểm chữ (A, B+, …) hoặc điểm hệ 10.');
            t1.push({ id: uid(), ten_mon: item.ten_mon, tin_chi: item.tin_chi, letter, points, sim: false, sim_letter: 'A' });
        } else {
            t2.push({ id: uid(), ten_mon: item.ten_mon, tin_chi: item.tin_chi, bp: null, gk: null, ck: null, letter: null, points: null });
        }
        picked[which] = null;
        save(); paint();
    }
    function bestUnder(course, cap, w) {
        let chosen = null;
        for (const [letter, minimum, points] of PLAN) {
            const ck = minCk(course.bp, course.gk, minimum, w);
            if (ck == null || ck > cap + 1e-9) continue;
            chosen = { letter, min_score10: minimum, points, ck };
        }
        return chosen;
    }
    function gpaOf(fixed, variable, assignment) {
        const rows = fixed.map(r => ({ credits: r.credits, points: r.points }));
        variable.forEach(c => rows.push({ credits: c.credits, points: assignment[c.id].points }));
        return cpa(rows.map(r => ({ credits: r.credits, points: r.points, tin_chi: r.credits })));
    }
    function renderSolve() {
        const target = parseFloat(document.getElementById('solveTarget').value);
        const scope = document.getElementById('solveScope').value;
        const w = weights();
        const fixed = [];
        const variable = [];
        const fromBang1 = (window.transcriptData || []).filter(c => POINTS[c.sim_grade || c.diem_he_4] != null).map(c => ({
            id: 't1-' + c.ten_mon, ten_mon: c.ten_mon, tin_chi: c.tin_chi, credits: c.tin_chi,
            letter: c.sim_grade || c.diem_he_4, points: POINTS[c.sim_grade || c.diem_he_4],
        }));
        if (scope === 'overall') fromBang1.forEach(c => fixed.push(c));
        t2.forEach(c => {
            if (c.bp != null && c.gk != null && c.ck == null) variable.push({ id: c.id, ten_mon: c.ten_mon, credits: c.tin_chi, bp: c.bp, gk: c.gk });
            else if (c.points != null) fixed.push({ id: c.id, ten_mon: c.ten_mon, credits: c.tin_chi, points: c.points, letter: c.letter });
        });
        let assignment = null;
        for (let cap = 0; cap <= 10.001; cap = Math.round((cap + 0.1) * 10) / 10) {
            const trial = {};
            let ok = true;
            for (const course of variable) {
                const plan = bestUnder(course, cap, w);
                if (!plan) { ok = false; break; }
                trial[course.id] = plan;
            }
            if (ok && (gpaOf(fixed, variable, trial) == null ? false : gpaOf(fixed, variable, trial) + 1e-9 >= target)) {
                assignment = trial; break;
            }
        }
        let impossible = !assignment;
        if (!variable.length) {
            const now = cpa(fixed);
            return `<div class="${now != null && now >= target ? 'text-success' : 'text-danger'}"><b>${now != null && now >= target ? 'Khả thi (Dễ/Trung bình)' : 'Bất khả thi trong kỳ này'}</b> — CPA hiện ${now == null ? '—' : now.toFixed(2)}, chưa có môn nào đang chờ điểm CK.</div>`;
        }
        if (impossible) {
            assignment = {};
            variable.forEach(c => { assignment[c.id] = { letter: 'A', min_score10: 8.5, points: 4, ck: minCk(c.bp, c.gk, 8.5, w) }; });
        } else {
            let guard = 0;
            while (guard++ < 400) {
                const order = [...variable].sort((a, b) => assignment[b.id].ck - assignment[a.id].ck);
                let changed = false;
                for (const course of order) {
                    const cur = assignment[course.id];
                    const idx = PLAN.findIndex(p => p[0] === cur.letter);
                    if (idx <= 0) continue;
                    const [letter, minimum, points] = PLAN[idx - 1];
                    const ck = minCk(course.bp, course.gk, minimum, w);
                    const trial = { ...assignment, [course.id]: { letter, min_score10: minimum, points, ck } };
                    if (gpaOf(fixed, variable, trial) + 1e-9 >= target) { assignment = trial; changed = true; break; }
                }
                if (!changed) break;
            }
        }
        const maxCk = Math.max(...variable.map(c => assignment[c.id].ck == null ? 99 : assignment[c.id].ck));
        const label = (impossible || maxCk > 10) ? 'Bất khả thi trong kỳ này' : (maxCk >= 8.5 ? 'Khó (cần CK >= 8.5)' : 'Khả thi (Dễ/Trung bình)');
        const lines = variable.map(c => {
            const p = assignment[c.id];
            const ck = p.ck == null || p.ck > 10 ? 'không đạt nổi (CK > 10)' : p.ck.toFixed(1);
            return `<li><b>${esc(c.ten_mon)}</b> (${c.credits} TC): chữ <b>${p.letter}</b>, điểm học phần tối thiểu <b>${p.min_score10}</b>, CK tối thiểu <b>${ck}</b></li>`;
        }).join('');
        let retake = '';
        if (label.startsWith('Bất khả thi') && scope === 'overall') {
            const ideas = fromBang1.filter(c => c.points < 4)
                .map(c => ({ c, gain: 4 - c.points, highlight: c.tin_chi >= 3 && LOW[c.letter] }))
                .sort((a, b) => (b.highlight - a.highlight) || (b.gain - a.gain) || (b.c.tin_chi - a.c.tin_chi));
            if (ideas.length) {
                const top = ideas[0].c;
                const projectedRows = fromBang1.map(c => ({ credits: c.tin_chi, points: c.id === top.id ? 4 : c.points }))
                    .concat(t2.filter(c => c.points != null).map(c => ({ credits: c.tin_chi, points: c.points })));
                const projected = cpa(projectedRows.filter(r => r.points != null));
                retake = `<p class="mt-2">Nên học lại <b>${esc(top.ten_mon)}</b> (${top.tin_chi} TC, đang ${esc(top.letter)}) lên A — tăng ${(ideas[0].gain).toFixed(1)} điểm hệ 4 mỗi tín chỉ. CPA dự kiến nếu học lại môn này: <b>${projected == null ? '—' : projected.toFixed(2)}</b>.</p>`;
            }
        }
        const achieved = gpaOf(fixed, variable, assignment);
        return `<div class="fw-bold">${label}</div><div>CPA / GPA sau phân bổ: <b>${achieved == null ? '—' : achieved.toFixed(2)}</b> (mốc ${target})</div><ul>${lines}</ul>${retake}`;
    }

    window.boardsAddOcr = function (target, rows) {
        rows.forEach(m => {
            if (String(target) === '1') {
                const letter = LETTERS.includes(m.diem_he_4) ? m.diem_he_4 : (m.diem_10 != null ? letterOf(m.diem_10)[0] : null);
                if (!letter || POINTS[letter] == null) return;
                if (!window.transcriptData.some(s => s.ten_mon === m.ten_mon)) {
                    window.transcriptData.push({ ...m, diem_he_4: letter, sim_grade: null, nam_hoc: '', hoc_ky: '', lan: 1 });
                }
            } else if (m.diem_10 != null || (m.diem_he_4 && POINTS[m.diem_he_4] != null)) {
                const [letter, points] = m.diem_10 != null ? letterOf(m.diem_10) : [m.diem_he_4, POINTS[m.diem_he_4]];
                t2.push({ id: uid(), ten_mon: m.ten_mon, tin_chi: m.tin_chi, bp: null, gk: null, ck: null, letter, points, score10: m.diem_10 });
            } else {
                t2.push({ id: uid(), ten_mon: m.ten_mon, tin_chi: m.tin_chi, bp: null, gk: null, ck: null, letter: null, points: null });
            }
        });
        save();
        if (String(target) === '1' && typeof saveData === 'function') saveData();
        paint();
        if (String(target) === '2') {
            const tab = document.querySelector('[data-panel="hocphan"]');
            if (tab) tab.click();
        }
    };
    paint();
})();
