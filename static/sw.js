/* Cache static files. API calls stay network-first and are never stored. */
const CACHE = 'ued-static-v2';
const PRECACHE = [
    '/',
    '/offline.html',
    '/manifest.webmanifest',
    '/static/style.css',
    '/static/script.js',
    '/static/boards.js',
    '/static/academics-ui.js',
    '/static/studio.js',
    '/static/advise.js',
    '/static/crop.js',
    '/static/vendor/chart.umd.min.js',
    '/static/vendor/qrcode.js',
    '/static/ued-logo.png',
    '/static/favicon.ico',
    '/static/favicon-32.png',
    '/static/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
    event.waitUntil(caches.keys().then((keys) => Promise.all(
        keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))
    )).then(() => self.clients.claim()));
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
        if (list.length) return list[0].focus();
        return self.clients.openWindow('/');
    }));
});

let reminderItems = [];
let reminderTimer = null;

function armReminders() {
    if (reminderTimer) clearTimeout(reminderTimer);
    const now = Date.now();
    let next = null;
    reminderItems.forEach((item) => {
        const due = item.at - item.lead;
        if (due <= now && now - due < 120000 && !item.fired) {
            item.fired = true;
            self.registration.showNotification(item.title, {
                body: item.body,
                icon: '/static/ued-logo.png',
            });
        } else if (due > now && (next === null || due < next)) {
            next = due;
        }
    });
    if (next !== null) {
        reminderTimer = setTimeout(armReminders, Math.max(1000, Math.min(next - now, 30 * 60 * 1000)));
    }
}

self.addEventListener('message', (event) => {
    if (!event.data || event.data.type !== 'reminders') return;
    reminderItems = event.data.items || [];
    armReminders();
});

self.addEventListener('fetch', (event) => {
    const request = event.request;
    if (request.method !== 'GET') return;
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(fetch(request).catch(() => new Response(
            JSON.stringify({ success: false, error: 'Không có mạng' }),
            { status: 503, headers: { 'Content-Type': 'application/json' } }
        )));
        return;
    }
    if (request.mode === 'navigate') {
        event.respondWith(fetch(request).catch(() => caches.match('/offline.html')));
        return;
    }
    event.respondWith(
        caches.match(request).then((cached) => cached || fetch(request).then((response) => {
            if (response && response.ok && url.pathname.startsWith('/static/')) {
                const copy = response.clone();
                caches.open(CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
        }).catch(() => caches.match('/offline.html')))
    );
});
