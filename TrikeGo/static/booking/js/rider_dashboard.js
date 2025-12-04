// Passenger dashboard JS (moved from template)
(function(){
    const cfg = window.PASSENGER_DASH_CONFIG || {};
    const ORS_API_KEY = cfg.ORS_API_KEY || '';
    const userId = cfg.userId || null;
    const csrfToken = cfg.csrfToken || '';

    // Small helper: escape HTML
    function escapeHtml(str) {
        return String(str).replace(/[&<>"']/g, function (s) {
            return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[s];
        });
    }

    function triggerEmergencyCall() {
        const telUri = 'tel:911';
        const skypeUri = 'skype:911?call';
        const userAgent = (typeof navigator !== 'undefined' && navigator.userAgent) ? navigator.userAgent : '';
        const isMobileDevice = /Mobi|Android|iPhone|iPad|iPod/i.test(userAgent);

        const attemptSkypeFallback = () => {
            try {
                window.location.href = skypeUri;
            } catch (err) {
                try {
                    window.open(skypeUri, '_blank');
                } catch (popupErr) {
                    alert('Please contact emergency services at 911 using your phone or Skype.');
                }
            }
        };

        if (isMobileDevice) {
            window.location.href = telUri;
        } else {
            let telAttempted = false;
            try {
                const telLink = document.createElement('a');
                telLink.href = telUri;
                telLink.style.display = 'none';
                document.body.appendChild(telLink);
                telLink.click();
                document.body.removeChild(telLink);
                telAttempted = true;
            } catch (err) {
                telAttempted = false;
            }

            if (!telAttempted) {
                attemptSkypeFallback();
            } else {
                setTimeout(() => {
                    if (!document.hidden) {
                        attemptSkypeFallback();
                    }
                }, 1200);
            }
        }

        if (navigator && typeof navigator.vibrate === 'function') {
            try {
                navigator.vibrate([180, 70, 180]);
            } catch (vibeErr) { /* optional */ }
        }
    }

    function initEmergencySOSButton() {
        const button = document.getElementById('passenger-sos-button');
        if (!button) return;

        const progressEl = button.querySelector('.sos-button__progress');
        const hintEl = button.querySelector('.sos-button__hint');
        const liveRegion = document.getElementById('passenger-sos-live-region');
        const HOLD_DURATION_MS = 3000;

        let holdTimeoutId = null;
        let rafId = null;
        let holdStart = 0;
        let completed = false;

        const updateProgress = () => {
            if (!holdStart) return;
            const elapsed = performance.now() - holdStart;
            const ratio = Math.min(1, elapsed / HOLD_DURATION_MS);
            if (progressEl) {
                progressEl.style.setProperty('--sos-progress', `${(ratio * 360).toFixed(1)}deg`);
            }
            if (!completed) {
                rafId = requestAnimationFrame(updateProgress);
            }
        };

        const clearTimers = () => {
            if (holdTimeoutId) {
                clearTimeout(holdTimeoutId);
                holdTimeoutId = null;
            }
            if (rafId) {
                cancelAnimationFrame(rafId);
                rafId = null;
            }
        };

        const resetVisuals = () => {
            button.classList.remove('is-holding');
            button.classList.remove('is-complete');
            if (progressEl) {
                progressEl.style.setProperty('--sos-progress', '0deg');
            }
            if (hintEl) {
                hintEl.classList.remove('is-visible');
            }
        };

        const cancelHold = () => {
            if (completed) {
                return;
            }
            clearTimers();
            if (holdStart && liveRegion) {
                liveRegion.textContent = 'Emergency call cancelled.';
                setTimeout(() => {
                    if (liveRegion.textContent === 'Emergency call cancelled.') {
                        liveRegion.textContent = '';
                    }
                }, 1500);
            }
            holdStart = 0;
            completed = false;
            resetVisuals();
        };

        const startHold = (event) => {
            if (event) {
                event.preventDefault();
            }
            if (completed || holdTimeoutId) {
                return;
            }
            holdStart = performance.now();
            if (progressEl) {
                progressEl.style.setProperty('--sos-progress', '0deg');
            }
            button.classList.add('is-holding');
            if (hintEl) {
                hintEl.classList.add('is-visible');
            }
            if (liveRegion) {
                liveRegion.textContent = 'Hold for three seconds to contact emergency services.';
            }
            rafId = requestAnimationFrame(updateProgress);
            holdTimeoutId = window.setTimeout(() => {
                completed = true;
                clearTimers();
                button.classList.remove('is-holding');
                button.classList.add('is-complete');
                if (progressEl) {
                    progressEl.style.setProperty('--sos-progress', '360deg');
                }
                if (liveRegion) {
                    liveRegion.textContent = 'Emergency call starting.';
                }
                triggerEmergencyCall();
                setTimeout(() => {
                    resetVisuals();
                    completed = false;
                    holdStart = 0;
                    if (liveRegion) {
                        liveRegion.textContent = '';
                    }
                }, 1600);
            }, HOLD_DURATION_MS);
        };

        button.addEventListener('pointerdown', startHold);
        button.addEventListener('pointerup', () => {
            if (!completed) {
                cancelHold();
            }
        });
        button.addEventListener('pointerleave', () => {
            if (!completed) {
                cancelHold();
            }
        });
        button.addEventListener('pointercancel', () => {
            if (!completed) {
                cancelHold();
            }
        });

        button.addEventListener('keydown', (event) => {
            if (event.code === 'Space' || event.code === 'Enter') {
                if (event.repeat) {
                    return;
                }
                startHold(event);
            }
        });
        button.addEventListener('keyup', (event) => {
            if (event.code === 'Space' || event.code === 'Enter') {
                if (!completed) {
                    cancelHold();
                }
            }
        });

        button.addEventListener('contextmenu', (event) => {
            event.preventDefault();
        });

        window.addEventListener('blur', () => {
            if (!completed) {
                cancelHold();
            }
        });
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && !completed) {
                cancelHold();
            }
        });
    }

    // ORSAutocomplete class (same behavior as inline version)
    class ORSAutocomplete {
        constructor(inputId, resultsId, latFieldId, lonFieldId, onSelectCallback) {
            this.input = document.getElementById(inputId);
            this.results = document.getElementById(resultsId);
            this.latField = document.getElementById(latFieldId);
            this.lonField = document.getElementById(lonFieldId);
            this.onSelectCallback = onSelectCallback;
            this.timeout = null;
            if (!this.input) return;
            this.init();
        }
        init() {
            this.input.addEventListener('input', (e) => this.handleInput(e));
            document.addEventListener('click', (e) => {
                if (!this.input.contains(e.target) && this.results && !this.results.contains(e.target)) {
                    this.results.classList.remove('active');
                }
            });
        }
        handleInput(e) {
            const query = e.target.value.trim();
            clearTimeout(this.timeout);
            if (query.length < 3) { if (this.results) { this.results.innerHTML = ''; this.results.classList.remove('active'); } return; }
            if (this.results) { this.results.innerHTML = '<div class="loading">Searching...</div>'; this.results.classList.add('active'); }
            this.timeout = setTimeout(() => this.search(query), 300);
        }
        async search(query) {
            try {
                const params = new URLSearchParams({ api_key: ORS_API_KEY, text: query, size: 10, 'boundary.country': 'PH' });
                const url = `https://api.openrouteservice.org/geocode/search?${params.toString()}`;
                const response = await fetch(url);
                const data = await response.json();
                let features = data.features || [];
                try { if (window.map) { const center = window.map.getCenter(); features.forEach(f => { const [lon, lat] = f.geometry.coordinates; f.__distance = window.map.distance(center, L.latLng(lat, lon)); }); features.sort((a,b) => (a.__distance||0) - (b.__distance||0)); } } catch(e){}
                this.displayResults(features);
            } catch (error) {
                console.error('Autocomplete API error:', error);
                if (this.results) this.results.innerHTML = '<div class="loading">Error loading results</div>';
            }
        }
        displayResults(features) {
            if (!this.results) return;
            this.results.innerHTML = '';
            if (features.length === 0) { this.results.innerHTML = '<div class="loading">No results found</div>'; return; }
            features.forEach(feature => {
                const item = document.createElement('div'); item.className = 'autocomplete-item';
                const props = feature.properties || {};
                const name = props.label || props.name || 'Unknown';
                let distanceText = '';
                if (feature.__distance != null) { distanceText = ` <small style="color:#999;margin-left:8px;">(${Math.round(feature.__distance)}m)</small>`; }
                item.innerHTML = `<strong>${name}</strong>${distanceText}`;
                item.addEventListener('click', () => this.selectResult(feature));
                this.results.appendChild(item);
            });
            this.results.classList.add('active');
        }
        selectResult(feature) {
            const coords = feature.geometry.coordinates; const lat = coords[1]; const lon = coords[0]; const props = feature.properties || {};
            this.input.value = props.label || props.name || `${lat}, ${lon}`;
            if (this.latField) this.latField.value = lat; if (this.lonField) this.lonField.value = lon;
            if (this.results) { this.results.classList.remove('active'); this.results.innerHTML = ''; }
            if (this.onSelectCallback) this.onSelectCallback(lat, lon);
        }
    }

    // Chat modal helpers ()
    let _chatModalBookingId = null;
    let _chatModalPolling = null;
    let _chatModalIsOpen = false; // Track if chat is currently open
    const chatModal = document.getElementById('chatModal');
    const chatModalMessages = document.getElementById('chatModalMessages');
    const chatModalForm = document.getElementById('chatModalForm');
    const chatModalInput = document.getElementById('chatModalInput');
    const chatModalTitle = document.getElementById('chatModalTitle');
    const chatModalClose = document.getElementById('chatModalClose');

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) { cookieValue = decodeURIComponent(cookie.substring(name.length + 1)); break; }
            }
        }
        return cookieValue;
    }

    function openChatModal(bookingId) {
        _chatModalBookingId = bookingId;
        _chatModalIsOpen = true; // Set flag
        if (!chatModal) return;
        chatModal.style.display = 'block';
        
        // Match the left positioning of dashboard-booking-card based on open panels
        if (document.body.classList.contains('history-panel-open')) {
            chatModal.style.left = '508px';
        } else {
            chatModal.style.left = '108px';
        }
        
        // Hide ALL booking panels and show chat in their place
        const bookingCard = document.querySelector('.dashboard-booking-card');
        if (bookingCard) {
            bookingCard.style.display = 'none';
        }
        const previewCard = document.getElementById('booking-preview-card');
        if (previewCard) {
            previewCard.style.display = 'none';
        }
        const driverInfoCard = document.getElementById('driver-info-card');
        if (driverInfoCard) {
            driverInfoCard.style.display = 'none';
        }
        
        chatModal.scrollIntoView({ behavior: 'smooth' });
        if (chatModalTitle) chatModalTitle.textContent = `Chat (Booking ${bookingId})`;
        loadModalMessages();
        if (!_chatModalBookingId) return;
        if (window._chatModalPolling) clearInterval(window._chatModalPolling);
        // Prefer push updates when SW controls the page
        if (navigator.serviceWorker && navigator.serviceWorker.controller) {
            console.log('Using push for passenger chat updates');
        } else {
            // Poll less often for chat as a fallback
            window._chatModalPolling = setInterval(loadModalMessages, 6000);
        }
    }

    function closeChatModal() { 
        if (!chatModal) return; 
        chatModal.style.display = 'none'; 
        _chatModalIsOpen = false; // Clear flag
        
        // Restore ALL booking panels visibility
        const bookingCard = document.querySelector('.dashboard-booking-card');
        if (bookingCard) {
            bookingCard.style.display = 'block';
        }
        const previewCard = document.getElementById('booking-preview-card');
        if (previewCard && previewCard.getAttribute('data-was-visible') !== 'false') {
            previewCard.style.display = 'block';
        }
        const driverInfoCard = document.getElementById('driver-info-card');
        if (driverInfoCard && driverInfoCard.getAttribute('data-was-visible') !== 'false') {
            driverInfoCard.style.display = 'block';
        }
        
        _chatModalBookingId = null; 
        if (window._chatModalPolling) { 
            clearInterval(window._chatModalPolling); 
            window._chatModalPolling = null; 
        } 
    }

    // ORS / routing rate-limit guard and previous-coords cache to avoid excessive routing requests
    let _orsRateLimitedUntil = 0;
    let _prevDriverToPickupCoords = null;
    let _prevPickupToDestCoords = null;
    let _lastDTData = null;
    let _lastRDData = null;

    async function loadModalMessages() {
        if (!_chatModalBookingId || !chatModalMessages) return;
        const res = await fetch(`/chat/api/booking/${_chatModalBookingId}/messages/`, { credentials: 'same-origin' });
        if (!res.ok) { chatModalMessages.innerHTML = '<p class="muted">Unable to load messages.</p>'; return; }
        const data = await res.json(); chatModalMessages.innerHTML = '';
        if (!data.messages || data.messages.length === 0) { chatModalMessages.innerHTML = '<p class="muted">No messages yet.</p>'; return; }
        let lastDate = null;
        data.messages.forEach(m => {
            const msgDate = new Date(m.timestamp).toDateString();
            if (msgDate !== lastDate) { const sep = document.createElement('div'); sep.className = 'chat-date-sep'; sep.textContent = new Date(m.timestamp).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }); chatModalMessages.appendChild(sep); lastDate = msgDate; }
            const div = document.createElement('div'); const own = (m.sender_id == userId); div.className = own ? 'chat-msg-own' : 'chat-msg-other'; div.innerHTML = `<div class="chat-msg-meta">${m.sender_username} • ${new Date(m.timestamp).toLocaleTimeString()}</div><div>${escapeHtml(m.message)}</div>`; chatModalMessages.appendChild(div);
        });
        try { const newest = chatModalMessages.lastElementChild; chatModalMessages.scrollTo({ top: chatModalMessages.scrollHeight, behavior: 'smooth' }); if (newest) { newest.classList.add('flash-animate'); setTimeout(() => newest.classList.remove('flash-animate'), 900); } } catch(e) { chatModalMessages.scrollTop = chatModalMessages.scrollHeight; }
    }

    if (chatModalClose) chatModalClose.addEventListener('click', (e) => { e.preventDefault(); closeChatModal(); });

    if (chatModalForm) chatModalForm.addEventListener('submit', async (e) => {
        e.preventDefault(); if (!_chatModalBookingId) return; const text = (chatModalInput.value || '').trim(); if (!text) return;
        const res = await fetch(`/chat/api/booking/${_chatModalBookingId}/messages/send/`, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') }, body: JSON.stringify({ message: text }) });
        if (!res.ok) { alert('Failed to send message'); return; }
        chatModalInput.value = ''; loadModalMessages();
    });

// Listen for push messages forwarded by the service worker and refresh chat when appropriate
try {
    if (navigator.serviceWorker && navigator.serviceWorker.addEventListener) {
        navigator.serviceWorker.addEventListener('message', function (evt) {
            try {
                const payload = evt.data || {};
                const data = (payload && payload.data) ? payload.data : payload;
                if (!data || data.type !== 'chat_message') return;
                const bid = data.booking_id;
                if (!bid) return;
                if (_chatModalBookingId && String(_chatModalBookingId) === String(bid)) {
                    loadModalMessages();
                } else {
                    // Optionally show indicator for new messages for other bookings
                }
            } catch (e) { /* ignore */ }
        });
    }
} catch (e) { /* ignore */ }

    // Export small helpers used by other pieces of UI
    window.openChatModal = openChatModal; window.closeChatModal = closeChatModal;

    // Initialize map and autocomplete on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', () => {
        initEmergencySOSButton();
        const openTripHistoryLink = document.getElementById('open-trip-history-link');
        if (openTripHistoryLink) {
            openTripHistoryLink.addEventListener('click', (event) => {
                event.preventDefault();
                const historyIcon = document.getElementById('passenger-history-icon');
                if (historyIcon) {
                    historyIcon.click();
                }
            });
        }

        try {
            window.map = L.map('map').setView([14.5995, 120.9842], 12);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors', maxZoom: 19 }).addTo(window.map);
            if (navigator.geolocation) navigator.geolocation.getCurrentPosition((pos) => { window.map.setView([pos.coords.latitude, pos.coords.longitude], 15); }, () => {}, { enableHighAccuracy: true, timeout: 5000 });
        } catch (e) { console.warn('Leaflet/map init failed', e); }

        // Keep track of the last focused booking input (so clicks on the map can still target it)
        window._lastFocusedBookingInputId = null;
        const bookingInputIds = ['pickup_location_input', 'destination_location_input'];
        document.addEventListener('focusin', (ev) => {
            try {
                const id = ev.target && ev.target.id ? ev.target.id : null;
                if (bookingInputIds.includes(id)) window._lastFocusedBookingInputId = id;
            } catch(e) {}
        });

        // Helper functions to place/update temporary markers for inputs (when user selects an address or clicks map)
        function setPickupInputMarker(lat, lon, label) {
            try {
                const latLng = [lat, lon];
                if (!pickupMarker) {
                    const pickupIcon = L.divIcon({ className: 'pickup-marker', html: '<div style="background: #ffc107; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white;"></div>', iconSize: [20,20] });
                    pickupMarker = L.marker(latLng, { icon: pickupIcon }).addTo(window.map).bindPopup(label || 'Pickup');
                } else {
                    pickupMarker.setLatLng(latLng);
                    if (pickupMarker.getPopup()) pickupMarker.getPopup().setContent(label || 'Pickup');
                }
                try { window.map.setView(latLng, 16); } catch(e){}
            } catch(e) { console.warn('setPickupInputMarker failed', e); }
        }

        function setDestinationInputMarker(lat, lon, label) {
            try {
                const latLng = [lat, lon];
                if (!destinationMarker) {
                    const destIcon = L.divIcon({ className: 'dest-marker', html: '<div style="background: #007bff; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white;"></div>', iconSize: [20,20] });
                    destinationMarker = L.marker(latLng, { icon: destIcon }).addTo(window.map).bindPopup(label || 'Destination');
                } else {
                    destinationMarker.setLatLng(latLng);
                    if (destinationMarker.getPopup()) destinationMarker.getPopup().setContent(label || 'Destination');
                }
                try { window.map.setView(latLng, 16); } catch(e){}
            } catch(e) { console.warn('setDestinationInputMarker failed', e); }
        }

        try { new ORSAutocomplete('pickup_location_input', 'pickup-results', 'id_pickup_latitude', 'id_pickup_longitude', (lat, lon) => { try { window.map.setView([lat, lon], 16); setPickupInputMarker(lat, lon); } catch(e){} }); } catch(e){}
        try { new ORSAutocomplete('destination_location_input', 'destination-results', 'id_destination_latitude', 'id_destination_longitude', (lat, lon) => { try { window.map.setView([lat, lon], 16); setDestinationInputMarker(lat, lon); } catch(e){} }); } catch(e){}

        // When hidden lat/lon fields are programmatically updated elsewhere, reflect them on the map.
        try {
            const hidPickupLat = document.getElementById('id_pickup_latitude');
            const hidPickupLon = document.getElementById('id_pickup_longitude');
            const hidDestLat = document.getElementById('id_destination_latitude');
            const hidDestLon = document.getElementById('id_destination_longitude');
            function tryPlacePickupFromHidden() {
                try {
                    const lat = parseFloat(hidPickupLat?.value);
                    const lon = parseFloat(hidPickupLon?.value);
                    if (!Number.isNaN(lat) && !Number.isNaN(lon)) setPickupInputMarker(lat, lon, document.getElementById('pickup_location_input')?.value || 'Pickup');
                } catch(e){}
            }
            function tryPlaceDestFromHidden() {
                try {
                    const lat = parseFloat(hidDestLat?.value);
                    const lon = parseFloat(hidDestLon?.value);
                    if (!Number.isNaN(lat) && !Number.isNaN(lon)) setDestinationInputMarker(lat, lon, document.getElementById('destination_location_input')?.value || 'Destination');
                } catch(e){}
            }
            if (hidPickupLat && hidPickupLon) {
                hidPickupLat.addEventListener('change', tryPlacePickupFromHidden);
                hidPickupLon.addEventListener('change', tryPlacePickupFromHidden);
            }
            if (hidDestLat && hidDestLon) {
                hidDestLat.addEventListener('change', tryPlaceDestFromHidden);
                hidDestLon.addEventListener('change', tryPlaceDestFromHidden);
            }
        } catch(e) {}

        // Map click -> reverse geocode into focused booking input
        try {
            if (window.map) {
                async function reverseGeocodeAndFill(lat, lon) {
                    const key = ORS_API_KEY || (window.PASSENGER_DASH_CONFIG && window.PASSENGER_DASH_CONFIG.ORS_API_KEY) || '';
                    if (!key) return null;
                    const url = `https://api.openrouteservice.org/geocode/reverse?api_key=${encodeURIComponent(key)}&point.lat=${encodeURIComponent(lat)}&point.lon=${encodeURIComponent(lon)}&size=1`;
                    try {
                        const res = await fetch(url);
                        if (!res.ok) return null;
                        const data = await res.json();
                        const feat = (data.features && data.features[0]) ? data.features[0] : null;
                        const label = feat?.properties?.label || feat?.properties?.name || null;
                        return label ? { label, props: feat.properties } : null;
                    } catch (e) { console.warn('Reverse geocode failed', e); return null; }
                }

                window.map.on('click', async function(e) {
                    try {
                        // Prefer the element that was last focused in booking inputs (clicking the map itself moves focus away)
                        const lastId = window._lastFocusedBookingInputId || null;
                        const active = document.activeElement;
                        const activeId = (active && (active.id || active.getAttribute('id'))) ? (active.id || active.getAttribute('id')) : null;
                        const id = (activeId && ['pickup_location_input','destination_location_input'].includes(activeId)) ? activeId : lastId;
                        if (!id) return;
                        const lat = e.latlng.lat; const lon = e.latlng.lng;
                        const result = await reverseGeocodeAndFill(lat, lon);
                        const label = result?.label || `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
                        // fill visible input and hidden lat/lon fields
                        const inputEl = document.getElementById(id);
                        if (inputEl) inputEl.value = label;
                        if (id === 'pickup_location_input') {
                            const hLat = document.getElementById('id_pickup_latitude');
                            const hLon = document.getElementById('id_pickup_longitude');
                            if (hLat) hLat.value = lat; if (hLon) hLon.value = lon;
                            // show marker
                            setPickupInputMarker(lat, lon, label);
                        } else if (id === 'destination_location_input') {
                            const hLat = document.getElementById('id_destination_latitude');
                            const hLon = document.getElementById('id_destination_longitude');
                            if (hLat) hLat.value = lat; if (hLon) hLon.value = lon;
                            // show marker
                            setDestinationInputMarker(lat, lon, label);
                        }
                    } catch (err) { console.warn('Map click handler error', err); }
                });
            }
        } catch (e) { /* non-critical */ }
    });
            // Booking / tracking variables and helpers
        let trackingInterval = null;
    let driverMarker = null;
    let pickupMarker = null;
    let destinationMarker = null;
    let itineraryRouteLayer = null;
    let itineraryRouteSignature = null;
    let fallbackRouteLayer = null;
        // Track whether we've performed the initial route fetch for a given booking/stage.
        // We want the loader to appear once when previewing a pending booking and once again
        // after a driver accepts (active stage).
        const initialRouteLoadDoneForBooking = new Set();

        function markRouteStageLoaded(bookingId, stage) {
            if (!bookingId) return;
            initialRouteLoadDoneForBooking.add(`${bookingId}:${stage}`);
        }

        function isRouteStageLoaded(bookingId, stage) {
            return bookingId ? initialRouteLoadDoneForBooking.has(`${bookingId}:${stage}`) : false;
        }

        function resetRouteStage(bookingId, stage) {
            if (!bookingId) return;
            initialRouteLoadDoneForBooking.delete(`${bookingId}:${stage}`);
        }
        let stopMarkers = [];
        let currentTrackedBookingId = null;

        function clearItineraryRouteLayer() {
            if (itineraryRouteLayer && window.map) {
                try { window.map.removeLayer(itineraryRouteLayer); } catch (err) { /* ignore */ }
            }
            itineraryRouteLayer = null;
            itineraryRouteSignature = null;
        }

        function clearFallbackRouteLayer() {
            if (fallbackRouteLayer && window.map) {
                try { window.map.removeLayer(fallbackRouteLayer); } catch (err) { /* ignore */ }
            }
            fallbackRouteLayer = null;
        }

        function renderSharedItineraryRoute(itinerary) {
            if (!window.map || !itinerary) {
                clearItineraryRouteLayer();
                return null;
            }

            const signatureSource = Array.isArray(itinerary.fullRouteSegments) && itinerary.fullRouteSegments.length
                ? itinerary.fullRouteSegments
                : itinerary.fullRoutePolyline;
            const signature = JSON.stringify(signatureSource || []);

            if (itineraryRouteLayer && itineraryRouteSignature === signature) {
                if (!window.map.hasLayer(itineraryRouteLayer)) {
                    itineraryRouteLayer.addTo(window.map);
                }
                return typeof itineraryRouteLayer.getBounds === 'function' ? itineraryRouteLayer.getBounds() : null;
            }

            clearItineraryRouteLayer();

            const segments = Array.isArray(itinerary.fullRouteSegments) ? itinerary.fullRouteSegments : [];
            const segmentLayers = [];
            segments.forEach(segment => {
                const rawPoints = Array.isArray(segment?.points) ? segment.points : [];
                const coords = rawPoints.map(pt => {
                    if (!Array.isArray(pt) || pt.length < 2) return null;
                    const lat = Number(pt[0]);
                    const lon = Number(pt[1]);
                    return (Number.isFinite(lat) && Number.isFinite(lon)) ? [lat, lon] : null;
                }).filter(Boolean);
                if (coords.length >= 2) {
                    segmentLayers.push(L.polyline(coords, { color: '#0b63d6', weight: 5, opacity: 0.9 }));
                }
            });

            if (!segmentLayers.length) {
                const fallbackPoints = Array.isArray(itinerary.fullRoutePolyline) ? itinerary.fullRoutePolyline : [];
                const coords = fallbackPoints.map(pt => {
                    if (!Array.isArray(pt) || pt.length < 2) return null;
                    const lat = Number(pt[0]);
                    const lon = Number(pt[1]);
                    return (Number.isFinite(lat) && Number.isFinite(lon)) ? [lat, lon] : null;
                }).filter(Boolean);
                if (coords.length >= 2) {
                    segmentLayers.push(L.polyline(coords, { color: '#0b63d6', weight: 5, opacity: 0.88 }));
                }
            }

            if (!segmentLayers.length) {
                itineraryRouteLayer = null;
                itineraryRouteSignature = null;
                return null;
            }

            const featureGroup = L.featureGroup(segmentLayers).addTo(window.map);
            itineraryRouteLayer = featureGroup;
            itineraryRouteSignature = signature;
            return typeof featureGroup.getBounds === 'function' ? featureGroup.getBounds() : null;
        }

            async function updateAll(bookingId) {
                const loader = document.getElementById('route-loader');
                const bookingKey = String(bookingId);
                let stage = (currentTrackedBookingId && String(currentTrackedBookingId) === bookingKey) ? 'active' : 'preview';
                let stageKey = `${bookingKey}:${stage}`;
                let loaderShowing = false;
                // Only show loader if this stage hasn't been loaded yet
                if (loader && !isRouteStageLoaded(bookingKey, stage)) {
                    loader.classList.remove('hidden');
                    loader.setAttribute('aria-hidden', 'false');
                    loaderShowing = true;
                }
                let infoRes;
                let stageLoadedSuccessfully = false;
                try {
                    infoRes = await fetch(`/api/booking/${bookingId}/route_info/`);
                    if (!infoRes.ok) {
                        console.error('Failed to fetch route info:', infoRes.status);
                        return;
                    }
                    const info = await infoRes.json();
                    if (info.status !== 'success') {
                        console.error('Route info error:', info.message);
                        return;
                    }

                    const infoBookingStatus = (info.booking_status || '').toLowerCase();
                    const driverAssigned = Boolean(info.driver || info.driver_id || info.driver_name || infoBookingStatus === 'accepted' || infoBookingStatus === 'on_the_way' || infoBookingStatus === 'started');
                    const resolvedStage = driverAssigned ? 'active' : 'preview';
                    // Only update stage and show loader if stage changed AND new stage not loaded yet
                    if (resolvedStage !== stage) {
                        const oldStage = stage;
                        stage = resolvedStage;
                        stageKey = `${bookingKey}:${stage}`;
                        // Show loader only if switching to a new stage that hasn't been loaded AND loader isn't already showing
                        if (loader && !loaderShowing && !isRouteStageLoaded(bookingKey, stage)) {
                            loader.classList.remove('hidden');
                            loader.setAttribute('aria-hidden', 'false');
                            loaderShowing = true;
                            console.debug('[Passenger Dashboard] Stage changed from', oldStage, 'to', stage, '— showing loader');
                        } else {
                            console.debug('[Passenger Dashboard] Stage changed from', oldStage, 'to', stage, '— loader already shown or stage already loaded');
                        }
                    }

                    const dLat = (info.driver_lat != null) ? Number(info.driver_lat) : null;
                    const dLon = (info.driver_lon != null) ? Number(info.driver_lon) : null;
                    const pLat = Number(info.pickup_lat);
                    const pLon = Number(info.pickup_lon);
                    const xLat = Number(info.destination_lat);
                    const xLon = Number(info.destination_lon);

                    console.log('[Passenger Dashboard] Driver coordinates:', { 
                        driver_lat: info.driver_lat, 
                        driver_lon: info.driver_lon, 
                        dLat, 
                        dLon,
                        booking_status: info.booking_status 
                    });

                    const hasDriver = (dLat != null && dLon != null && Number.isFinite(dLat) && Number.isFinite(dLon));
                    const hasPickup = Number.isFinite(pLat) && Number.isFinite(pLon);
                    const hasDest = Number.isFinite(xLat) && Number.isFinite(xLon);
                    const itineraryPayload = info && typeof info.itinerary === 'object' ? info.itinerary : null;
                    const stopsSource = itineraryPayload && Array.isArray(itineraryPayload.stops) ? itineraryPayload.stops : null;
                    const stopsList = Array.isArray(stopsSource) && stopsSource.length ? stopsSource : (Array.isArray(info.stops) ? info.stops : []);
                    const hasStops = stopsList.length > 0;
                    const hasSharedItinerary = Boolean(itineraryPayload && hasStops);
                    const bookingIdNum = Number(bookingId);
                    const bookingStatusLower = (info.booking_status || '').toLowerCase();
                    const passengerOnBoard = bookingStatusLower === 'started' || bookingStatusLower === 'completed';
                    const bookingSummaries = Array.isArray(itineraryPayload?.bookingSummaries) ? itineraryPayload.bookingSummaries : [];
                    const itinerarySummary = bookingSummaries.find((summary) => Number(summary.bookingId) === bookingIdNum) || null;
                    const routePayload = info.route_payload || null;

                    // Update fare display in active and preview cards
                    let appliedFareText = '--';
                    try {
                        let fareNumeric = null;
                        if (typeof info.fare === 'number') {
                            fareNumeric = info.fare;
                        } else if (info.fare != null) {
                            const parsedFare = Number(info.fare);
                            if (Number.isFinite(parsedFare)) {
                                fareNumeric = parsedFare;
                            }
                        }

                        let fareText = (typeof info.fare_display === 'string' && info.fare_display.trim() !== '') ? info.fare_display : null;
                        if (!fareText) {
                            fareText = Number.isFinite(fareNumeric) ? `₱${fareNumeric.toFixed(2)}` : '--';
                        }

                        if (fareText && fareText !== '--') {
                            appliedFareText = fareText;
                        }
                        
                        console.log('[Passenger Dashboard] Fare data:', { 
                            fare: info.fare, 
                            fare_display: info.fare_display, 
                            fareNumeric, 
                            fareText, 
                            appliedFareText 
                        });

                        ['active-card-fare', 'preview-fare'].forEach((id) => {
                            const el = document.getElementById(id);
                            if (el) {
                                el.textContent = appliedFareText;
                                console.log(`[Passenger Dashboard] Updated #${id} to:`, appliedFareText);
                            }
                        });
                    } catch (e) {
                        console.warn('Fare display update failed', e);
                    }

                    // Update markers (driver + numbered stops or fallback pickup/destination markers)
                    const boundsPoints = [];

                    try {
                        if (!window.map) {
                            throw new Error('Map not initialised');
                        }

                        // Always clear previously rendered stop markers
                        if (stopMarkers.length) {
                            stopMarkers.forEach(marker => {
                                try { window.map.removeLayer(marker); } catch (err) { /* ignore */ }
                            });
                            stopMarkers = [];
                        }

                        if (hasDriver) {
                            const driverLatLng = [dLat, dLon];
                            if (!driverMarker) {
                                const driverIcon = L.divIcon({ className: 'driver-marker', html: '<div style="background: #28a745; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white;"></div>', iconSize: [28,28] });
                                driverMarker = L.marker(driverLatLng, { icon: driverIcon }).addTo(window.map).bindPopup('Driver');
                            } else {
                                driverMarker.setLatLng(driverLatLng);
                            }
                            boundsPoints.push(driverLatLng);
                        } else if (driverMarker) {
                            try { window.map.removeLayer(driverMarker); } catch (err) { /* ignore */ }
                            driverMarker = null;
                        }

                        if (hasStops) {
                            if (pickupMarker) { try { window.map.removeLayer(pickupMarker); } catch (err) { /* ignore */ } pickupMarker = null; }
                            if (destinationMarker) { try { window.map.removeLayer(destinationMarker); } catch (err) { /* ignore */ } destinationMarker = null; }

                            stopsList.forEach((stop, idx) => {
                                const rawLat = stop.lat ?? stop.latitude ?? (Array.isArray(stop.coordinates) ? stop.coordinates[0] : null);
                                const rawLon = stop.lon ?? stop.longitude ?? (Array.isArray(stop.coordinates) ? stop.coordinates[1] : null);
                                const latNum = Number(rawLat);
                                const lonNum = Number(rawLon);
                                if (!Number.isFinite(latNum) || !Number.isFinite(lonNum)) {
                                    return;
                                }

                                let sequenceNumber = Number(stop.sequence);
                                if (!Number.isFinite(sequenceNumber) || sequenceNumber <= 0) {
                                    sequenceNumber = idx + 1;
                                }

                                const typeKey = (stop.type || '').toUpperCase();
                                const iconClass = typeKey === 'PICKUP' ? 'pickup-marker' : 'dest-marker';
                                const markerHtml = `<div class="marker-inner"><span class="marker-number">${sequenceNumber}</span></div>`;
                                const stopIcon = L.divIcon({ className: `stop-marker ${iconClass}`, html: markerHtml, iconSize: [32, 36], iconAnchor: [16, 36] });

                                const marker = L.marker([latNum, lonNum], { icon: stopIcon }).addTo(window.map);
                                try { if (typeof marker.setZIndexOffset === 'function') marker.setZIndexOffset(800 + (stopsList.length - idx)); } catch (e) { /* ignore */ }

                                const labelParts = [];
                                const defaultLabel = typeKey === 'PICKUP' ? 'Pickup' : (typeKey === 'DROPOFF' ? 'Drop-off' : 'Stop');
                                labelParts.push(defaultLabel);
                                if (stop.bookingId) { labelParts.push(`Booking #${escapeHtml(String(stop.bookingId))}`); }
                                if (stop.address) { labelParts.push(escapeHtml(String(stop.address))); }
                                const pax = Number(stop.passengerCount);
                                if (Number.isFinite(pax) && pax > 0) {
                                    labelParts.push(`${pax} passenger${pax === 1 ? '' : 's'}`);
                                }
                                const fareText = stop.bookingFareDisplay || (Number.isFinite(stop.bookingFare) ? `₱${Number(stop.bookingFare).toFixed(2)}` : null);
                                if (stop.isFirstForBooking && fareText) {
                                    labelParts.push(`Fare: ${escapeHtml(fareText)}`);
                                }
                                marker.bindPopup(labelParts.join('<br>') || `Stop ${sequenceNumber}`);
                                stopMarkers.push(marker);
                                boundsPoints.push([latNum, lonNum]);
                            });
                        } else {
                            if (pickupMarker && !hasPickup) { try { window.map.removeLayer(pickupMarker); } catch (err) { /* ignore */ } pickupMarker = null; }
                            if (destinationMarker && !hasDest) { try { window.map.removeLayer(destinationMarker); } catch (err) { /* ignore */ } destinationMarker = null; }

                            if (hasPickup) {
                                const pickupLatLng = [pLat, pLon];
                                if (!pickupMarker) {
                                    const pickupIcon = L.divIcon({ className: 'pickup-marker', html: '<div style="background: #ffc107; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white;"></div>', iconSize: [20,20] });
                                    pickupMarker = L.marker(pickupLatLng, { icon: pickupIcon }).addTo(window.map).bindPopup('Pickup');
                                } else {
                                    pickupMarker.setLatLng(pickupLatLng);
                                }
                                boundsPoints.push(pickupLatLng);
                            }
                            if (hasDest) {
                                const destLatLng = [xLat, xLon];
                                if (!destinationMarker) {
                                    const destIcon = L.divIcon({ className: 'dest-marker', html: '<div style="background: #007bff; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white;"></div>', iconSize: [20,20] });
                                    destinationMarker = L.marker(destLatLng, { icon: destIcon }).addTo(window.map).bindPopup('Destination');
                                } else {
                                    destinationMarker.setLatLng(destLatLng);
                                }
                                boundsPoints.push(destLatLng);
                            }
                        }
                    } catch (e) { console.warn('Marker update failed', e); }

                    let sharedRouteBounds = null;
                    let sharedRouteActive = false;
                    if (hasSharedItinerary) {
                        try {
                            sharedRouteBounds = renderSharedItineraryRoute(itineraryPayload);
                            sharedRouteActive = Boolean(itineraryRouteLayer);
                            if (sharedRouteActive) {
                                clearFallbackRouteLayer();
                            }
                        } catch (routeErr) {
                            console.warn('Shared route render failed', routeErr);
                        }
                    } else {
                        clearItineraryRouteLayer();
                    }

                    // Fetch routes when appropriate, but avoid repeated ORS calls if coords unchanged or rate-limited
                    let dtData = null, rdData = null;
                    try {
                        const now = Date.now();
                        const rateLimited = (_orsRateLimitedUntil && now < _orsRateLimitedUntil);
                        if (!rateLimited) {
                            if (hasDriver && hasPickup) {
                                const driverPickupKey = `${dLat},${dLon}|${pLat},${pLon}`;
                                if (driverPickupKey !== _prevDriverToPickupCoords) {
                                    const dtUrl = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${ORS_API_KEY}&start=${dLon},${dLat}&end=${pLon},${pLat}`;
                                    try {
                                        const dtRes = await fetch(dtUrl);
                                        if (dtRes.status === 429) { _orsRateLimitedUntil = now + 30000; console.warn('ORS rate limit detected (429)'); }
                                        else { dtData = await dtRes.json(); _lastDTData = dtData; _prevDriverToPickupCoords = driverPickupKey; }
                                    } catch(e) { console.warn('Driver->pickup route fetch failed', e); }
                                } else {
                                    dtData = _lastDTData;
                                }
                            }

                            if (hasPickup && hasDest) {
                                const pickupDestKey = `${pLat},${pLon}|${xLat},${xLon}`;
                                if (pickupDestKey !== _prevPickupToDestCoords) {
                                    const rdUrl = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${ORS_API_KEY}&start=${pLon},${pLat}&end=${xLon},${xLat}`;
                                    try {
                                        const rdRes = await fetch(rdUrl);
                                        if (rdRes.status === 429) { _orsRateLimitedUntil = now + 30000; console.warn('ORS rate limit detected (429)'); }
                                        else { rdData = await rdRes.json(); _lastRDData = rdData; _prevPickupToDestCoords = pickupDestKey; }
                                    } catch(e) { console.warn('Pickup->dest route fetch failed', e); }
                                } else {
                                    rdData = _lastRDData;
                                }
                            }
                        } else {
                            console.warn('Skipping ORS calls until', new Date(_orsRateLimitedUntil));
                        }
                    } catch(e) { console.warn('Route fetch failed', e); }

                    const allowFallbackRoute = !sharedRouteActive;
                    if (allowFallbackRoute) {
                        clearFallbackRouteLayer();
                        const routeLayers = [];
                        try {
                            if (dtData && dtData.features && dtData.features.length > 0) {
                                routeLayers.push(L.geoJSON(dtData.features[0], { style: { color: '#0b63d6', weight: 5, opacity: 0.85 } }));
                            }
                            if (rdData && rdData.features && rdData.features.length > 0) {
                                routeLayers.push(L.geoJSON(rdData.features[0], { style: { color: '#0b63d6', weight: 5, opacity: 0.85 } }));
                            }
                            if (routeLayers.length > 0) {
                                fallbackRouteLayer = L.featureGroup(routeLayers).addTo(window.map);
                            }
                        } catch(e) { console.warn('Add fallback route failed', e); }
                    }

                    // Fit map to show layers if present
                    try {
                        let bounds = null;
                        if (sharedRouteBounds && typeof sharedRouteBounds.isValid === 'function' ? sharedRouteBounds.isValid() : sharedRouteBounds) {
                            bounds = sharedRouteBounds.clone ? sharedRouteBounds.clone() : sharedRouteBounds;
                        } else if (!sharedRouteBounds && fallbackRouteLayer && typeof fallbackRouteLayer.getBounds === 'function') {
                            bounds = fallbackRouteLayer.getBounds();
                        }

                        boundsPoints.forEach(([lat, lon]) => {
                            if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
                            const point = L.latLng(lat, lon);
                            if (!bounds) {
                                bounds = L.latLngBounds(point, point);
                            } else {
                                bounds.extend(point);
                            }
                        });

                        if (bounds && (typeof bounds.isValid !== 'function' || bounds.isValid())) {
                            window.map.fitBounds(bounds, { padding: [50,50], maxZoom: 17 });
                        }
                    } catch(e) {}

                    // Update ETA and distance UI focusing on passenger trip (pickup → destination)
                    try {
                        const etaLabel = document.getElementById('eta-label');
                        const etaValue = document.getElementById('eta-value');
                        const distanceValue = document.getElementById('distance-value');

                        let driverLegDistanceKm = null;
                        let driverLegDurationSec = null;
                        if (dtData && dtData.features?.[0]?.properties?.segments?.[0]) {
                            const seg = dtData.features[0].properties.segments[0];
                            driverLegDistanceKm = Number(seg.distance) / 1000;
                            driverLegDurationSec = Number(seg.duration);
                        }
                        if (!Number.isFinite(driverLegDistanceKm)) {
                            const fallbackDriverDistance = Number(info.driver_to_pickup_km);
                            if (Number.isFinite(fallbackDriverDistance)) {
                                driverLegDistanceKm = fallbackDriverDistance;
                            }
                        }

                        let tripDistanceKm = null;
                        let tripDurationMinutes = null;
                        let tripDurationSecSource = null;

                        if (rdData && rdData.features?.[0]?.properties?.segments?.[0]) {
                            const seg = rdData.features[0].properties.segments[0];
                            const rawDistKm = Number(seg.distance) / 1000;
                            const rawDurationSec = Number(seg.duration);
                            if (Number.isFinite(rawDistKm)) {
                                tripDistanceKm = rawDistKm;
                            }
                            if (Number.isFinite(rawDurationSec)) {
                                tripDurationSecSource = rawDurationSec;
                                tripDurationMinutes = Math.max(0, Math.round(rawDurationSec / 60));
                            }
                        }

                        if (!Number.isFinite(tripDistanceKm) && itinerarySummary) {
                            const summaryDist = Number(itinerarySummary.remainingDistanceKm);
                            if (Number.isFinite(summaryDist)) {
                                let adjusted = summaryDist;
                                if (!passengerOnBoard && Number.isFinite(driverLegDistanceKm)) {
                                    adjusted = Math.max(0, adjusted - driverLegDistanceKm);
                                }
                                tripDistanceKm = adjusted;
                            }
                        }

                        if (tripDurationMinutes == null && itinerarySummary) {
                            let summaryDurationSec = Number(itinerarySummary.remainingDurationSec);
                            if (Number.isFinite(summaryDurationSec)) {
                                if (!passengerOnBoard && Number.isFinite(driverLegDurationSec)) {
                                    summaryDurationSec = Math.max(0, summaryDurationSec - driverLegDurationSec);
                                }
                                tripDurationMinutes = Math.max(0, Math.round(summaryDurationSec / 60));
                            } else {
                                const summaryDurationMinutes = Number(itinerarySummary.remainingDurationMinutes);
                                if (Number.isFinite(summaryDurationMinutes)) {
                                    const adjustedMinutes = !passengerOnBoard && Number.isFinite(driverLegDurationSec)
                                        ? Math.max(0, summaryDurationMinutes - Math.round(driverLegDurationSec / 60))
                                        : summaryDurationMinutes;
                                    tripDurationMinutes = Math.max(0, Math.round(adjustedMinutes));
                                }
                            }
                        }

                        if (!Number.isFinite(tripDistanceKm)) {
                            const fallbackDist = Number(
                                (routePayload && routePayload.distance) ??
                                info.pickup_to_destination_km ??
                                info.estimated_distance_km
                            );
                            if (Number.isFinite(fallbackDist)) {
                                tripDistanceKm = fallbackDist;
                            }
                        }

                        if (tripDurationMinutes == null) {
                            if (Number.isFinite(tripDurationSecSource)) {
                                tripDurationMinutes = Math.max(0, Math.round(tripDurationSecSource / 60));
                            } else {
                                const fallbackEtaMinutes = Number(info.estimated_duration_min);
                                if (Number.isFinite(fallbackEtaMinutes)) {
                                    tripDurationMinutes = Math.max(0, Math.round(fallbackEtaMinutes));
                                } else if (itinerarySummary) {
                                    const summaryDuration = Number(itinerarySummary.remainingDurationSec);
                                    if (Number.isFinite(summaryDuration)) {
                                        const safeDuration = Math.max(0, summaryDuration);
                                        tripDurationMinutes = Math.max(0, Math.round(safeDuration / 60));
                                    } else {
                                        const summaryMinutes = Number(itinerarySummary.remainingDurationMinutes);
                                        if (Number.isFinite(summaryMinutes)) {
                                            tripDurationMinutes = Math.max(0, Math.round(Math.max(0, summaryMinutes)));
                                        }
                                    }
                                } else if (routePayload && Number.isFinite(Number(routePayload.duration))) {
                                    const routeDurationSec = Number(routePayload.duration);
                                    tripDurationMinutes = Math.max(0, Math.round(routeDurationSec / 60));
                                }
                            }
                        }

                        const hasTripDistance = Number.isFinite(tripDistanceKm);
                        const hasTripDuration = Number.isFinite(tripDurationMinutes);
                        const formattedDistance = hasTripDistance ? `${tripDistanceKm.toFixed(2)} km` : '--';
                        const formattedEta = hasTripDuration ? `${tripDurationMinutes} min` : '--';

                        if (etaLabel) {
                            etaLabel.textContent = 'Trip ETA:';
                        }
                        if (etaValue) {
                            etaValue.textContent = formattedEta;
                        }
                        if (distanceValue) {
                            distanceValue.textContent = formattedDistance;
                        }

                        const cardEta = document.getElementById('card-eta');
                        const cardDistance = document.getElementById('card-distance');
                        const cardPickup = document.getElementById('card-pickup');
                        const cardDest = document.getElementById('card-dest');
                        if (cardEta) cardEta.textContent = formattedEta;
                        if (cardDistance) cardDistance.textContent = formattedDistance;

                        let pickupAddr = info.pickup_address || null;
                        let destAddr = info.destination_address || null;
                        if ((!pickupAddr || !destAddr) && bookingId) {
                            const bookingEl = document.querySelector(`.booking-item[data-booking-id="${bookingId}"]`);
                            if (bookingEl) {
                                const txt = (bookingEl.textContent || '').trim();
                                const parts = txt.split('→');
                                if (!pickupAddr && parts[0]) pickupAddr = parts[0].trim();
                                if (!destAddr && parts[1]) destAddr = parts[1].trim();
                            }
                        }
                        if (cardPickup) cardPickup.textContent = pickupAddr || (pLat && pLon ? `${pLat.toFixed(5)}, ${pLon.toFixed(5)}` : '--');
                        if (cardDest) cardDest.textContent = destAddr || (xLat && xLon ? `${xLat.toFixed(5)}, ${xLon.toFixed(5)}` : '--');

                        const previewEta = document.getElementById('preview-eta');
                        const previewDistance = document.getElementById('preview-distance');
                        if (previewEta) previewEta.textContent = formattedEta;
                        if (previewDistance) previewDistance.textContent = formattedDistance;
                    } catch(e) { /* non-critical */ }

                    // Declare bookingCompleted outside try blocks so it's accessible in finally
                    let bookingCompleted = false;
                    try {
                        bookingCompleted = (info.booking_status === 'completed');
                    } catch(e) { /* ignore */ }

                    // Update driver info card visibility and contents
                    try {
                        const infoCard = document.getElementById('driver-info-card');
                        const bookingAccepted = (info.booking_status === 'accepted' || info.booking_status === 'on_the_way' || info.booking_status === 'started');
                        if (bookingAccepted) {
                            document.body.classList.add('booking-active');
                        } else {
                            document.body.classList.remove('booking-active');
                        }
                        if (infoCard) {
                            const previewCard = document.getElementById('booking-preview-card');
                            if (bookingAccepted) {
                                // hide the preview card when a driver has accepted (show driver info instead)
                                if (previewCard) { previewCard.style.display = 'none'; previewCard.setAttribute('aria-hidden','true'); }
                                const driverObj = info.driver || null; const tricycle = info.tricycle || {};
                                const driverName = (driverObj && driverObj.name) ? driverObj.name : (info.driver_name || 'Driver');
                                const driverPlate = (driverObj && driverObj.plate) ? driverObj.plate : (info.driver_plate || 'AB 1234');
                                const driverColor = tricycle.color || info.driver_color || 'Red';
                                infoCard.querySelector('.driver-name').textContent = driverName;
                                infoCard.querySelector('.driver-plate').textContent = `Plate: ${driverPlate}`;
                                infoCard.querySelector('.driver-color').textContent = `Color: ${driverColor}`;
                                const fareTarget = document.getElementById('active-card-fare');
                                if (fareTarget) {
                                    fareTarget.textContent = appliedFareText;
                                }
                                // Only show info card if chat is NOT open
                                if (!_chatModalIsOpen) {
                                    infoCard.style.display = 'block'; 
                                    infoCard.setAttribute('aria-hidden','false');
                                }
                            } else if (bookingCompleted) {
                                // Completed bookings should hide both active card and preview to avoid regression to pending state
                                infoCard.style.display = 'none';
                                infoCard.setAttribute('aria-hidden', 'true');
                                if (previewCard) {
                                    previewCard.style.display = 'none';
                                    previewCard.setAttribute('aria-hidden', 'true');
                                }
                                document.body.classList.remove('booking-active');
                            } else {
                                infoCard.style.display = 'none'; infoCard.setAttribute('aria-hidden','true');
                                if (previewCard && !_chatModalIsOpen) { previewCard.style.display = 'block'; previewCard.setAttribute('aria-hidden','false'); }
                            }
                        }
                    } catch(e) { console.warn('Driver card update failed', e); }

                    if (bookingCompleted) {
                        // For completed bookings, clear tracking and trigger a refresh so the payment status banner renders
                        currentTrackedBookingId = null;
                        if (trackingInterval) { clearInterval(trackingInterval); trackingInterval = null; }
                        // Remove any booking-item entries so UI does not revert to pending card
                        try {
                            const items = document.querySelectorAll(`.booking-item[data-booking-id="${bookingId}"]`);
                            items.forEach(el => el.parentNode && el.parentNode.removeChild(el));
                        } catch (e) { /* ignore */ }
                        // Allow existing notification toast to display before reload
                        setTimeout(() => {
                            if (!window._trikegoReloadedAfterCompletion) {
                                window._trikegoReloadedAfterCompletion = true;
                                window.location.reload();
                            }
                        }, 1200);
                    }

                    stageLoadedSuccessfully = true;
                } catch (err) {
                    console.error('Tracking error', err);
                    const indicator = document.getElementById('status-indicator'); if (indicator) { indicator.style.backgroundColor = '#dc3545'; }
                    if (loader) { loader.classList.add('hidden'); loader.setAttribute('aria-hidden','true'); }
                } finally {
                    if (stage && stageKey && stageLoadedSuccessfully) {
                        markRouteStageLoaded(bookingKey, stage);
                    }
                    if (loader) {
                        loader.classList.add('hidden');
                        loader.setAttribute('aria-hidden', 'true');
                    }
                }
            }

            function startTracking(bookingId) {
                        const trackingInfo = document.getElementById('tracking-info'); if (trackingInfo) trackingInfo.style.display = 'block';
                        currentTrackedBookingId = bookingId;
                        // Ensure UI reflects that a booking is now active: hide the booking form and preview card immediately
                        try {
                            document.body.classList.add('booking-active');
                            const bookingPanel = document.querySelector('.dashboard-booking-card');
                            if (bookingPanel) bookingPanel.style.display = 'none';
                            const previewCard = document.getElementById('booking-preview-card');
                            if (previewCard) { previewCard.style.display = 'none'; previewCard.setAttribute('aria-hidden','true'); }
                            const infoCard = document.getElementById('driver-info-card');
                            if (infoCard) { infoCard.style.display = 'block'; infoCard.setAttribute('aria-hidden','false'); }
                        } catch(e) { console.warn('startTracking UI update failed', e); }

                        // Do NOT reset the route stage here — loader should only show once when acceptance occurs
                        // resetRouteStage(bookingId, 'active');
                        updateAll(bookingId);
                        if (trackingInterval) clearInterval(trackingInterval);
                        // Poll less aggressively to avoid hitting ORS rate limits; update route every 12s
                        trackingInterval = setInterval(() => updateAll(bookingId), 12000);
            }

            // Booking preview and tracking boot
            try {
                const bookingItems = document.querySelectorAll('.booking-item');
                console.debug('Booking boot: found booking items count =', bookingItems.length);
                if (bookingItems.length > 0) {
                    // find pending preview booking or first non-pending target
                    let previewBooking = null; let target = null;
                    bookingItems.forEach(el => {
                        const statusRaw = (el.querySelector('.booking-status')?.textContent || '').trim();
                        const status = statusRaw.toLowerCase();
                        const hasDriverAssigned = !!el.dataset.bookingDriver;
                        // Determine preview: pending-like statuses without a driver assigned
                        if (!previewBooking && (status.includes('pending') || status === '' ) && !hasDriverAssigned) {
                            previewBooking = el;
                        }
                        // Determine target for tracking: prefer any booking that either has a driver assigned or shows accepted/on the way/started
                        if (!target) {
                            if (hasDriverAssigned) {
                                target = el;
                            } else if (status.includes('accept') || status.includes('on the way') || status.includes('started')) {
                                target = el;
                            }
                        }
                    });

                    if (!target) target = bookingItems[0];
                    console.debug('Booking boot: previewBooking=', previewBooking, 'target=', target);

                    // If there's an accepted/on_the_way booking, start full tracking
                    if (target) {
                        const bookingStatusRaw = (target.querySelector('.booking-status')?.textContent || '').trim();
                        const bookingStatus = bookingStatusRaw.toLowerCase();
                        const bookingId = target.dataset.bookingId;
                        const hasDriverAssigned = !!target.dataset.bookingDriver;
                        // If booking indicates driver assigned or status text suggests acceptance, start tracking
                        if (bookingId && (hasDriverAssigned || bookingStatus.includes('accept') || bookingStatus.includes('on the way') || bookingStatus.includes('started') )) {
                            // hide booking panel immediately and start tracking
                            try { document.body.classList.add('booking-active'); const bookingPanel = document.querySelector('.dashboard-booking-card'); if (bookingPanel) bookingPanel.style.display = 'none'; } catch(e){}
                            startTracking(bookingId);
                        } else if (bookingStatus.includes('completed')) {
                            // Completed booking without payment verification should hide preview and refresh to show payment banner
                            try {
                                const previewCard = document.getElementById('booking-preview-card');
                                if (previewCard) { previewCard.style.display = 'none'; previewCard.setAttribute('aria-hidden','true'); }
                                document.body.classList.remove('booking-active');
                            } catch (e) { /* ignore */ }
                        } else if (previewBooking) {
                            // show preview card
                            const bookingId = previewBooking.dataset.bookingId;
                            const pickupText = previewBooking.querySelector('strong')?.textContent?.trim() || '--';
                            const destText = previewBooking.childNodes[2]?.textContent?.trim() || '--';
                            const previewCard = document.getElementById('booking-preview-card');
                            const previewPickup = document.getElementById('preview-pickup');
                            const previewDest = document.getElementById('preview-dest');
                            const previewFare = document.getElementById('preview-fare');
                            if (previewPickup) previewPickup.textContent = pickupText; if (previewDest) previewDest.textContent = destText; if (previewFare) previewFare.textContent = 'Estimating...';
                            const previewForm = document.getElementById('preview-cancel-form'); if (previewForm) {
                                const tpl = (window.PASSENGER_DASH_CONFIG && window.PASSENGER_DASH_CONFIG.cancelBookingUrlTemplate) || previewForm.getAttribute('data-cancel-template') || previewForm.action || '';
                                if (tpl && tpl.indexOf('/0/') !== -1) {
                                    previewForm.action = tpl.replace('/0/', `/${bookingId}/`);
                                } else if (tpl) {
                                    // fallback: append id
                                    previewForm.action = tpl.replace(/\/$/, '') + `/${bookingId}/`;
                                }
                            }
                            if (previewCard) { previewCard.style.display = 'block'; previewCard.setAttribute('aria-hidden','false'); }
                            // hide booking panel
                            try { document.body.classList.add('booking-active'); const bookingPanel = document.querySelector('.dashboard-booking-card'); if (bookingPanel) bookingPanel.style.display = 'none'; } catch(e){}
                            // draw preview route once
                            resetRouteStage(bookingId, 'preview');
                            try { updateAll(bookingId); } catch(e){}
                        }
                    }
                }
            } catch(e) { console.warn('Booking boot failed', e); }

            // Automatic refresh: poll booking items for status/assignment changes so passenger doesn't need to refresh
            try {
                async function pollBookingItems() {
                    try {
                        const items = document.querySelectorAll('.booking-item');
                        if (!items || items.length === 0) return;
                        for (const el of items) {
                            const bid = el.dataset.bookingId;
                            if (!bid) continue;
                            try {
                                const infoRes = await fetch(`/api/booking/${bid}/route_info/`);
                                if (!infoRes.ok) continue;
                                const info = await infoRes.json();
                                if (info.status !== 'success') continue;
                                // update dataset for driver assignment
                                if (info.driver && info.driver.id) {
                                    if (!el.dataset.bookingDriver) el.dataset.bookingDriver = info.driver.id;
                                }
                                // update display text if addresses differ
                                const pickupEl = el.querySelector('strong');
                                const destText = el.childNodes[2] && el.childNodes[2].textContent ? el.childNodes[2].textContent.trim() : null;
                                if (pickupEl && info.pickup_address && pickupEl.textContent.trim() !== info.pickup_address) pickupEl.textContent = info.pickup_address;
                                if (destText && info.destination_address && destText !== info.destination_address) {
                                    // replace the arrow content after strong
                                    // simple approach: set innerHTML to pickup → destination + small est arrival if present
                                    let html = `<strong>${info.pickup_address || (pickupEl?pickupEl.textContent:'--')}</strong> → ${info.destination_address || '--'}`;
                                    if (info.estimated_arrival) html += `<br><small>Est. Arrival: ${new Date(info.estimated_arrival).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</small>`;
                                    el.innerHTML = html;
                                }
                                // if booking now accepted/on_the_way/started and we're not already tracking it, start tracking
                                const bookingStatus = (info.booking_status || '').toLowerCase();
                                if ((bookingStatus.includes('accept') || bookingStatus.includes('on the way') || bookingStatus.includes('started')) && (!currentTrackedBookingId || currentTrackedBookingId !== String(bid))) {
                                    // start tracking this booking
                                    try { startTracking(bid); } catch(e){}
                                } else if (bookingStatus.includes('completed')) {
                                    // Completed bookings should no longer appear in pending list
                                    try { el.parentNode && el.parentNode.removeChild(el); } catch (e) { /* ignore */ }
                                    if (!window._trikegoReloadedAfterCompletion) {
                                        window._trikegoReloadedAfterCompletion = true;
                                        setTimeout(() => window.location.reload(), 1200);
                                    }
                                }
                            } catch(e) { /* ignore per-item errors */ }
                        }
                    } catch(e) { console.warn('pollBookingItems failed', e); }
                }
                // Run immediately and then periodically (reduced frequency to lower load)
                pollBookingItems();
                setInterval(pollBookingItems, 10000);
            } catch(e) { /* non-critical */ }

            // Wire Chat button in driver-info-card to open chat for current tracked booking
            try {
                const chatBtn = document.getElementById('msg-driver-btn');
                if (chatBtn) {
                    chatBtn.addEventListener('click', (ev) => {
                        ev.preventDefault();
                        // prefer explicit currentTrackedBookingId, else fall back to any booking-item with driver
                        let bid = currentTrackedBookingId || null;
                        if (!bid) {
                            const assigned = document.querySelector('.booking-item[data-booking-driver]');
                            if (assigned) bid = assigned.dataset.bookingId;
                        }
                        if (!bid) {
                            alert('No active booking found to start chat.');
                            return;
                        }
                        if (typeof window.openChatModal === 'function') {
                            window.openChatModal(bid);
                        } else {
                            console.warn('openChatModal is not available yet');
                        }
                    });
                }
            } catch (e) { console.warn('Chat button wiring failed', e); }
            // Ensure the booking form's submit button shows loading so the user
            // knows the request is in progress (prevents accidental double
            // submissions and avoids the button reverting to text before the
            // server/UI update is reflected).
            try {
                const bookingForm = document.querySelector('.booking-form');
                if (bookingForm) {
                    bookingForm.addEventListener('submit', function (ev) {
                        // find the primary submit button inside the form
                        const submitBtn = bookingForm.querySelector('button[type="submit"]');
                        if (!submitBtn) return;
                        try {
                            if (window.singleClickHelper && typeof window.singleClickHelper.setLoading === 'function') {
                                window.singleClickHelper.setLoading(submitBtn);
                                // If the form ultimately does not cause navigation (e.g.
                                // server returns the same page with errors), clear the
                                // loading state after a reasonable timeout so the UI
                                // doesn't remain stuck permanently.
                                setTimeout(() => {
                                    try { if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') window.singleClickHelper.clearLoading(submitBtn); } catch (e) {}
                                }, 30000);
                            } else {
                                submitBtn.disabled = true;
                            }
                        } catch (e) {
                            submitBtn.disabled = true;
                        }
                    });
                }
            } catch (e) { /* non-critical */ }
})();
