(function () {
    function getCsrfToken(form) {
        const configToken = window.RIDER_DASH_CONFIG && window.RIDER_DASH_CONFIG.csrfToken;
        if (configToken) {
            return configToken;
        }
        const input = form.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    document.addEventListener('DOMContentLoaded', () => {
        const form = document.getElementById('rating-form');
        const modal = document.getElementById('ratingModal');

        if (!form || !modal) {
            return;
        }

        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const formData = new FormData(form);
            const csrfToken = getCsrfToken(form);

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {}
                });

                const payload = await response.json();
                if (response.ok) {
                    modal.style.display = 'none';
                    modal.setAttribute('aria-hidden', 'true');
                    const successBanner = document.createElement('div');
                    successBanner.className = 'rating-success-banner';
                    successBanner.setAttribute('role', 'status');
                    successBanner.textContent = payload.message || 'Rating submitted successfully.';
                    successBanner.style.cssText = 'position:fixed;top:24px;right:24px;z-index:1200;background:#0b63d6;color:#fff;padding:12px 18px;border-radius:8px;box-shadow:0 6px 18px rgba(0,0,0,0.2);font-weight:600;opacity:1;transition:opacity 0.3s ease;';
                    document.body.appendChild(successBanner);
                    setTimeout(() => {
                        successBanner.style.opacity = '0';
                        setTimeout(() => successBanner.remove(), 350);
                    }, 4000);
                    document.dispatchEvent(new CustomEvent('rider:ratingSubmitted', { detail: payload }));
                } else {
                    alert('Error submitting rating. Please check all fields.');
                    console.error('Rating submission failed:', payload);
                }
            } catch (error) {
                console.error('Network or system error:', error);
                alert('A network error occurred. Please try again.');
            }
        });
    });
})();
