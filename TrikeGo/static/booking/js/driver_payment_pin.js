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
    }
    
    startCountdown() {
        const countdownEl = document.getElementById(`countdown-${this.bookingId}`);
        if (!countdownEl) return;
        
        this.countdownInterval = setInterval(() => {
            const now = new Date();
            const diff = Math.max(0, this.expiresAt - now);
            
            const minutes = Math.floor(diff / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);
            
            countdownEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            
            if (diff === 0) {
                clearInterval(this.countdownInterval);
                alert('PIN expired. Please generate a new one.');
                location.reload();
            }
        }, 1000);
    }
    
    startPolling() {
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
        // Stop polling and countdown
        clearInterval(this.pollInterval);
        clearInterval(this.countdownInterval);
        
        // Show success and reload
        alert('✅ Payment verified! Trip completed.');
        location.reload();
    }
    
    showVerified() {
        clearInterval(this.pollInterval);
        clearInterval(this.countdownInterval);
    }
    
    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
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
});
