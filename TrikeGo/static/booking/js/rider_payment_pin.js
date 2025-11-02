/**
 * Rider Payment PIN Verification
 * Handles PIN entry and verification for riders
 */

class RiderPaymentPIN {
    constructor(bookingId) {
        this.bookingId = bookingId;
        this.pollInterval = null;
        
        this.init();
    }
    
    init() {
        // Start polling to check if PIN is available
        this.startPolling();
        
        // Set up verify button
        const verifyBtn = document.querySelector(`.verify-pin-btn[data-booking-id="${this.bookingId}"]`);
        if (verifyBtn) {
            verifyBtn.addEventListener('click', () => this.verifyPIN());
        }
        
        // Allow Enter key to submit
        const pinInput = document.getElementById(`pin-input-${this.bookingId}`);
        if (pinInput) {
            pinInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.verifyPIN();
                }
            });
            
            // Only allow digits
            pinInput.addEventListener('input', (e) => {
                e.target.value = e.target.value.replace(/[^0-9]/g, '');
            });
        }
    }
    
    startPolling() {
        // Check if driver generated PIN
        this.pollInterval = setInterval(() => this.checkPINAvailable(), 2000);
        // Also check immediately
        this.checkPINAvailable();
    }
    
    async checkPINAvailable() {
        try {
            const response = await fetch(`/booking/api/${this.bookingId}/payment/pin-status/`);
            const data = await response.json();
            
            if (data.payment_verified) {
                this.onPaymentVerified();
            } else if (data.pin_exists && data.pin_valid) {
                this.showPINEntry(data.attempts_remaining);
            }
        } catch (error) {
            console.error('Error checking PIN status:', error);
        }
    }
    
    showPINEntry(attemptsRemaining) {
        clearInterval(this.pollInterval);
        
        const waitingContainer = document.getElementById(`waiting-pin-${this.bookingId}`);
        const entryContainer = document.getElementById(`pin-entry-${this.bookingId}`);
        const attemptsEl = document.getElementById(`attempts-${this.bookingId}`);
        
        if (waitingContainer) waitingContainer.style.display = 'none';
        if (entryContainer) entryContainer.style.display = 'block';
        if (attemptsEl) attemptsEl.textContent = attemptsRemaining;
        
        // Focus input
        const pinInput = document.getElementById(`pin-input-${this.bookingId}`);
        if (pinInput) pinInput.focus();
    }
    
    async verifyPIN() {
        const pinInput = document.getElementById(`pin-input-${this.bookingId}`);
        const pin = pinInput?.value.trim();
        
        // Validate format
        if (!pin || !/^\d{4}$/.test(pin)) {
            this.showError('Please enter a 4-digit PIN');
            return;
        }
        
        try {
            const response = await fetch(`/booking/api/${this.bookingId}/payment/verify-pin/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ pin })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.onPaymentVerified();
            } else {
                this.showError(data.message);
                
                if (data.attempts_remaining !== undefined) {
                    const attemptsEl = document.getElementById(`attempts-${this.bookingId}`);
                    if (attemptsEl) attemptsEl.textContent = data.attempts_remaining;
                }
                
                // Clear input for retry
                if (pinInput) {
                    pinInput.value = '';
                    pinInput.focus();
                }
            }
        } catch (error) {
            console.error('Error verifying PIN:', error);
            this.showError('Network error. Please try again.');
        }
    }
    
    showError(message) {
        const errorEl = document.getElementById(`pin-error-${this.bookingId}`);
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.style.display = 'block';
            
            // Hide after 5 seconds
            setTimeout(() => {
                errorEl.style.display = 'none';
            }, 5000);
        }
    }
    
    onPaymentVerified() {
        clearInterval(this.pollInterval);
        
        alert('✅ Payment verified! Trip completed successfully.');
        
        // Reload page to show updated status
        location.reload();
    }
    
    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
}

// Initialize if on booking detail page as rider
document.addEventListener('DOMContentLoaded', function() {
    if (window.BOOKING_DETAIL_CONFIG) {
        const config = window.BOOKING_DETAIL_CONFIG;
        
        // Only initialize if rider and booking is started and not yet verified
        if (config.isRider && config.bookingStatus === 'started' && !config.paymentVerified) {
            new RiderPaymentPIN(config.bookingId);
        }
    }
});
