(function () {
    const modal = document.getElementById('rider-payment-pin-modal');
    if (!modal) {
        return;
    }

    const modalFare = document.getElementById('rider-modal-fare');
    const pinInput = document.getElementById('rider-pin-input');
    const verifyBtn = document.getElementById('rider-verify-pin-btn');
    const closeBtn = document.getElementById('rider-modal-close-btn');
    const errorMsg = document.getElementById('rider-pin-error');
    const attemptsCount = document.getElementById('attempts-count');
    const waitingSection = document.getElementById('rider-pin-waiting-section');
    const entrySection = document.getElementById('rider-pin-entry-section');
    const successSection = document.getElementById('rider-pin-success-section');

    const config = window.RIDER_DASH_CONFIG || {};
    const pending = Array.isArray(config.pendingPaymentBookings) ? config.pendingPaymentBookings : [];

    let currentBookingId = null;
    let pollingInterval = null;
    let _swMessageHandler = null;

    function formatFare(amount) {
        const parsed = Number.parseFloat(amount);
        return Number.isFinite(parsed) ? parsed.toFixed(2) : '0.00';
    }

    function setAttemptsRemaining(value) {
        attemptsCount.textContent = Number.isFinite(value) ? value : 3;
    }

    async function fetchPinStatus(bookingId) {
        try {
            const response = await fetch(`/booking/api/${bookingId}/payment/pin-status/`);
            if (!response.ok) {
                throw new Error(`Failed status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching PIN status:', error);
            return null;
        }
    }

    function resetState() {
        errorMsg.style.display = 'none';
        errorMsg.textContent = '';
        pinInput.value = '';
        pinInput.style.borderColor = '#ddd';
        waitingSection.style.display = 'none';
        entrySection.style.display = 'block';
        successSection.style.display = 'none';
        setAttemptsRemaining(3);
    }

    async function populateInitialStatus(bookingId) {
        const status = await fetchPinStatus(bookingId);
        if (!status) {
            return;
        }

        setAttemptsRemaining(status.attempts_remaining);

        if (!status.pin_exists) {
            console.warn('No PIN exists for this booking yet!');
        }
        if (status.pin_expired) {
            console.warn('PIN has expired!');
        }
        if (status.payment_verified) {
            showSuccess();
        }
    }

    function showModal(bookingId, fare) {
        currentBookingId = bookingId;
        modalFare.textContent = `₱${formatFare(fare)}`;

        resetState();
        void populateInitialStatus(bookingId);

        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
        // Avoid focus issues on older browsers
        setTimeout(() => pinInput.focus(), 100);
    }

    function hideModal() {
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
        currentBookingId = null;
    }

    function showError(message) {
        errorMsg.textContent = message;
        errorMsg.style.display = 'block';
        pinInput.style.borderColor = '#dc3545';
    }

    function showSuccess() {
        entrySection.style.display = 'none';
        successSection.style.display = 'block';
        setTimeout(() => {
            hideModal();
            window.location.reload();
        }, 3000);
    }

    async function verifyPIN() {
        if (!currentBookingId) {
            return;
        }

        const rawPin = pinInput.value.trim();
        if (rawPin.length !== 4 || /\D/.test(rawPin)) {
            showError('Please enter a 4-digit PIN');
            return;
        }

        try {
            if (window.singleClickHelper && typeof window.singleClickHelper.setLoading === 'function') {
                window.singleClickHelper.setLoading(verifyBtn);
            } else {
                verifyBtn.disabled = true;
            }
        } catch (e) { verifyBtn.disabled = true; }
        errorMsg.style.display = 'none';

        try {
            const response = await fetch(`/booking/api/${currentBookingId}/payment/verify-pin/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': config.csrfToken || ''
                },
                body: JSON.stringify({ pin: rawPin })
            });

            const data = await response.json();

            if (response.ok && data.status === 'success') {
                showSuccess();
                try { verifyBtn.dispatchEvent(new CustomEvent('single-click-success', { bubbles: true })); } catch (e) {}
                try { if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') { window.singleClickHelper.clearLoading(verifyBtn); verifyBtn.dataset.processing = 'false'; } } catch (e) {}
            } else {
                showError(data.message || 'Invalid PIN');
                setAttemptsRemaining(data.attempts_remaining);
                pinInput.value = '';
                pinInput.focus();
                try { verifyBtn.dispatchEvent(new CustomEvent('single-click-error', { bubbles: true })); } catch (e) {}
                try { if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') { window.singleClickHelper.clearLoading(verifyBtn); verifyBtn.dataset.processing = 'false'; } } catch (e) {}
            }
        } catch (error) {
            console.error('Error verifying PIN:', error);
            showError('Failed to verify PIN');
            try { verifyBtn.dispatchEvent(new CustomEvent('single-click-error', { bubbles: true })); } catch (e) {}
            try { if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') { window.singleClickHelper.clearLoading(verifyBtn); verifyBtn.dataset.processing = 'false'; } } catch (e) {}
        } finally {
            try {
                if (!(window.singleClickHelper && typeof window.singleClickHelper.setLoading === 'function')) {
                    verifyBtn.disabled = false;
                }
            } catch (e) { verifyBtn.disabled = false; }
        }
    }

    function clearPolling() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
        if (_swMessageHandler && navigator.serviceWorker && navigator.serviceWorker.removeEventListener) {
            try {
                navigator.serviceWorker.removeEventListener('message', _swMessageHandler);
            } catch (e) { /* ignore */ }
            _swMessageHandler = null;
        }
    }

    function startPolling() {
        // If a service worker is active and controlling the page, prefer push messages
        if (navigator.serviceWorker && navigator.serviceWorker.controller) {
            // Register a message handler to receive push messages forwarded by the SW
            if (!_swMessageHandler) {
                _swMessageHandler = function (evt) {
                    try {
                        const payload = evt.data || {};
                        const data = (payload && payload.data) ? payload.data : payload;
                        const type = data && data.type;
                        const booking = data && data.booking_id;
                        if (!booking || booking !== currentBookingId) return;
                        if (type === 'payment_verified') {
                            clearPolling();
                            showSuccess();
                        }
                        if (type === 'payment_pin_generated') {
                            // Ensure entry UI becomes available
                            waitingSection.style.display = 'none';
                            entrySection.style.display = 'block';
                            setAttemptsRemaining(data.attempts_remaining || 3);
                        }
                    } catch (e) { /* ignore */ }
                };
                try { navigator.serviceWorker.addEventListener('message', _swMessageHandler); } catch (e) { /* ignore */ }
            }
            return;
        }

        // Fallback to polling when SW not available
        clearPolling();
        if (!currentBookingId) return;
        pollingInterval = window.setInterval(async () => {
            const status = await fetchPinStatus(currentBookingId);
            if (!status) {
                return;
            }

            if (status.payment_verified) {
                clearPolling();
                showSuccess();
                return;
            }

            if (status.pin_exists && !status.pin_expired) {
                setAttemptsRemaining(status.attempts_remaining);
            }
        }, 2000);
    }

    verifyBtn.addEventListener('click', verifyPIN);
    pinInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            verifyPIN();
        }
    });
    closeBtn.addEventListener('click', () => {
        hideModal();
        clearPolling();
    });

    window.showRiderPaymentPINModal = function (bookingId, fare) {
        showModal(bookingId, fare);
        startPolling();
    };

    if (pending.length) {
        pending.forEach((entry, index) => {
            setTimeout(() => {
                showModal(entry.id, entry.fare);
                startPolling();
            }, 1000 * (index + 1));
        });
    }
})();
