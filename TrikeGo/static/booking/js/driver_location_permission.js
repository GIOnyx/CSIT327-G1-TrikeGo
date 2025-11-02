document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('location-permission-overlay');
    const enableBtn = document.getElementById('enable-location-btn');
    const promptTitle = document.getElementById('location-prompt-title');
    const promptMessage = document.getElementById('location-prompt-message');
    const body = document.body;

    if (!overlay || !enableBtn || !promptTitle || !promptMessage || !body) {
        return;
    }

    const hasActiveBookings = body.dataset.hasActiveBookings === 'true';
    const updateLocationUrl = body.dataset.updateLocationUrl;

    if (!hasActiveBookings) {
        return;
    }

    if (!('geolocation' in navigator)) {
        alert('Geolocation is not supported by this browser.');
        return;
    }

    function showOverlay() {
        overlay.classList.add('visible');
    }

    function hideOverlay() {
        overlay.classList.remove('visible');
    }

    function requestPermissions() {
        if ('permissions' in navigator && navigator.permissions.query) {
            navigator.permissions.query({ name: 'geolocation' }).then((result) => {
                if (result.state === 'granted') {
                    startLocationWatch();
                } else if (result.state === 'prompt') {
                    showOverlay();
                    enableBtn.onclick = () => {
                        hideOverlay();
                        startLocationWatch();
                    };
                } else if (result.state === 'denied') {
                    showPermissionDeniedError();
                }
            }).catch((error) => {
                console.warn('Unable to query geolocation permissions:', error);
                startLocationWatch();
            });
        } else {
            startLocationWatch();
        }
    }

    function startLocationWatch() {
        const options = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        };

        navigator.geolocation.watchPosition(sendLocation, handleError, options);
    }

    function sendLocation(position) {
        if (!updateLocationUrl) {
            return;
        }

        const { latitude, longitude } = position.coords;

        fetch(updateLocationUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: latitude, lon: longitude })
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.status !== 'success') {
                    console.error('Failed to update location:', data.message);
                }
            })
            .catch((error) => console.error('Error sending location:', error));
    }

    function handleError(error) {
        console.warn(`Geolocation error: ${error.message}`);
        if (error.code === 1) {
            showPermissionDeniedError();
        }
    }

    function showPermissionDeniedError() {
        promptTitle.innerText = 'Location Access Denied';
        promptMessage.innerHTML = 'You have blocked location access for this site. To use live tracking, you must manually enable location permissions in your browser settings. <br><br> Look for the lock icon 🔒 next to the website address.';
        enableBtn.style.display = 'none';
        showOverlay();
    }

    requestPermissions();
});
