// Booking detail page JS moved from inline template
(function() {
    const cfg = window.BOOKING_DETAIL_CONFIG || {};
    const bookingId = cfg.bookingId;
    const userId = cfg.userId || null;
    const csrfToken = cfg.csrfToken || '';

    document.addEventListener('DOMContentLoaded', function() {
        // Cancel button handler - perform POST to cancel endpoint if present
        const cancelBtn = document.getElementById('cancelBtn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', function() {
                if (!confirm('Are you sure you want to cancel this ride?')) return;
                const url = (window.BOOKING_DETAIL_CONFIG && window.BOOKING_DETAIL_CONFIG.cancelUrl) ? window.BOOKING_DETAIL_CONFIG.cancelUrl : null;
                if (!url) {
                    alert('Cancel URL not available');
                    return;
                }
                fetch(url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' }
                })
                .then(r => r.json())
                .then(data => {
                    const messageDiv = document.getElementById('message');
                    messageDiv.textContent = data.message || 'Cancelled';
                    messageDiv.style.display = 'block';
                    if (data.status === 'success') {
                        messageDiv.className = 'msg-success';
                        cancelBtn.textContent = 'Cancelled';
                        cancelBtn.disabled = true;
                        cancelBtn.classList.add('btn-disabled');
                        setTimeout(() => window.location.reload(), 1200);
                    } else {
                        messageDiv.className = 'msg-error';
                    }
                })
                .catch(err => {
                    console.error('Cancel error', err);
                    const messageDiv = document.getElementById('message');
                    messageDiv.textContent = 'An unexpected error occurred.';
                    messageDiv.className = 'msg-error';
                    messageDiv.style.display = 'block';
                });
            });
        }
    });

    // Chat polling logic
    (function() {
        if (!bookingId) return;
        const messagesEl = document.getElementById('chatMessages');
        const chatForm = document.getElementById('chatForm');
        const chatInput = document.getElementById('chatInput');

        if (!messagesEl || !chatForm) return;

        const apiGet = `/chat/api/booking/${bookingId}/messages/`;
        const apiPost = `/chat/api/booking/${bookingId}/messages/send/`;

        function escapeHtml(str) {
            return String(str).replace(/[&<>"']/g, function (s) {
                return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[s];
            });
        }

        function formatMessage(m) {
            const own = (m.sender_id == userId);
            const cls = own ? 'chat-msg-own' : 'chat-msg-other';
            return `<div class="${cls}" style="margin-bottom:6px;"><small style="color:#666">${m.sender_username} • ${new Date(m.timestamp).toLocaleString()}</small><div>${escapeHtml(m.message)}</div></div>`;
        }

        function loadMessages() {
            fetch(apiGet, { credentials: 'same-origin' })
                .then(r => { if (!r.ok) throw r; return r.json(); })
                .then(data => {
                    messagesEl.innerHTML = '';
                    if (!data.messages || data.messages.length === 0) {
                        messagesEl.innerHTML = '<p class="muted">No messages yet.</p>';
                        return;
                    }
                    data.messages.forEach(m => messagesEl.insertAdjacentHTML('beforeend', formatMessage(m)));
                    messagesEl.scrollTop = messagesEl.scrollHeight;
                })
                .catch(err => { console.error('Failed to load messages', err); messagesEl.innerHTML = '<p class="muted">Unable to load messages.</p>'; });
        }

    // Initial load & polling (reduced frequency to lower server load)
    loadMessages();
    // If a service worker is controlling the page, rely on push messages. Otherwise fallback to polling.
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        console.log('Using push messages for chat updates');
    } else {
        setInterval(loadMessages, 6000);
    }

    // Listen for push messages forwarded by the service worker and refresh chat when appropriate
    if (navigator.serviceWorker && navigator.serviceWorker.addEventListener) {
        try {
            navigator.serviceWorker.addEventListener('message', function (evt) {
                try {
                    const payload = evt.data || {};
                    const data = (payload && payload.data) ? payload.data : payload;
                    if (!data) return;
                    if (data.type === 'chat_message' && String(data.booking_id) === String(bookingId)) {
                        loadMessages();
                    }
                } catch (e) { /* ignore */ }
            });
        } catch (e) { /* ignore */ }
    }

        chatForm.addEventListener('submit', function(ev) {
            ev.preventDefault();
            const text = (chatInput.value || '').trim();
            if (!text) return;
            fetch(apiPost, {
                method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ message: text })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) { alert(data.error); return; }
                messagesEl.insertAdjacentHTML('beforeend', formatMessage(data));
                messagesEl.scrollTop = messagesEl.scrollHeight;
                chatInput.value = '';
            })
            .catch(err => { console.error('Send failed', err); alert('Failed to send message.'); });
        });
    })();
})();
