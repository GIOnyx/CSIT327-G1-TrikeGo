(function () {
    const HIDE_CLASS = 'is-hidden';
    const driverControllers = new Map();
    const riderControllers = new Map();

    function hide(element) {
        if (element) {
            element.classList.add(HIDE_CLASS);
        }
    }

    function show(element) {
        if (element) {
            element.classList.remove(HIDE_CLASS);
        }
    }

    function setText(element, value) {
        if (element) {
            element.textContent = value;
        }
    }

    function getCsrfToken() {
        const csrfInput = document.querySelector('[name="csrfmiddlewaretoken"]');
        if (csrfInput) {
            return csrfInput.value;
        }
        const cookieMatch = document.cookie.match(/csrftoken=([^;]+)/);
        return cookieMatch ? cookieMatch[1] : '';
    }

    class DriverPaymentPIN {
        constructor(bookingId, fare) {
            this.bookingId = bookingId;
            this.fare = fare;
            this.pollTimer = null;
            this.countdownTimer = null;
            this.expiresAt = null;

            this.section = document.getElementById('payment-pin-section');
            this.generateContainer = document.getElementById('generate-pin-container');
            this.displayContainer = document.getElementById('pin-display-container');
            this.verifiedContainer = document.getElementById('payment-verified-container');
            this.fareAmount = document.getElementById('driver-fare-amount');
            this.pinValue = document.getElementById('pin-value');
            this.countdownValue = document.getElementById('pin-countdown');
            this.generateButton = document.getElementById('generate-pin-btn');
            this.regenerateButton = document.getElementById('regenerate-pin-btn');

            this.bindEvents();
        }

        bindEvents() {
            if (this.generateButton) {
                this.generateButton.addEventListener('click', () => this.generatePin());
            }

            if (this.regenerateButton) {
                this.regenerateButton.addEventListener('click', () => {
                    const confirmed = window.confirm('Generate a new PIN? The current PIN will be invalidated.');
                    if (confirmed) {
                        this.generatePin();
                    }
                });
            }
        }

        async generatePin() {
            try {
                const response = await fetch(`/booking/api/${this.bookingId}/payment/generate-pin/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    }
                });

                const payload = await response.json();
                if (!response.ok) {
                    window.alert(payload.message || 'Failed to generate PIN.');
                    return;
                }

                this.handlePinGenerated(payload.pin, payload.expires_at);
            } catch (error) {
                console.error('Error generating payment PIN:', error);
                window.alert('Network error. Please try again.');
            }
        }

        handlePinGenerated(pin, expiresAt) {
            setText(this.fareAmount, Number(this.fare).toFixed(2));
            setText(this.pinValue, pin);
            this.expiresAt = new Date(expiresAt);

            hide(this.generateContainer);
            show(this.displayContainer);
            hide(this.verifiedContainer);

            this.startCountdown();
            this.startPolling();
        }

        startCountdown() {
            if (!this.countdownValue || !this.expiresAt) {
                return;
            }

            window.clearInterval(this.countdownTimer);
            this.countdownTimer = window.setInterval(() => {
                const remaining = Math.max(0, this.expiresAt - Date.now());
                const minutes = Math.floor(remaining / 60000);
                const seconds = Math.floor((remaining % 60000) / 1000);
                setText(this.countdownValue, `${minutes}:${seconds.toString().padStart(2, '0')}`);

                if (remaining === 0) {
                    window.clearInterval(this.countdownTimer);
                    window.alert('PIN expired. Please generate a new one.');
                    hide(this.displayContainer);
                    show(this.generateContainer);
                }
            }, 1000);
        }

        startPolling() {
            window.clearInterval(this.pollTimer);
            this.pollTimer = window.setInterval(() => this.checkStatus(), 2000);
        }

        async checkStatus() {
            try {
                const response = await fetch(`/booking/api/${this.bookingId}/payment/pin-status/`);
                const payload = await response.json();

                if (payload.payment_verified) {
                    this.handlePaymentVerified();
                }
            } catch (error) {
                console.error('Error checking payment status:', error);
            }
        }

        handlePaymentVerified() {
            window.clearInterval(this.pollTimer);
            window.clearInterval(this.countdownTimer);

            hide(this.generateContainer);
            hide(this.displayContainer);
            show(this.verifiedContainer);

            window.setTimeout(() => window.location.reload(), 2000);
        }
    }

    class RiderPaymentPIN {
        constructor(bookingId, fare) {
            this.bookingId = bookingId;
            this.fare = fare;
            this.pollTimer = null;

            this.section = document.getElementById('payment-verification-section');
            this.waitingContainer = document.getElementById('waiting-for-pin-container');
            this.entryContainer = document.getElementById('pin-entry-container');
            this.verifiedContainer = document.getElementById('rider-payment-verified-container');
            this.fareLabelPrimary = document.getElementById('rider-fare-amount');
            this.fareLabelSecondary = document.getElementById('rider-fare-amount-2');
            this.pinInput = document.getElementById('pin-input');
            this.verifyButton = document.getElementById('verify-pin-btn');
            this.errorContainer = document.getElementById('pin-error');
            this.attemptsLabel = document.getElementById('attempts-remaining');

            this.bindEvents();
        }

        bindEvents() {
            if (this.verifyButton) {
                this.verifyButton.addEventListener('click', () => this.verifyPin());
            }

            if (this.pinInput) {
                this.pinInput.addEventListener('keypress', (event) => {
                    if (event.key === 'Enter') {
                        event.preventDefault();
                        this.verifyPin();
                    }
                });
            }
        }

        startPolling() {
            window.clearInterval(this.pollTimer);
            this.pollTimer = window.setInterval(() => this.checkStatus(), 2000);
        }

        async checkStatus() {
            try {
                const response = await fetch(`/booking/api/${this.bookingId}/payment/pin-status/`);
                const payload = await response.json();

                if (payload.payment_verified) {
                    this.handlePaymentVerified();
                    return;
                }

                if (payload.pin_exists && payload.pin_valid) {
                    this.showEntry(payload.attempts_remaining);
                }
            } catch (error) {
                console.error('Error checking rider PIN status:', error);
            }
        }

        showEntry(attemptsRemaining) {
            hide(this.waitingContainer);
            hide(this.verifiedContainer);
            show(this.entryContainer);

            setText(this.fareLabelPrimary, Number(this.fare).toFixed(2));
            setText(this.fareLabelSecondary, Number(this.fare).toFixed(2));
            setText(this.attemptsLabel, attemptsRemaining ?? 3);

            if (this.pinInput) {
                this.pinInput.focus();
            }
        }

        async verifyPin() {
            if (!this.pinInput) {
                return;
            }

            const pin = this.pinInput.value.trim();
            if (!/^\d{4}$/.test(pin)) {
                this.showError('Please enter a 4-digit PIN');
                return;
            }

            try {
                if (this.verifyButton && window.singleClickHelper && typeof window.singleClickHelper.setLoading === 'function') {
                    try { window.singleClickHelper.setLoading(this.verifyButton); } catch (err) {}
                    try { this.verifyButton.dataset.processing = 'true'; } catch (err) {}
                } else {
                    this.verifyButton?.setAttribute('disabled', 'disabled');
                }
            } catch (e) { this.verifyButton?.setAttribute('disabled', 'disabled'); }
            hide(this.errorContainer);

            try {
                const response = await fetch(`/booking/api/${this.bookingId}/payment/verify-pin/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ pin })
                });

                const payload = await response.json();
                if (!response.ok) {
                    this.showError(payload.message || 'Unable to verify PIN');
                    setText(this.attemptsLabel, payload.attempts_remaining ?? 0);
                    this.pinInput.value = '';
                    this.pinInput.focus();
                    return;
                }

                this.handlePaymentVerified();
            } catch (error) {
                console.error('Error verifying rider PIN:', error);
                this.showError('Network error. Please try again.');
                try { if (this.verifyButton && window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') { window.singleClickHelper.clearLoading(this.verifyButton); this.verifyButton.dataset.processing = 'false'; } } catch (err) {}
            } finally {
                try { if (!(this.verifyButton && window.singleClickHelper && typeof window.singleClickHelper.setLoading === 'function')) { this.verifyButton?.removeAttribute('disabled'); } } catch (err) { this.verifyButton?.removeAttribute('disabled'); }
            }
        }

        showError(message) {
            if (!this.errorContainer) {
                return;
            }
            this.errorContainer.textContent = message;
            show(this.errorContainer);

            window.setTimeout(() => hide(this.errorContainer), 5000);
        }

        handlePaymentVerified() {
            window.clearInterval(this.pollTimer);
            hide(this.waitingContainer);
            hide(this.entryContainer);
            show(this.verifiedContainer);
            window.setTimeout(() => window.location.reload(), 2000);
        }
    }

    function showPaymentPINSection(bookingId, fare) {
        const key = String(bookingId);
        let instance = driverControllers.get(key);
        if (!instance) {
            instance = new DriverPaymentPIN(bookingId, fare);
            driverControllers.set(key, instance);
        }

        setText(instance.fareAmount, Number(fare).toFixed(2));
        show(instance.section);
        show(instance.generateContainer);
        hide(instance.displayContainer);
        hide(instance.verifiedContainer);
    }

    function showPaymentVerificationSection(bookingId, fare) {
        const key = String(bookingId);
        let instance = riderControllers.get(key);
        if (!instance) {
            instance = new RiderPaymentPIN(bookingId, fare);
            riderControllers.set(key, instance);
        }

        setText(instance.fareLabelPrimary, Number(fare).toFixed(2));
        setText(instance.fareLabelSecondary, Number(fare).toFixed(2));
        show(instance.section);
        show(instance.waitingContainer);
        hide(instance.entryContainer);
        hide(instance.verifiedContainer);
        instance.startPolling();
    }

    window.showPaymentPINSection = showPaymentPINSection;
    window.showPaymentVerificationSection = showPaymentVerificationSection;

    document.addEventListener('DOMContentLoaded', () => {
        const configEl = document.getElementById('payment-pin-demo-config');
        if (!configEl) {
            return;
        }

        const driverBookingId = configEl.dataset.driverBookingId;
        const driverFare = configEl.dataset.driverFare;
        const riderBookingId = configEl.dataset.riderBookingId;
        const riderFare = configEl.dataset.riderFare;
        const demoMode = configEl.dataset.demoMode === 'true';

        if (!demoMode) {
            return;
        }

        if (driverBookingId && driverFare) {
            show(document.getElementById('payment-pin-section'));
            hide(document.getElementById('pin-display-container'));
            hide(document.getElementById('payment-verified-container'));
            setText(document.getElementById('driver-fare-amount'), Number(driverFare).toFixed(2));
        }

        if (riderBookingId && riderFare) {
            show(document.getElementById('payment-verification-section'));
            hide(document.getElementById('pin-entry-container'));
            hide(document.getElementById('rider-payment-verified-container'));
            setText(document.getElementById('rider-fare-amount'), Number(riderFare).toFixed(2));
            setText(document.getElementById('rider-fare-amount-2'), Number(riderFare).toFixed(2));
        }
    });
})();
