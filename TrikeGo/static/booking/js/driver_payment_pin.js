/**
 * Driver Payment PIN Verification
 * Handles PIN generation and status polling for drivers
 */

class DriverPaymentPIN {
    constructor(bookingId, fare) {
    this.bookingId = bookingId;
    this.fare = fare;
    this.pollInterval = null;
    this.countdownInterval = null;
    this.expiresAt = null;

    this.init();
    }
    
    init() {
        // Check if PIN already exists
        this.checkInitialStatus();
    }
    
    async checkInitialStatus() {
        try {
            const response = await fetch(`/booking/api/${this.bookingId}/payment/pin-status/`);
            const data = await response.json();
            
            if (data.payment_verified) {
                this.showVerified();
            } else if (data.pin_exists && data.pin_valid) {
                // PIN already generated, poll for verification
                this.startPolling();
            }
        } catch (error) {
            console.error('Error checking initial PIN status:', error);
        }
    }
    
    async generatePIN() {
        try {
            const response = await fetch(`/booking/api/${this.bookingId}/payment/generate-pin/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.displayPIN(data.pin, data.expires_at);
                this.startPolling();
            } else {
                alert(data.message || 'Failed to generate PIN');
            }
        } catch (error) {
            console.error('Error generating PIN:', error);
            alert('Network error. Please try again.');
        }
    }
    
    displayPIN(pin, expiresAt) {
        // Hide generate button, show PIN
        const genContainer = document.getElementById(`pin-gen-${this.bookingId}`);
        const displayContainer = document.getElementById(`pin-display-${this.bookingId}`);
        const pinValue = document.getElementById(`pin-value-${this.bookingId}`);
        
        if (genContainer) genContainer.style.display = 'none';
        if (displayContainer) {
            displayContainer.style.display = 'block';
            if (pinValue) pinValue.textContent = pin;
        }
        
        this.expiresAt = new Date(expiresAt);
        this.startCountdown();
        this.showBanner('Share this PIN with the rider to confirm payment.', 'info');
    }
    
    startCountdown() {
        const countdownEl = document.getElementById(`countdown-${this.bookingId}`);
        if (!countdownEl) return;
        
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
        }

        this.countdownInterval = setInterval(() => {
            const now = new Date();
            const diff = Math.max(0, this.expiresAt - now);
            
            const minutes = Math.floor(diff / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);
            
            countdownEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            
            if (diff === 0) {
                this.handlePinExpired();
            }
        }, 1000);
    }
    
    startPolling() {
        // Keep for backward compatibility; prefer push-based updates
        if (navigator.serviceWorker && navigator.serviceWorker.controller) {
            // Rely on push messages; perform an initial check
            this.checkPaymentStatus();
            return;
        }
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
        }
        this.pollInterval = setInterval(() => this.checkPaymentStatus(), 2000);
    }
    
    async checkPaymentStatus() {
        try {
            const response = await fetch(`/booking/api/${this.bookingId}/payment/pin-status/`);
            const data = await response.json();
            
            if (data.payment_verified) {
                this.onPaymentVerified();
            }
        } catch (error) {
            console.error('Error checking status:', error);
        }
    }
    
    onPaymentVerified() {
        this.showVerified();
        try {
            if (typeof window.fetchItineraryData === 'function') {
                window.fetchItineraryData();
            }
        } catch (refreshErr) {
            console.warn('Failed to refresh itinerary after payment verification', refreshErr);
        }

        document.dispatchEvent(new CustomEvent('driver:paymentVerified', {
            detail: { bookingId: this.bookingId }
        }));
    }
    
    showVerified() {
        this.clearTimers();

        const genContainer = document.getElementById(`pin-gen-${this.bookingId}`);
        const displayContainer = document.getElementById(`pin-display-${this.bookingId}`);
        const section = document.getElementById(`payment-section-${this.bookingId}`);

        if (genContainer) {
            genContainer.style.display = 'none';
        }
        if (displayContainer) {
            displayContainer.style.display = 'none';
        }

        if (section) {
            let verified = section.querySelector('.payment-verified-container');
            if (!verified) {
                verified = document.createElement('div');
                verified.className = 'payment-verified-container';
                verified.innerHTML = '<div class="alert-success"><h4>Payment Verified!</h4><p>Trip completed successfully.</p></div>';
                section.appendChild(verified);
            }
            verified.style.display = 'block';
        }

        this.showBanner('Payment verified! Trip completed successfully.', 'success');
        this.expiresAt = null;
    }
    
    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    clearTimers() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
    }

    handlePinExpired() {
        this.clearTimers();
        this.showBanner('PIN expired. Generate a new one to verify payment.', 'warning');
        const displayContainer = document.getElementById(`pin-display-${this.bookingId}`);
        const genContainer = document.getElementById(`pin-gen-${this.bookingId}`);
        const section = document.getElementById(`payment-section-${this.bookingId}`);
        if (displayContainer) {
            displayContainer.style.display = 'none';
        }
        if (genContainer) {
            genContainer.style.display = 'block';
            const triggerBtn = genContainer.querySelector('.generate-pin-btn, .btn');
            if (triggerBtn) {
                triggerBtn.disabled = false;
                triggerBtn.textContent = '🔑 Generate Payment PIN';
            }
        }
        if (section) {
            const verified = section.querySelector('.payment-verified-container');
            if (verified) {
                verified.style.display = 'none';
            }
        }
        this.expiresAt = null;
    }

    showBanner(message, variant = 'info') {
        const section = document.getElementById(`payment-section-${this.bookingId}`);
        if (!section) return;

        const bannerId = `pin-banner-${this.bookingId}`;
        let banner = document.getElementById(bannerId);
        if (!banner) {
            banner = document.createElement('div');
            banner.id = bannerId;
            banner.className = 'pin-banner';
            section.insertBefore(banner, section.firstChild);
        }

        const palette = {
            success: { bg: '#d4edda', text: '#155724' },
            warning: { bg: '#fff3cd', text: '#856404' },
            error: { bg: '#f8d7da', text: '#721c24' },
            info: { bg: '#d1ecf1', text: '#0c5460' }
        };

        const colors = palette[variant] || palette.info;
        banner.style.backgroundColor = colors.bg;
        banner.style.color = colors.text;
        banner.style.padding = '10px 14px';
        banner.style.marginBottom = '12px';
        banner.style.borderRadius = '8px';
        banner.style.fontWeight = '500';
        banner.textContent = message;
    }
}

// Initialize for all bookings with payment sections
document.addEventListener('DOMContentLoaded', function() {
    const paymentSections = document.querySelectorAll('.payment-pin-section');
    const pinInstances = new Map();
    
    paymentSections.forEach(section => {
        const bookingId = section.dataset.bookingId;
        const fare = section.dataset.fare;
        
        // Create instance
        const instance = new DriverPaymentPIN(bookingId, fare);
        pinInstances.set(bookingId, instance);
        
        // Attach event listeners for generate button
        const generateBtn = section.querySelector('.generate-pin-btn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => {
                instance.generatePIN();
            });
        }
        
        // Attach event listener for regenerate button
        const regenerateBtn = section.querySelector('.regenerate-pin-btn');
        if (regenerateBtn) {
            regenerateBtn.addEventListener('click', () => {
                if (confirm('Generate a new PIN? The current PIN will be invalidated.')) {
                    instance.generatePIN();
                }
            });
        }
    });
    // Register instances globally for SW message dispatch
    window.__driverPaymentPinInstances = window.__driverPaymentPinInstances || new Map();
    paymentSections.forEach(section => {
        const bookingId = section.dataset.bookingId;
        if (bookingId && pinInstances.has(bookingId)) {
            window.__driverPaymentPinInstances.set(String(bookingId), pinInstances.get(bookingId));
        }
    });
});

// Global SW listener to handle payment verified events
if (navigator.serviceWorker && navigator.serviceWorker.addEventListener) {
    try {
        navigator.serviceWorker.addEventListener('message', function (evt) {
            try {
                const payload = evt.data || {};
                const data = (payload && payload.data) ? payload.data : payload;
                const type = data && data.type;
                const bookingId = data && data.booking_id;
                if (!bookingId || !type) return;
                const inst = window.__driverPaymentPinInstances && window.__driverPaymentPinInstances.get(String(bookingId));
                if (!inst) return;
                if (type === 'payment_verified') {
                    inst.onPaymentVerified && inst.onPaymentVerified();
                }
            } catch (e) { /* ignore */ }
        });
    } catch (e) { /* ignore */ }
}
