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

        const ratingInputs = form.querySelectorAll('.rating-stars input[type="radio"]');

        function updateStarStates(selectedValue) {
            // Clear all first to avoid stale classes
            const allStars = form.querySelectorAll('.rating-star');
            allStars.forEach(s => s.classList.remove('rating-star--active'));

            ratingInputs.forEach((input) => {
                const star = form.querySelector(`label[for="${input.id}"]`);
                if (!star) return;
                const isActive = Number(input.value) <= Number(selectedValue);
                star.classList.toggle('rating-star--active', isActive);
            });
        }

        function refreshFromChecked() {
            const checked = form.querySelector('.rating-stars input[type="radio"]:checked');
            if (checked) {
                updateStarStates(checked.value);
            } else {
                // Default to the lowest rating (1) so the left-most star is highlighted
                if (ratingInputs.length) {
                    ratingInputs[0].checked = true;
                    updateStarStates(ratingInputs[0].value);
                } else {
                    updateStarStates(0);
                }
            }
        }

        ratingInputs.forEach((input) => {
            const star = form.querySelector(`label[for="${input.id}"]`);

            input.addEventListener('change', () => {
                updateStarStates(input.value);
            });

            if (star) {
                star.addEventListener('mouseenter', () => updateStarStates(input.value));
                star.addEventListener('focus', () => updateStarStates(input.value));
                star.addEventListener('mouseleave', refreshFromChecked);
                star.addEventListener('blur', refreshFromChecked);
                // clicking the label should also set the input (browser does this),
                // but ensure change handler runs by listening to click as well.
                star.addEventListener('click', () => {
                    input.checked = true;
                    updateStarStates(input.value);
                });
            }
        });

        refreshFromChecked();

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
