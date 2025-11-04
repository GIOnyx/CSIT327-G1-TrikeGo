/* Service Worker for TrikeGo push notifications
   - Listens for 'push' events and displays notifications
   - Handles notification click to open appropriate URL
*/

self.addEventListener('push', function (event) {
    let payload = {};
    try {
        if (event.data) payload = event.data.json();
    } catch (e) {
        try {
            payload = { body: event.data.text() };
        } catch (e2) {
            payload = {};
        }
    }

    const title = payload.title || 'TrikeGo';
    const options = {
        body: payload.body || '',
        icon: payload.icon || '/static/user/images/trike_icon.png',
        badge: payload.badge || '/static/user/images/trike_badge.png',
        data: payload.data || {},
        tag: payload.tag || undefined,
        renotify: payload.renotify || false
    };

    event.waitUntil(self.registration.showNotification(title, options));
    // Also notify any open pages (so in-focus clients can react without showing notification UI)
    try {
        const payloadForClients = options || {};
        event.waitUntil(
            clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
                clientList.forEach(function(client) {
                    try {
                        client.postMessage(payloadForClients);
                    } catch (e) {
                        // Ignore postMessage failures
                    }
                });
            })
        );
    } catch (e) {
        // ignore
    }
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    const data = event.notification.data || {};
    let url = '/';
    if (data && data.booking_id) {
        url = `/booking/${data.booking_id}/`;
    } else if (data && data.url) {
        url = data.url;
    }

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (clientList) {
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if (client.url === url && 'focus' in client) return client.focus();
            }
            if (clients.openWindow) return clients.openWindow(url);
        })
    );
});

self.addEventListener('pushsubscriptionchange', function (event) {
    // Best effort re-subscribe — application code should handle server-side updates
    event.waitUntil((async function () {
        try {
            const reg = await self.registration;
            // Try to fetch the current VAPID public key from the server
            let applicationServerKey = null;
            try {
                const resp = await fetch('/notifications/public_key/', { credentials: 'same-origin' });
                if (resp && resp.ok) {
                    const data = await resp.json();
                    if (data && data.public_key) {
                        // convert base64 to Uint8Array
                        const base64String = data.public_key;
                        const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
                        const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
                        const rawData = atob(base64);
                        const outputArray = new Uint8Array(rawData.length);
                        for (let i = 0; i < rawData.length; ++i) {
                            outputArray[i] = rawData.charCodeAt(i);
                        }
                        applicationServerKey = outputArray;
                    }
                }
            } catch (e) {
                // ignore, proceed without applicationServerKey
            }

            const subscribeOptions = { userVisibleOnly: true };
            if (applicationServerKey) subscribeOptions.applicationServerKey = applicationServerKey;

            const sub = await reg.pushManager.subscribe(subscribeOptions);
            // Notify server about new subscription
            try {
                const p256dh = sub.getKey ? btoa(String.fromCharCode.apply(null, new Uint8Array(sub.getKey('p256dh')))) : null;
                const auth = sub.getKey ? btoa(String.fromCharCode.apply(null, new Uint8Array(sub.getKey('auth')))) : null;
                const body = JSON.stringify({ endpoint: sub.endpoint, keys: { p256dh: p256dh, auth: auth }, user_agent: 'service-worker', topics: ['general'] });
                await fetch('/notifications/sw_subscribe/', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: body });
            } catch (e) {
                // ignore server notification failure
            }
        } catch (e) {
            // ignore
        }
    })());
});
