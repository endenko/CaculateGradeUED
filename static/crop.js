/* Cắt ảnh trên máy người dùng trước khi gửi OCR. */
(function () {
    const $ = (id) => document.getElementById(id);
    let img = null;
    let done = null;
    let quarter = 0;
    let straight = 0;
    let zoom = 1;
    let panX = 0;
    let panY = 0;
    let crop = { x: 20, y: 20, w: 200, h: 120 };
    let drag = null;
    const pointers = new Map();
    let pinch = null;

    function stageBox() {
        const stage = $('cropStage');
        return { w: stage.clientWidth, h: stage.clientHeight };
    }

    function rad() {
        return (quarter * 90 + straight) * Math.PI / 180;
    }

    function rotatedSize() {
        const a = Math.abs(rad());
        const c = Math.abs(Math.cos(a));
        const s = Math.abs(Math.sin(a));
        return {
            w: img.width * c + img.height * s,
            h: img.width * s + img.height * c,
        };
    }

    function fitScale() {
        const st = stageBox();
        const rot = rotatedSize();
        if (!rot.w || !rot.h) return 1;
        return Math.min(st.w / rot.w, st.h / rot.h);
    }

    function clamp(box) {
        const st = stageBox();
        const min = 48;
        const next = { ...box };
        next.w = Math.max(min, next.w);
        next.h = Math.max(min, next.h);
        if (next.x < 0) { next.w += next.x; next.x = 0; }
        if (next.y < 0) { next.h += next.y; next.y = 0; }
        if (next.x + next.w > st.w) next.w = st.w - next.x;
        if (next.y + next.h > st.h) next.h = st.h - next.y;
        next.w = Math.max(min, Math.min(next.w, st.w));
        next.h = Math.max(min, Math.min(next.h, st.h));
        next.x = Math.max(0, Math.min(next.x, st.w - next.w));
        next.y = Math.max(0, Math.min(next.y, st.h - next.h));
        return next;
    }

    function paint() {
        const canvas = $('cropCanvas');
        const st = stageBox();
        if (!img || st.w < 2 || st.h < 2) return;
        const dpr = Math.min(2, window.devicePixelRatio || 1);
        canvas.width = Math.round(st.w * dpr);
        canvas.height = Math.round(st.h * dpr);
        const ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.fillStyle = '#10233f';
        ctx.fillRect(0, 0, st.w, st.h);
        ctx.save();
        ctx.translate(st.w / 2 + panX, st.h / 2 + panY);
        ctx.rotate(rad());
        const scale = fitScale() * zoom;
        ctx.scale(scale, scale);
        ctx.drawImage(img, -img.width / 2, -img.height / 2);
        ctx.restore();
        const box = $('cropBox');
        box.style.left = crop.x + 'px';
        box.style.top = crop.y + 'px';
        box.style.width = crop.w + 'px';
        box.style.height = crop.h + 'px';
    }

    function suggest() {
        const maxSide = 220;
        const scale = maxSide / Math.max(img.width, img.height);
        const sample = document.createElement('canvas');
        sample.width = Math.max(1, Math.round(img.width * scale));
        sample.height = Math.max(1, Math.round(img.height * scale));
        const ctx = sample.getContext('2d', { willReadFrequently: true });
        ctx.drawImage(img, 0, 0, sample.width, sample.height);
        const data = ctx.getImageData(0, 0, sample.width, sample.height).data;
        const bgAt = (x, y) => {
            const i = (y * sample.width + x) * 4;
            return [data[i], data[i + 1], data[i + 2]];
        };
        const bg = bgAt(1, 1);
        let minX = sample.width;
        let minY = sample.height;
        let maxX = 0;
        let maxY = 0;
        let hits = 0;
        for (let y = 0; y < sample.height; y += 2) {
            for (let x = 0; x < sample.width; x += 2) {
                const i = (y * sample.width + x) * 4;
                const delta = Math.abs(data[i] - bg[0]) + Math.abs(data[i + 1] - bg[1]) + Math.abs(data[i + 2] - bg[2]);
                if (delta < 50) continue;
                hits += 1;
                if (x < minX) minX = x;
                if (y < minY) minY = y;
                if (x > maxX) maxX = x;
                if (y > maxY) maxY = y;
            }
        }
        const st = stageBox();
        if (hits < 40 || quarter !== 0 || straight !== 0) {
            crop = clamp({ x: st.w * 0.06, y: st.h * 0.08, w: st.w * 0.88, h: st.h * 0.84 });
            return;
        }
        const view = fitScale() * zoom;
        const cx = st.w / 2 + panX;
        const cy = st.h / 2 + panY;
        const left = (minX / scale - img.width / 2) * view + cx;
        const top = (minY / scale - img.height / 2) * view + cy;
        const right = (maxX / scale - img.width / 2) * view + cx;
        const bottom = (maxY / scale - img.height / 2) * view + cy;
        crop = clamp({ x: left - 4, y: top - 4, w: right - left + 8, h: bottom - top + 8 });
    }

    function resetView() {
        quarter = 0;
        straight = 0;
        zoom = 1;
        panX = 0;
        panY = 0;
        if ($('cropStraight')) $('cropStraight').value = '0';
        if ($('cropZoom')) $('cropZoom').value = '1';
        if (stageBox().h < 8) {
            requestAnimationFrame(resetView);
            return;
        }
        suggest();
        paint();
    }

    function exportJpeg() {
        const view = fitScale() * zoom;
        let outW = Math.max(1, Math.round(crop.w / view));
        let outH = Math.max(1, Math.round(crop.h / view));
        const cap = 2000 / Math.max(outW, outH);
        if (cap < 1) {
            outW = Math.max(1, Math.round(outW * cap));
            outH = Math.max(1, Math.round(outH * cap));
        }
        const canvas = document.createElement('canvas');
        canvas.width = outW;
        canvas.height = outH;
        const ctx = canvas.getContext('2d');
        const st = stageBox();
        ctx.setTransform(outW / crop.w, 0, 0, outH / crop.h, 0, 0);
        ctx.translate(-crop.x, -crop.y);
        ctx.translate(st.w / 2 + panX, st.h / 2 + panY);
        ctx.rotate(rad());
        ctx.scale(view, view);
        ctx.drawImage(img, -img.width / 2, -img.height / 2);
        return new Promise((resolve) => {
            canvas.toBlob((blob) => resolve(new File([blob], 'scan.jpg', { type: 'image/jpeg' })), 'image/jpeg', 0.92);
        });
    }

    function pointerPos(ev) {
        const rect = $('cropStage').getBoundingClientRect();
        return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
    }

    function pairDistance() {
        const pts = [...pointers.values()];
        const dx = pts[0].x - pts[1].x;
        const dy = pts[0].y - pts[1].y;
        return Math.hypot(dx, dy) || 1;
    }

    function onDown(ev) {
        if (ev.target.closest('.crop-tools, .crop-actions')) return;
        $('cropStage').setPointerCapture(ev.pointerId);
        pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
        if (pointers.size >= 2) {
            pinch = { dist: pairDistance(), zoom };
            drag = null;
            return;
        }
        const pos = pointerPos(ev);
        const handle = ev.target.dataset ? ev.target.dataset.h : '';
        if (handle) drag = { type: 'resize', handle, ...pos, crop: { ...crop } };
        else if (ev.target.closest('#cropBox')) drag = { type: 'move', ...pos, crop: { ...crop } };
        else drag = { type: 'pan', x: ev.clientX, y: ev.clientY, panX, panY };
    }

    function onMove(ev) {
        if (!pointers.has(ev.pointerId)) return;
        pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
        if (pointers.size >= 2 && pinch) {
            zoom = Math.min(4, Math.max(1, pinch.zoom * pairDistance() / pinch.dist));
            $('cropZoom').value = String(zoom);
            paint();
            return;
        }
        if (!drag) return;
        if (drag.type === 'pan') {
            panX = drag.panX + (ev.clientX - drag.x);
            panY = drag.panY + (ev.clientY - drag.y);
            paint();
            return;
        }
        const pos = pointerPos(ev);
        const dx = pos.x - drag.x;
        const dy = pos.y - drag.y;
        if (drag.type === 'move') {
            crop = clamp({ ...drag.crop, x: drag.crop.x + dx, y: drag.crop.y + dy });
        } else {
            const next = { ...drag.crop };
            const h = drag.handle;
            if (h.includes('w')) { next.x += dx; next.w -= dx; }
            if (h.includes('e')) next.w += dx;
            if (h.includes('n')) { next.y += dy; next.h -= dy; }
            if (h.includes('s')) next.h += dy;
            crop = clamp(next);
        }
        paint();
    }

    function onUp(ev) {
        pointers.delete(ev.pointerId);
        if (pointers.size < 2) pinch = null;
        if (pointers.size === 0) drag = null;
    }

    function close(file) {
        $('cropModal').hidden = true;
        document.body.classList.remove('crop-open');
        const finish = done;
        done = null;
        img = null;
        if (finish) finish(file || null);
    }

    function bindOnce() {
        const stage = $('cropStage');
        if (!stage || stage.dataset.bound) return;
        stage.dataset.bound = '1';
        stage.addEventListener('pointerdown', onDown);
        stage.addEventListener('pointermove', onMove);
        stage.addEventListener('pointerup', onUp);
        stage.addEventListener('pointercancel', onUp);
        stage.addEventListener('wheel', (ev) => {
            ev.preventDefault();
            zoom = Math.min(4, Math.max(1, zoom * (ev.deltaY < 0 ? 1.08 : 0.92)));
            $('cropZoom').value = String(zoom);
            paint();
        }, { passive: false });
        $('cropRot').addEventListener('click', () => {
            quarter = (quarter + 1) % 4;
            panX = 0;
            panY = 0;
            const st = stageBox();
            crop = clamp({ x: st.w * 0.08, y: st.h * 0.08, w: st.w * 0.84, h: st.h * 0.84 });
            paint();
        });
        $('cropStraight').addEventListener('input', () => {
            straight = parseFloat($('cropStraight').value) || 0;
            paint();
        });
        $('cropZoom').addEventListener('input', () => {
            zoom = parseFloat($('cropZoom').value) || 1;
            paint();
        });
        $('cropReset').addEventListener('click', resetView);
        $('cropCancel').addEventListener('click', () => close(null));
        $('cropOk').addEventListener('click', async () => {
            const file = await exportJpeg();
            close(file);
        });
        window.addEventListener('resize', () => {
            if (!$('cropModal').hidden) paint();
        });
    }

    window.openCropper = function (file) {
        bindOnce();
        return new Promise((resolve, reject) => {
            const url = URL.createObjectURL(file);
            const image = new Image();
            image.onload = () => {
                URL.revokeObjectURL(url);
                img = image;
                done = resolve;
                $('cropModal').hidden = false;
                document.body.classList.add('crop-open');
                requestAnimationFrame(() => resetView());
            };
            image.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error('decode'));
            };
            image.src = url;
        });
    };
})();
