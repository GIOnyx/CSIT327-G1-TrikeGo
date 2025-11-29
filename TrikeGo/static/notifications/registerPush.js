/* Register service worker and subscribe to Web Push
   Expects a global `WEBPUSH_VAPID_PUBLIC_KEY` and `CURRENT_USER_ROLE` to be present
   Sends subscription to POST /notifications/subscribe/ with JSON payload
*/
(function () {
    'use strict';

    function urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
        const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    function arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer || new ArrayBuffer(0));
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary);
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    function roleToTopics(role) {
        if (!role) return ['general'];
        const map = { 'P': 'passenger', 'D': 'driver', 'A': 'admin' };
        return [map[role] || role.toLowerCase()];
    }

    async function sendSubscriptionToServer(subscription, topics, swMode = false) {
        try {
            const p256dh = subscription.getKey ? arrayBufferToBase64(subscription.getKey('p256dh')) : null;
            const auth = subscription.getKey ? arrayBufferToBase64(subscription.getKey('auth')) : null;

            const body = {
                endpoint: subscription.endpoint,
                keys: {
                    p256dh: p256dh,
                    auth: auth
                },
                user_agent: navigator.userAgent,
                topics: topics
            };

            const url = swMode ? '/notifications/sw_subscribe/' : '/notifications/subscribe/';
            const headers = { 'Content-Type': 'application/json' };
            if (!swMode) headers['X-CSRFToken'] = getCookie('csrftoken') || '';

            const resp = await fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: headers,
                body: JSON.stringify(body)
            });

            if (!resp.ok) {
                console.warn('Failed to register push subscription:', resp.statusText || resp.status);
            }
        } catch (err) {
            console.warn('Error sending subscription to server:', err);
        }
    }

    async function fetchPublicKey() {
        try {
            const resp = await fetch('/notifications/public_key/', { credentials: 'same-origin' });
            if (!resp.ok) return null;
            const data = await resp.json();
            return data.public_key || null;
        } catch (e) {
            return null;
        }
    }

    async function registerForPush(role) {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            return;
        }

        try {
            const publicKey = await fetchPublicKey();
            console.debug('Push public key from server:', publicKey);
            const sw = await navigator.serviceWorker.register('/static/notifications/sw.js');
            // Request permission
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') return;

            let subscription = await sw.pushManager.getSubscription();
            const applicationServerKey = publicKey ? urlBase64ToUint8Array(publicKey) : null;

            if (!subscription) {
                subscription = await sw.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: applicationServerKey
                });
                console.debug('New push subscription created:', subscription ? subscription.endpoint : '(no sub)');
            }
            try {
                const p256 = subscription.getKey ? arrayBufferToBase64(subscription.getKey('p256dh')) : null;
                const auth = subscription.getKey ? arrayBufferToBase64(subscription.getKey('auth')) : null;
                console.debug('Subscription details: endpoint=%s, p256dh_len=%s, auth_len=%s', subscription.endpoint, p256 ? p256.length : null, auth ? auth.length : null);
            } catch (e) {
                console.debug('Could not read subscription keys for debug', e);
            }
            const topics = roleToTopics(role);
            await sendSubscriptionToServer(subscription, topics, /*swMode=*/false);
        } catch (err) {
            console.warn('Push registration failed:', err);
        }
    }

    async function unsubscribeFromPush() {
        try {
            if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
            const reg = await navigator.serviceWorker.ready;
            const sub = await reg.pushManager.getSubscription();
            if (!sub) return;
            const endpoint = sub.endpoint;

            // Tell server to remove subscription
            await fetch('/notifications/unsubscribe/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') || '' },
                body: JSON.stringify({ endpoint })
            });

            // Unsubscribe locally
            await sub.unsubscribe();
            console.log('Unsubscribed from push');
        } catch (e) {
            console.warn('Failed to unsubscribe:', e);
        }
    }

    // Expose a simple global initializer
    window.registerForPush = registerForPush;
    window.unsubscribeFromPush = unsubscribeFromPush;

    // Wire up any unsubscribe button on the page
    document.addEventListener('DOMContentLoaded', function () {
        const btn = document.getElementById('push-unsubscribe-btn');
        if (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                if (!confirm('Unsubscribe from push notifications on this device?')) return;
                unsubscribeFromPush();
            });
        }
    });
})();
