self.addEventListener('push', (event) => {
    let data = {title: 'Procurement Update', body: 'You have a new notification.'};
    try {
        data = event.data.json();
    } catch (e) {
        // ignore malformed payloads
    }
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/static/images/icon.png',
        })
    );
});

self.addEventListener('fetch', (event) => {
    event.respondWith(
        fetch(event.request).catch(() => caches.match('/static/offline.html'))
    );
});
