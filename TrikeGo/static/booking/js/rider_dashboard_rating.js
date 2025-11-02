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
                    alert(payload.message || 'Rating submitted successfully.');
                    window.location.reload();
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
