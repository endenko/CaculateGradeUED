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
        const value = $('semSelect') && $('semSelect').value;
        return value || 'unknown';
    }
    function tongKey(c) {
        if (!c || c.term_unknown || !c.nam_hoc || !c.hoc_ky) return 'unknown';
        return c.nam_hoc + '|' + c.hoc_ky;
    }
    function rowsForView() {
        const key = currentKey();
        const own = t2.filter(c => semKey(c) === key);
        const names = new Set(own.map(c => c.ten_mon));
        const extra = (window.transcriptData || []).filter(c => tongKey(c) === key && !names.has(c.ten_mon)).map(c => ({
            id: 'tong-' + (c.nam_hoc || '') + '-' + (c.hoc_ky || '') + '-' + c.ten_mon,
            ten_mon: c.ten_mon, tin_chi: c.tin_chi, letter: c.diem_he_4,
            points: POINTS[c.diem_he_4] ?? null, score10: c.diem_10 ?? null,
            bp: null, gk: null, ck: null, nam_hoc: c.nam_hoc || null, hoc_ky: c.hoc_ky || null,
            term_unknown: !!c.term_unknown, lan: c.lan || 1, in_progress: false,
            from_ocr: true, fromTong: true,
        }));
        return own.concat(extra);
    }
    function visible() { return rowsForView(); }
    function save() { localStorage.setItem('ued_table2', JSON.stringify(t2)); }
    function blank(partial) {
        return Object.assign({
            id: uid(), ten_mon: '', tin_chi: 3, letter: null, points: null, score10: null,
            bp: null, gk: null, ck: null, nam_hoc: null, hoc_ky: null, term_unknown: true,
            lan: 1, in_progress: true, from_ocr: false,
        }, partial);
    }

    function collectKeys() {
        const keys = [];
        const add = (k) => { if (k && !keys.includes(k)) keys.push(k); };
        t2.forEach(c => add(semKey(c)));
        (window.transcriptData || []).forEach(c => add(tongKey(c)));
        const year = $('assignYear') && $('assignYear').value;
        const term = $('assignTerm') && $('assignTerm').value;
        if (year && term) add(year + '|' + term);
        if (!keys.length) add('2025-2026|2');
        keys.sort((a, b) => (a === 'unknown') - (b === 'unknown') || (a < b ? 1 : a > b ? -1 : 0));
        return keys;
    }
    function fillSemSelect() {
        const sel = $('semSelect');
        if (!sel) return;
        const prev = sel.value;
        const keys = collectKeys();
        sel.innerHTML = keys.map(k => `<option value="${esc(k)}">${esc(semLabel(k))}</option>`).join('');
        const populated = keys.find(k => k !== 'unknown' && (
            t2.some(c => semKey(c) === k) || (window.transcriptData || []).some(c => tongKey(c) === k)));
        if (keys.includes(prev)) sel.value = prev;
        else sel.value = populated || keys.find(k => k !== 'unknown') || keys[0];
    }
    function syncAssignFromKey(key) {
        if (!key || key === 'unknown' || !$('assignYear')) return;
        const [year, ky] = key.split('|');
        if ([...$('assignYear').options].some(o => o.value === year)) $('assignYear').value = year;
        if ([...$('assignTerm').options].some(o => o.value === ky)) $('assignTerm').value = ky;
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
            const row = visible().find(c => c.id === btn.dataset.del);
            if (row && row.fromTong) {
                window.transcriptData = (window.transcriptData || []).filter(c => tongKey(c) + c.ten_mon !== tongKey(row) + row.ten_mon);
                if (typeof saveData === 'function') saveData();
            } else {
                t2 = t2.filter(c => c.id !== btn.dataset.del);
            }
            if (editingId === btn.dataset.del) closeEditor();
            save(); fillSemSelect(); renderBody(); renderOptions();
        }));
    }

    function openEditor(id) {
        let row = t2.find(c => c.id === id) || visible().find(c => c.id === id);
        if (row && row.fromTong) {
            const copy = blank({
                ten_mon: row.ten_mon, tin_chi: row.tin_chi, letter: row.letter, points: row.points,
                score10: row.score10, nam_hoc: row.nam_hoc, hoc_ky: row.hoc_ky,
                term_unknown: row.term_unknown, lan: row.lan, in_progress: false, from_ocr: true,
            });
            t2.push(copy);
            save();
            row = copy;
        }
        editingId = row ? row.id : id;
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
            const first = options[0];
            if (!options.length || (first && (first.kind === 'empty' || first.kind === 'idle'))) {
                if (first && first.kind === 'idle') {
                    const gpa = first.gpa == null ? '' : `GPA học kỳ hiện tại ${Number(first.gpa).toFixed(2)}. `;
                    host.innerHTML = `<div class="text-muted">${gpa}Không có môn đang chờ điểm cuối kỳ.</div>`;
                } else {
                    host.innerHTML = '<div class="text-muted">Chưa có môn trong học kỳ này.</div>';
                }
                return;
            }
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
    const VI = (n) => (n == null || Number.isNaN(n) ? '—' : Number(n).toFixed(2).replace('.', ','));
    function outlookBundle() {
        const fixed = [];
        const variable = [];
        (window.transcriptData || []).forEach(c => {
            const letter = c.sim_grade || c.diem_he_4;
            if (POINTS[letter] == null) return;
            fixed.push({ ten_mon: c.ten_mon, credits: c.tin_chi, points: POINTS[letter], letter, lan: c.lan || 1 });
        });
        visible().forEach(c => {
            if (c.fromTong || fixed.some(r => r.ten_mon === c.ten_mon)) {
                if (c.bp != null && c.gk != null && c.ck == null) variable.push(c);
                return;
            }
            const open = c.in_progress || c.points == null || (c.bp != null && c.gk != null && c.ck == null);
            if (open) variable.push(c);
            else if (c.points != null) fixed.push({ ten_mon: c.ten_mon, credits: c.tin_chi, points: c.points, letter: c.letter, lan: c.lan || 1 });
        });
        return { fixed, variable };
    }
    function gpaOf(rows) {
        return cpa(rows.map(r => ({ credits: r.credits, points: r.points })));
    }
    function creditsUntil(quality, credits, target, grade) {
        if (!(credits > 0) || grade <= target) return null;
        for (let n = 0; n <= 400; n++) {
            if (round2((quality + n * grade) / (credits + n)) + 1e-9 >= target) return n;
        }
        return null;
    }
    function creditsAfford(quality, credits, target, grade) {
        if (grade + 1e-9 >= target) return null;
        let n = 0;
        for (let k = 1; k <= 400; k++) {
            if (round2((quality + k * grade) / (credits + k)) + 1e-9 < target) break;
            n = k;
        }
        return n;
    }
    function renderOverall() {
        const out = $('solveOut');
        if (!out) return;
        const target = parseFloat(($('solveTarget') || {}).value || '3.2');
        const w = weights();
        const { fixed, variable } = outlookBundle();
        const rows = fixed.map(r => ({ credits: r.credits, points: r.points }));
        let quality = 0, credits = 0;
        rows.forEach(r => { quality += r.points * r.credits; credits += r.credits; });
        const now = credits ? round2(quality / credits) : null;
        const reached = now != null && now + 1e-9 >= target;
        const gap = now == null ? null : round2(target - now);
        const pct = now == null ? 0 : Math.max(0, Math.min(100, (now / target) * 100));
        const gapHtml = now == null ? '<b>—</b>' : (reached
            ? `<b class="cpa-ok">Vượt ${VI(now - target)}</b>`
            : `<b class="cpa-gap">Thiếu ${VI(gap)}</b>`);
        let body = '';
        if (!credits && !variable.length) {
            body = '<p class="mb-0 text-muted">Chưa có điểm để tính CPA.</p>';
        } else if (!variable.length) {
            if (reached) {
                const b = creditsAfford(quality, credits, target, 3);
                const c = creditsAfford(quality, credits, target, 2);
                const room = (label, n) => n == null
                    ? `Điểm ${label} không thấp hơn mốc, thêm bao nhiêu cũng không kéo CPA xuống dưới.`
                    : (n === 0 ? `Thêm 1 tín chỉ điểm ${label} là CPA xuống dưới mốc.` : `Còn thêm được khoảng ${n} tín chỉ điểm ${label}.`);
                body = `<p class="mb-1">Đã đạt mốc, cao hơn ${VI(now - target)}.</p>
                    <p class="mb-0 text-muted">Nếu học tiếp: ${room('B (3,0)', b)} ${room('C (2,0)', c)}</p>`;
            } else {
                const a = creditsUntil(quality, credits, target, 4);
                const bp = creditsUntil(quality, credits, target, 3.5);
                const aText = a == null ? 'Điểm A cũng không kéo tới mốc.' : `Cần thêm khoảng <b>${a} tín chỉ điểm A (4,0)</b>.`;
                const bText = bp == null ? 'Điểm B+ (3,5) thấp hơn mốc nên không kéo CPA lên mốc này.' : `Nếu toàn B+ thì cần khoảng <b>${bp} tín chỉ</b>.`;
                body = `<p class="mb-1">Chưa có môn đang học trong kỳ đang xem.</p><p class="mb-0">${aText} ${bText}</p>`;
            }
        } else {
            const plans = outlookPlans(fixed, variable, target, w);
            const best = bestReachable(fixed, variable, w);
            if (plans.length) {
                body = `<p class="mb-1">Môn đang học cần những mức sau để CPA tới mốc. Dễ trước.</p>` + plans.slice(0, 5).map((opt, i) => {
                    const lines = opt.courses.map(c => c.components && c.min_ck != null
                        ? `${esc(c.ten_mon)} <b>${esc(c.letter)}</b> (CK ${Number(c.min_ck).toFixed(1)})`
                        : `${esc(c.ten_mon)} <b>${esc(c.letter)}</b>`).join(', ');
                    return `<div class="sem-option"><span class="tag">${i + 1}. CPA ${VI(opt.gpa)}</span> · ${esc(opt.label)}<div>${lines}</div></div>`;
                }).join('');
            } else {
                body = `<p class="mb-0">Kể cả môn đang học được mức cao nhất có thể, CPA chỉ tới <b>${VI(best)}</b>, vẫn thiếu ${VI(target - best)}. Không có cách nào trong các môn này.</p>`;
            }
        }
        const second = [...fixed, ...variable].reduce((s, c) => s + ((c.lan || 1) >= 2 ? Number(c.credits || c.tin_chi) || 0 : 0), 0);
        const program = parseFloat(($('targetCredits') || {}).value) || 130;
        const retake = second > program * 0.05
            ? `<p class="mb-0 mt-2 text-muted">Tín chỉ học từ lần 2 là ${second}, vượt 5% của ${program} tín chỉ chương trình. QĐ 1586 Điều 13 và QĐ 1473 Điều 25 hạ một bậc hạng xuất sắc hoặc giỏi.</p>`
            : '';
        out.innerHTML = `<div class="cpa-stats">
            <div><span>CPA hiện tại</span><b>${VI(now)}</b></div>
            <div><span>Tín chỉ tính</span><b>${credits || 0}</b></div>
            <div><span>Mốc</span><b>${VI(target)}</b></div>
            <div><span>Khoảng cách</span>${gapHtml}</div>
        </div>
        <div class="progress mb-2" aria-hidden="true"><div class="progress-bar" style="width:${pct.toFixed(0)}%">${reached ? 'Đạt' : pct.toFixed(0) + '%'}</div></div>
        ${body}${retake}`;
    }
    function outlookPlans(fixed, variable, target, w) {
        const letters = [['D', 4, 1], ['D+', 5, 1.5], ['C', 5.5, 2], ['C+', 6.5, 2.5], ['B', 7, 3], ['B+', 8, 3.5], ['A', 8.5, 4]];
        const prepared = variable.map(course => {
            const known = course.bp != null && course.gk != null && course.ck == null;
            const opts = [];
            letters.forEach(([letter, minimum, points]) => {
                if (!known) { opts.push({ letter, points, ck: null, known: false }); return; }
                const ck = minCk(course.bp, course.gk, minimum, w);
                if (ck == null || ck > 10) return;
                opts.push({ letter, points, ck, known: true });
            });
            return opts.length ? opts : [{ letter: 'A', points: 4, ck: null, known: false }];
        });
        const found = [];
        const base = fixed.map(r => ({ credits: r.credits, points: r.points }));
        function consider(choice) {
            const rows = base.slice();
            let maxCk = 0, sumCk = 0, saw = false;
            const courses = choice.map((opt, i) => {
                rows.push({ credits: variable[i].tin_chi, points: opt.points });
                if (opt.known && opt.ck != null) { saw = true; maxCk = Math.max(maxCk, opt.ck); sumCk += opt.ck; }
                return { ten_mon: variable[i].ten_mon, letter: opt.letter, points: opt.points, min_ck: opt.known ? opt.ck : null, components: opt.known, credits: variable[i].tin_chi };
            });
            const gpa = gpaOf(rows.map(r => ({ credits: r.credits, points: r.points, tin_chi: r.credits })));
            if (gpa == null || gpa + 1e-9 < target) return;
            found.push({ gpa, maxCk: saw ? maxCk : 99, sumCk, courses, label: maxCk >= 8.5 && saw ? 'Khó (cần CK ≥ 8,5)' : 'Khả thi' });
        }
        function walk(i, acc) {
            if (found.length > 2500) return;
            if (i === prepared.length) { consider(acc); return; }
            prepared[i].forEach(opt => { acc.push(opt); walk(i + 1, acc); acc.pop(); });
        }
        if (variable.length && variable.length <= 4) walk(0, []);
        found.sort((a, b) => a.maxCk - b.maxCk || a.sumCk - b.sumCk || a.courses.reduce((s, c) => s + c.points * c.credits, 0) - b.courses.reduce((s, c) => s + c.points * c.credits, 0));
        const seen = new Set();
        const out = [];
        found.forEach(p => {
            const key = p.courses.map(c => c.ten_mon + c.letter).join('|');
            if (seen.has(key)) return;
            seen.add(key);
            out.push(p);
        });
        return out.slice(0, 5);
    }
    function bestReachable(fixed, variable, w) {
        const letters = [['D', 4, 1], ['D+', 5, 1.5], ['C', 5.5, 2], ['C+', 6.5, 2.5], ['B', 7, 3], ['B+', 8, 3.5], ['A', 8.5, 4]];
        const rows = fixed.map(r => ({ credits: r.credits, points: r.points }));
        variable.forEach(course => {
            const known = course.bp != null && course.gk != null && course.ck == null;
            let best = 0;
            letters.forEach(([letter, minimum, points]) => {
                if (!known) { best = Math.max(best, points); return; }
                const ck = minCk(course.bp, course.gk, minimum, w);
                if (ck != null && ck <= 10) best = Math.max(best, points);
            });
            rows.push({ credits: course.tin_chi, points: best || 4 });
        });
        return gpaOf(rows.map(r => ({ credits: r.credits, points: r.points, tin_chi: r.credits })));
    }

    function bind() {
        const storedW = JSON.parse(localStorage.getItem('ued_weights') || 'null');
        if (storedW) { $('wBp').value = storedW[0]; $('wGk').value = storedW[1]; $('wCk').value = storedW[2]; }
        $('semSelect').addEventListener('change', () => {
            syncAssignFromKey($('semSelect').value);
            renderBody(); renderOptions(); renderOverall(); if (editing()) renderEditor();
        });
        const viewPickedTerm = () => {
            const key = $('assignYear').value + '|' + $('assignTerm').value;
            fillSemSelect();
            $('semSelect').value = key;
            renderBody(); renderOptions(); renderOverall();
        };
        $('assignYear').addEventListener('change', viewPickedTerm);
        $('assignTerm').addEventListener('change', viewPickedTerm);
        $('semTarget').addEventListener('change', () => renderOptions());
        $('btnAssignTerm').addEventListener('click', () => {
            const year = $('assignYear').value, ky = $('assignTerm').value;
            visible().forEach(c => {
                if (c.fromTong) {
                    const src = (window.transcriptData || []).find(s => s.ten_mon === c.ten_mon && tongKey(s) === semKey(c));
                    if (src) { src.nam_hoc = year; src.hoc_ky = ky; src.term_unknown = false; }
                } else {
                    c.nam_hoc = year; c.hoc_ky = ky; c.term_unknown = false;
                }
            });
            if (typeof saveData === 'function') saveData();
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
        const solveTarget = $('solveTarget');
        if (solveTarget) solveTarget.addEventListener('change', () => renderOverall());
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
        // Every scanned row belongs to the semester (Điểm học phần), including
        // in-progress courses with no score. Graded rows are also copied to
        // Điểm tổng. CPA counts the cumulative copy only, so nothing is added twice.
        const known = term && term.nam_hoc && term.hoc_ky;
        if (!window.transcriptData) window.transcriptData = [];
        rows.forEach(m => {
            const letter = m.in_progress ? null : (POINTS[m.diem_he_4] != null ? m.diem_he_4 : (m.diem_10 != null ? letterOf(m.diem_10)[0] : null));
            const nam = known ? term.nam_hoc : null;
            const ky = known ? term.hoc_ky : null;
            const key = known ? nam + '|' + ky : 'unknown';
            if (!t2.some(c => c.ten_mon === m.ten_mon && semKey(c) === key)) {
                if (letter) {
                    const [L, pts] = m.diem_10 != null ? letterOf(m.diem_10) : [letter, POINTS[letter]];
                    t2.push(blank({
                        ten_mon: m.ten_mon, tin_chi: m.tin_chi, letter: L, points: pts, score10: m.diem_10,
                        in_progress: false, from_ocr: true, lan: m.lan || 1,
                        nam_hoc: nam, hoc_ky: ky, term_unknown: !known,
                    }));
                } else {
                    t2.push(blank({
                        ten_mon: m.ten_mon, tin_chi: m.tin_chi, in_progress: true, lan: m.lan || 1,
                        nam_hoc: nam, hoc_ky: ky, term_unknown: !known,
                    }));
                }
            }
            if (letter && !window.transcriptData.some(s => s.ten_mon === m.ten_mon && tongKey(s) === key)) {
                window.transcriptData.push({
                    ...m, diem_he_4: letter, sim_grade: null,
                    nam_hoc: nam || '', hoc_ky: ky || '', lan: m.lan || 1,
                    term_unknown: !known, pass_only: false,
                });
            }
        });
        save();
        if (typeof saveData === 'function') saveData();
        fillSemSelect();
        const key = known ? term.nam_hoc + '|' + term.hoc_ky : 'unknown';
        if ([...$('semSelect').options].some(o => o.value === key)) $('semSelect').value = key;
        syncAssignFromKey(key);
        renderBody(); renderOptions(); renderOverall();
        const panel = (String(target) === '1' && !rows.some(m => m.in_progress)) ? 'bangdiem' : 'diemhp';
        const tab = document.querySelector(`.site-menu [data-panel="${panel}"]`);
        if (tab) tab.click();
    };

    if ($('hpBody')) {
        bind();
        fillSemSelect();
        renderBody();
        renderOptions();
        renderOverall();
    }
})();
