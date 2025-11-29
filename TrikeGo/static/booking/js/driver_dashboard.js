// Driver dashboard JS (moved from template)
(function(){
    // Ensure a placeholder exists so inline onclicks don't fail if the DOMContentLoaded handler
    // hasn't run yet or initialization is delayed. Clicks will be queued and processed later.
    if (!window.reviewBooking) {
        window._queuedReviewCalls = window._queuedReviewCalls || [];
        window.reviewBooking = function(bid) {
            console.log('reviewBooking not available yet, queuing', bid);
            window._queuedReviewCalls.push(bid);
        };
    }
    const cfg = window.DRIVER_DASH_CONFIG || {};
    const ORS_API_KEY = cfg.ORS_API_KEY || '';
    const userId = cfg.userId || null;
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const driverAvailability = {
        status: 'Offline',
        busy: false,
        button: null,
        label: null,
        control: null,
        map: null,
        marker: null,
        pendingLocation: null,
        shouldCenterNext: false,
        hasActiveTrip: Boolean(cfg.hasActiveTrip),
    };

    function normalizeDriverStatus(value) {
        if (value === 'Online' || value === 'Offline' || value === 'In_trip') {
            return value;
        }
        return 'Offline';
    }

    function driverStatusLabel(value) {
        if (value === 'In_trip') {
            return 'In trip';
        }
        return value || 'Offline';
    }

    function setDriverAvailabilityUI() {
        if (!driverAvailability.button || !driverAvailability.label) {
            return;
        }
        const status = driverAvailability.status;
        const label = driverStatusLabel(status);
        driverAvailability.label.textContent = label;
        const actionHint = status === 'Online' ? 'Go offline' : (status === 'Offline' ? 'Go online' : 'Trip in progress');
        driverAvailability.button.setAttribute('aria-pressed', status === 'Online' ? 'true' : 'false');
        driverAvailability.button.setAttribute('aria-label', `${label}. ${actionHint}.`);
        driverAvailability.button.classList.toggle('is-online', status === 'Online');
        driverAvailability.button.classList.toggle('is-offline', status === 'Offline');
        driverAvailability.button.classList.toggle('is-intrip', status === 'In_trip');
        driverAvailability.button.classList.toggle('is-busy', driverAvailability.busy);
        driverAvailability.button.disabled = driverAvailability.busy || status === 'In_trip';
        if (driverAvailability.control) {
            driverAvailability.control.classList.toggle('is-online', status === 'Online');
            driverAvailability.control.classList.toggle('is-offline', status === 'Offline');
            driverAvailability.control.classList.toggle('is-intrip', status === 'In_trip');
        }
    }

    function clearDriverAvailabilityMarker() {
        driverAvailability.pendingLocation = null;
        if (driverAvailability.marker && driverAvailability.map) {
            try {
                driverAvailability.map.removeLayer(driverAvailability.marker);
            } catch (err) {
                console.warn('Availability marker removal failed', err);
            }
        }
        driverAvailability.marker = null;
    }

    function clearDriverReviewOverlays() {
        const map = window.DRIVER_MAP;
        const refs = [
            '_driverReviewLayer',
            '_driverReviewDriverToPickupLayer',
            '_driverReviewDriverMarker',
            '_driverReviewPickupMarker',
            '_driverReviewDestMarker',
        ];
        refs.forEach((ref) => {
            const layer = window[ref];
            if (!layer) {
                window[ref] = null;
                return;
            }
            try {
                if (map && typeof map.removeLayer === 'function') {
                    map.removeLayer(layer);
                } else if (layer.remove) {
                    layer.remove();
                }
            } catch (err) {
                console.warn('Failed to remove review overlay', ref, err);
            }
            window[ref] = null;
        });
    }
    window.clearDriverReviewOverlays = clearDriverReviewOverlays;

    function ensureDriverAvailabilityMarker(location) {
        if (!location) {
            return;
        }
        const lat = Number(location.lat ?? location.latitude);
        const lon = Number(location.lon ?? location.longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
            return;
        }
        driverAvailability.pendingLocation = { lat, lon };
        if (!driverAvailability.map || typeof L === 'undefined') {
            return;
        }
        if (!driverAvailability.marker) {
            try {
                const icon = L.divIcon({
                    className: 'driver-marker driver-availability-marker',
                    html: '<div class="marker-inner"></div>',
                    iconSize: [30, 30]
                });
                driverAvailability.marker = L.marker([lat, lon], { icon }).addTo(driverAvailability.map).bindPopup('You are here');
            } catch (err) {
                console.warn('Availability marker init failed', err);
                return;
            }
        } else {
            try {
                driverAvailability.marker.setLatLng([lat, lon]);
            } catch (err) {
                console.warn('Availability marker update failed', err);
            }
        }
        if (driverAvailability.shouldCenterNext) {
            try {
                const currentZoom = driverAvailability.map.getZoom();
                driverAvailability.map.setView([lat, lon], currentZoom < 14 ? 14 : currentZoom);
            } catch (err) {
                console.warn('Availability auto-center failed', err);
            }
            driverAvailability.shouldCenterNext = false;
        }
    }

    function applyDriverAvailabilityBehavior(status) {
        const isOnline = status === 'Online';
        driverAvailability.shouldCenterNext = isOnline;

        if (isOnline) {
            if (typeof window.startLocationTracking === 'function') {
                window.startLocationTracking(false);
            }
            if (driverAvailability.pendingLocation) {
                ensureDriverAvailabilityMarker(driverAvailability.pendingLocation);
            }
            return;
        }

        clearDriverAvailabilityMarker();
        if (status === 'Offline' && typeof window.stopLocationTracking === 'function') {
            window.stopLocationTracking();
        }
    }

    function setDriverAvailabilityStatus(newStatus, options = {}) {
        const normalized = normalizeDriverStatus(newStatus);
        const previous = driverAvailability.status;
        driverAvailability.status = normalized;
        if (window.console && typeof console.log === 'function') {
            console.log('[driver-availability] status update', {
                previous,
                next: normalized,
                forced: Boolean(options.force),
            });
        }
        setDriverAvailabilityUI();
        if (options.force || previous !== normalized) {
            applyDriverAvailabilityBehavior(normalized);
        }
    }

    function setDriverAvailabilityBusy(flag) {
        driverAvailability.busy = Boolean(flag);
        setDriverAvailabilityUI();
    }

    async function postDriverAvailability(nextStatus) {
        if (!cfg.driverStatusEndpoint) {
            return;
        }
        setDriverAvailabilityBusy(true);
            const csrf = getCookie('csrftoken');
        if (!csrf) {
            console.warn('Driver status update missing CSRF token; request may be rejected.');
        }
        if (window.console && typeof console.log === 'function') {
            console.log('[driver-availability] posting update', { nextStatus, csrfPresent: Boolean(csrf) });
        }
        try {
            const response = await fetch(cfg.driverStatusEndpoint, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf || '',
                    'Accept': 'application/json',
                },
                body: JSON.stringify({ status: nextStatus })
            });
            const payload = await response.json().catch(() => null);
            if (window.console && typeof console.log === 'function') {
                console.log('[driver-availability] server response', { status: response.status, payload });
            }
            if (!response.ok || !payload || payload.status !== 'success') {
                const message = payload && payload.message ? payload.message : 'Unable to update availability.';
                throw new Error(message);
            }
            const resolvedStatus = payload.driverStatus || nextStatus;
            setDriverAvailabilityStatus(resolvedStatus, { force: true });
            if (payload && Object.prototype.hasOwnProperty.call(payload, 'hasActiveTrip')) {
                driverAvailability.hasActiveTrip = Boolean(payload.hasActiveTrip);
            }
            if (payload.currentLocation) {
                driverAvailability.pendingLocation = payload.currentLocation;
                if (driverAvailability.status === 'Online') {
                    ensureDriverAvailabilityMarker(payload.currentLocation);
                }
            }
        } catch (err) {
            alert(err.message || 'Unable to update availability.');
        } finally {
            setDriverAvailabilityBusy(false);
        }
    }

    async function refreshDriverAvailabilityFromServer() {
        if (!cfg.driverStatusEndpoint) {
            return;
        }
        try {
            const response = await fetch(cfg.driverStatusEndpoint, {
                credentials: 'same-origin',
                headers: {
                    'Accept': 'application/json',
                },
            });
            if (window.console && typeof console.log === 'function') {
                console.log('[driver-availability] refresh response status', response.status);
            }
            if (!response.ok) {
                return;
            }
            const payload = await response.json().catch(() => null);
            if (window.console && typeof console.log === 'function') {
                console.log('[driver-availability] refresh payload', payload);
            }
            if (!payload) {
                return;
            }
            if (Object.prototype.hasOwnProperty.call(payload, 'hasActiveTrip')) {
                driverAvailability.hasActiveTrip = Boolean(payload.hasActiveTrip);
            }
            if (payload.driverStatus) {
                setDriverAvailabilityStatus(payload.driverStatus, { force: false });
            }
            if (payload.currentLocation) {
                driverAvailability.pendingLocation = payload.currentLocation;
                if (driverAvailability.status === 'Online') {
                    ensureDriverAvailabilityMarker(payload.currentLocation);
                }
            }
        } catch (err) {
            console.warn('Driver availability refresh failed', err);
        }
    }

    function handleDriverAvailabilityToggle(event) {
        if (event) {
            event.preventDefault();
        }
        if (driverAvailability.busy || driverAvailability.status === 'In_trip') {
            if (window.console && typeof console.log === 'function') {
                console.log('[driver-availability] click ignored', {
                    busy: driverAvailability.busy,
                    status: driverAvailability.status,
                    hasActiveTrip: driverAvailability.hasActiveTrip,
                });
            }
            return;
        }
        if (window.console && typeof console.log === 'function') {
            console.log('[driver-availability] toggle clicked', {
                currentStatus: driverAvailability.status,
                hasActiveTrip: driverAvailability.hasActiveTrip,
            });
        }
        const nextStatus = driverAvailability.status === 'Online' ? 'Offline' : 'Online';
        postDriverAvailability(nextStatus);
    }

    function bindDriverAvailabilityControls() {
        driverAvailability.button = document.getElementById('driver-availability-toggle');
        driverAvailability.label = document.getElementById('driver-availability-status');
        driverAvailability.control = document.getElementById('driver-availability-control');
        if (driverAvailability.button) {
            driverAvailability.button.addEventListener('click', handleDriverAvailabilityToggle);
        }
        let initialStatus = normalizeDriverStatus(cfg.driverStatus || 'Offline');
        driverAvailability.hasActiveTrip = Boolean(cfg.hasActiveTrip);
        if (initialStatus === 'Offline' && driverAvailability.hasActiveTrip) {
            initialStatus = 'In_trip';
        }
    setDriverAvailabilityStatus(initialStatus, { force: initialStatus === 'Online' });
        setDriverAvailabilityUI();
        if (cfg.driverStatusEndpoint) {
            refreshDriverAvailabilityFromServer();
        }
    }

    document.addEventListener('DOMContentLoaded', bindDriverAvailabilityControls);
    document.addEventListener('driver:mapReady', function(event) {
        driverAvailability.map = (event && event.detail && event.detail.map) ? event.detail.map : window.DRIVER_MAP;
        if (driverAvailability.status === 'Online' && driverAvailability.pendingLocation) {
            ensureDriverAvailabilityMarker(driverAvailability.pendingLocation);
        }
    });
    document.addEventListener('driver:rideAccepted', function() {
        refreshDriverAvailabilityFromServer();
    });
    document.addEventListener('driver:rideCancelled', function() {
        refreshDriverAvailabilityFromServer();
    });

    window.updateDriverAvailabilityUI = function(status, options) {
        const normalized = normalizeDriverStatus(status);
        const force = options && options.force;
        setDriverAvailabilityStatus(normalized, { force: Boolean(force) });
    };
    window.updateDriverAvailabilityMarker = function(location) {
        if (!location) {
            clearDriverAvailabilityMarker();
            return;
        }
        if (driverAvailability.status !== 'Online') {
            driverAvailability.pendingLocation = location;
            return;
        }
        ensureDriverAvailabilityMarker(location);
    };
    window.refreshDriverAvailability = refreshDriverAvailabilityFromServer;
    window.driverAvailabilityState = driverAvailability;

    // Helper: escape HTML
    function escapeHtml(str) {
        return String(str).replace(/[&<>"']/g, function (s) {
            return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[s];
        });
    }
    
        function formatKilometers(km) {
            if (!Number.isFinite(km) || km <= 0) {
                return null;
            }
            if (km >= 100) {
                return `${km.toFixed(0)} km`;
            }
            if (km >= 10) {
                return `${km.toFixed(1)} km`;
            }
            return `${km.toFixed(2)} km`;
        }
    
        function formatEtaMinutes(minutes) {
            if (!Number.isFinite(minutes)) {
                return null;
            }
            const rounded = Math.max(0, Math.round(minutes));
            return `ETA ~${rounded} min`;
        }
    
        function secondsToMinutes(seconds) {
            if (!Number.isFinite(seconds) || seconds < 0) {
                return null;
            }
            if (seconds === 0) {
                return 0;
            }
            return Math.ceil(seconds / 60);
        }

        const driverRidesState = {
            signature: null,
            refreshing: false,
            timerId: null,
        };

        function buildAcceptRideUrl(bookingId) {
            const id = String(bookingId);
            const tpl = cfg.acceptRideUrlTemplate || '';
            if (!tpl) {
                return `/drivers/booking/${id}/accept/`;
            }
            if (tpl.indexOf('/0/') !== -1) {
                return tpl.replace('/0/', `/${id}/`);
            }
            if (tpl.endsWith('0')) {
                return tpl.slice(0, -1) + id;
            }
            return tpl.replace('0', id);
        }

        function computeAvailableRidesSignature(rides) {
            if (!Array.isArray(rides)) {
                return '[]';
            }
            return rides.map((ride) => {
                const updated = ride.updated_at || ride.booking_time || '';
                return `${ride.id || ''}:${ride.status || ''}:${updated}`;
            }).join('|');
        }

        function renderAvailableRidesList(rides) {
            const container = document.getElementById('rides-panel-list');
            if (!container) {
                return;
            }
            if (!Array.isArray(rides) || rides.length === 0) {
                container.innerHTML = '<p class="driver-rides-panel__empty">No rides are available right now. Check back soon.</p>';
                return;
            }

            const fragment = document.createDocumentFragment();
            rides.forEach((ride) => {
                const card = document.createElement('div');
                card.className = 'driver-ride-card';
                card.setAttribute('data-booking-id', ride.id);

                const passengerName = ride.passenger_name || 'Passenger';
                const passengers = Number(ride.passengers || 1);
                const seatsLabel = passengers === 1 ? '1 passenger' : `${passengers} passengers`;
                const fareDisplay = ride.fare_display || (Number.isFinite(ride.fare) ? `₱${Number(ride.fare).toFixed(2)}` : 'Fare pending');
                const pickup = ride.pickup_address || '—';
                const destination = ride.destination_address || '—';

                const distanceVal = Number(ride.estimated_distance_km ?? ride.estimated_distance ?? NaN);
                const durationVal = Number(ride.estimated_duration_min ?? ride.estimated_duration ?? NaN);
                const distanceLabel = Number.isFinite(distanceVal) ? `Distance: ${distanceVal.toFixed(distanceVal >= 10 ? 1 : 2)} km` : '';
                const etaLabel = Number.isFinite(durationVal) ? `ETA: ~${Math.max(1, Math.round(durationVal))} mins` : '';
                const metaPieces = [distanceLabel, etaLabel].filter(Boolean);

                const acceptUrl = buildAcceptRideUrl(ride.id);
                const csrfToken = cfg.csrfToken || '';

                card.innerHTML = `
                    <div class="driver-ride-card__top">
                        <div>
                            <span class="driver-ride-card__passenger">${escapeHtml(passengerName)}</span>
                            <span class="driver-ride-card__seats">${escapeHtml(seatsLabel)}</span>
                        </div>
                        <div class="driver-ride-card__fare">
                            <span class="driver-ride-card__fare-amount${fareDisplay === 'Fare pending' ? ' driver-ride-card__fare-amount--pending' : ''}">${escapeHtml(fareDisplay)}</span>
                        </div>
                    </div>
                    <div class="driver-ride-card__route">
                        <div class="driver-ride-card__route-item">
                            <span class="driver-ride-card__label">from:</span>
                            <span class="driver-ride-card__value">${escapeHtml(pickup)}</span>
                        </div>
                        <div class="driver-ride-card__route-item">
                            <span class="driver-ride-card__label">to:</span>
                            <span class="driver-ride-card__value">${escapeHtml(destination)}</span>
                        </div>
                    </div>
                    ${metaPieces.length ? `<div class="driver-ride-card__meta">${metaPieces.map((txt) => `<span class="driver-ride-card__meta-text">${escapeHtml(txt)}</span>`).join('')}</div>` : ''}
                    <div class="driver-ride-card__actions">
                        <button class="btn btn-secondary review-ride-btn" data-booking-id="${escapeHtml(String(ride.id))}">Review</button>
                        <form class="accept-ride-form" data-booking-id="${escapeHtml(String(ride.id))}" method="POST" action="${escapeHtml(acceptUrl)}">
                            <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}" />
                            <button type="submit" class="btn btn-success" data-role="accept-submit">Accept</button>
                        </form>
                    </div>
                `;
                fragment.appendChild(card);
            });

            container.innerHTML = '';
            container.appendChild(fragment);
        }

        async function refreshAvailableRidesList(immediate = false) {
            if (!cfg.availableRidesEndpoint || driverRidesState.refreshing) {
                if (!cfg.availableRidesEndpoint) {
                    console.warn('Available rides endpoint not configured; skipping poll');
                }
                return;
            }
            driverRidesState.refreshing = true;
            try {
                const response = await fetch(cfg.availableRidesEndpoint + (immediate ? '?t=' + Date.now() : ''), { credentials: 'same-origin' });
                if (!response.ok) {
                    console.warn('Available rides fetch failed:', response.status, response.statusText);
                    return;
                }
                const payload = await response.json();
                if (!payload || payload.status !== 'success' || !Array.isArray(payload.rides)) {
                    console.warn('Available rides response invalid:', payload);
                    return;
                }
                const signature = computeAvailableRidesSignature(payload.rides);
                if (signature !== driverRidesState.signature) {
                    console.debug('Available rides updated:', payload.rides.length, 'rides');
                    driverRidesState.signature = signature;
                    renderAvailableRidesList(payload.rides);
                }
            } catch (err) {
                console.warn('Available rides refresh failed', err);
            } finally {
                driverRidesState.refreshing = false;
            }
        }

        function startAvailableRidesPolling() {
            if (!cfg.availableRidesEndpoint) {
                console.warn('Cannot start available rides polling: endpoint not configured');
                return;
            }
            console.debug('Starting available rides polling, endpoint:', cfg.availableRidesEndpoint);
            refreshAvailableRidesList(true);
            if (driverRidesState.timerId) {
                clearInterval(driverRidesState.timerId);
            }
            driverRidesState.timerId = setInterval(() => refreshAvailableRidesList(false), 7000);
        }

    // ---- Multi-stop itinerary state management ----
    let itineraryData = null;
    let currentStopIndex = 0;
    let itineraryExpanded = false;
    let itineraryTimer = null;
    let itineraryMarkers = [];
    let itineraryRouteLayer = null;
    let itineraryRouteSignature = null;
    let itineraryRouteIsFallback = false;
    let itineraryRouteRequestId = 0;
    let itineraryRoutePaneCache = {};
    let itineraryDom = {};
    let mapInstance = null;
    let routeLoaderDepth = 0;
    let itineraryHasLoaded = false;
    let lastRouteLoaderHiddenAt = performance.now();

    function updateRouteLoaderVisibility() {
        const loaderEl = document.getElementById('driver-route-loader');
        if (!loaderEl) {
            return;
        }
        if (routeLoaderDepth > 0) {
            loaderEl.classList.remove('hidden');
            loaderEl.setAttribute('aria-hidden', 'false');
        } else {
            loaderEl.classList.add('hidden');
            loaderEl.setAttribute('aria-hidden', 'true');
        }
    }
    async function handleAcceptRide(form) {
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            try {
                if (window.singleClickHelper && typeof window.singleClickHelper.setLoading === 'function') {
                    window.singleClickHelper.setLoading(submitBtn);
                } else {
                    submitBtn.disabled = true;
                }
            } catch (e) { submitBtn.disabled = true; }
        }

        const csrf = cfg.csrfToken || (function getCSRFTokenFromCookie() {
            const name = 'csrftoken';
            if (!document.cookie) return null;
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i += 1) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    return decodeURIComponent(cookie.substring(name.length + 1));
                }
            }
            return null;
        })();

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': csrf || '',
                    'Accept': 'application/json'
                },
                body: new URLSearchParams(new FormData(form))
            });

            const raw = await response.text();
            let payload = null;
            if (raw) {
                try {
                    payload = JSON.parse(raw);
                } catch (parseErr) {
                    console.warn('accept payload parse failed', parseErr);
                }
            }

            if (!response.ok || !payload || payload.status !== 'success') {
                const errMsg = payload && payload.message ? payload.message : (response.statusText || 'Unable to accept ride');
                alert('Accept failed: ' + errMsg);
                if (submitBtn) submitBtn.disabled = false;
                return;
            }

            const rideCard = form.closest('.driver-ride-card');
            if (rideCard) {
                rideCard.classList.add('driver-ride-card--accepted');
                const notice = document.createElement('p');
                notice.className = 'driver-ride-card__meta-text driver-ride-card__meta-text--success';
                notice.textContent = 'Ride accepted! Updating itinerary…';
                rideCard.appendChild(notice);
                setTimeout(() => {
                    if (rideCard.parentElement) {
                        rideCard.remove();
                    }
                }, 1200);
            }

            try {
                if (typeof window.clearDriverReviewOverlays === 'function') {
                    window.clearDriverReviewOverlays();
                }
            } catch (overlayErr) {
                console.warn('Unable to clear preview overlays after accept', overlayErr);
            }

            document.dispatchEvent(new CustomEvent('driver:rideAccepted', { detail: payload.booking }));
            if (typeof window.refreshDriverAvailability === 'function') {
                try {
                    window.refreshDriverAvailability();
                } catch (err) {
                    console.warn('Driver availability refresh failed after accept', err);
                }
            }

            try {
                if (typeof fetchItineraryData === 'function') {
                    itineraryHasLoaded = false;
                    await fetchItineraryData({ forceLoader: true });
                }
            } catch (err) {
                console.warn('Unable to refresh itinerary after accept', err);
            }

            try {
                if (typeof window.closeDriverRidesPanel === 'function') {
                    window.closeDriverRidesPanel();
                } else {
                    const panel = document.getElementById('driver-rides-panel');
                    if (panel) panel.setAttribute('aria-hidden', 'true');
                    const sidebar = document.querySelector('.sidebar');
                    if (sidebar) sidebar.setAttribute('aria-expanded', 'false');
                }
            } catch (panelErr) {
                console.warn('Unable to close rides panel after accept', panelErr);
            }

            if (submitBtn) {
                try { submitBtn.dispatchEvent(new CustomEvent('single-click-success', { bubbles: true })); } catch (e) {}
                try {
                    if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') {
                        window.singleClickHelper.clearLoading(submitBtn);
                        submitBtn.dataset.processing = 'false';
                    } else {
                        submitBtn.disabled = false;
                    }
                } catch (e) { try { submitBtn.disabled = false; } catch (e) {} }
            }
        } catch (err) {
            console.warn('Accept request failed', err);
            if (submitBtn) {
                try { submitBtn.dispatchEvent(new CustomEvent('single-click-error', { bubbles: true })); } catch (e) {}
                try {
                    if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') {
                        window.singleClickHelper.clearLoading(submitBtn);
                        submitBtn.dataset.processing = 'false';
                    } else {
                        submitBtn.disabled = false;
                    }
                } catch (e) { try { submitBtn.disabled = false; } catch (e) {} }
            }
            alert('Network error while accepting ride.');
        }
    }

    function showRouteLoader(force = false) {
        if (!force && itineraryHasLoaded) {
            return;
        }
        const now = performance.now();
        const sinceHide = now - lastRouteLoaderHiddenAt;
        const allowImmediate = force || (!itineraryHasLoaded && routeLoaderDepth === 0);
        if (allowImmediate || routeLoaderDepth > 0 || sinceHide > 300) {
            routeLoaderDepth += 1;
            updateRouteLoaderVisibility();
        }
    }

    function hideRouteLoader() {
        if (routeLoaderDepth > 0) {
            routeLoaderDepth -= 1;
            updateRouteLoaderVisibility();
        }
        if (routeLoaderDepth === 0) {
            lastRouteLoaderHiddenAt = performance.now();
        }
    }

    function getTripBookingIds() {
        if (!itineraryData || !Array.isArray(itineraryData.stops)) return [];
        const idSet = new Set();
        itineraryData.stops.forEach(stop => {
            if (stop && stop.bookingId) {
                idSet.add(stop.bookingId);
            }
        });
        return Array.from(idSet);
    }

    function getPreferredChatBookingId() {
        const bookingIds = getTripBookingIds();
        if (!bookingIds.length) {
            return null;
        }
        if (itineraryData && Array.isArray(itineraryData.stops) && itineraryData.stops[currentStopIndex]) {
            return itineraryData.stops[currentStopIndex].bookingId || bookingIds[0];
        }
        return bookingIds[0];
    }

    function updateTrackingState() {
        const hasStops = itineraryData && Array.isArray(itineraryData.stops) && itineraryData.stops.length > 0;
        if (hasStops) {
            document.body.setAttribute('data-has-itinerary', 'true');
            if (typeof window.startLocationTracking === 'function') {
                window.startLocationTracking(false);
            }
        } else {
            document.body.removeAttribute('data-has-itinerary');
            if (typeof window.stopLocationTracking === 'function') {
                window.stopLocationTracking();
            }
        }
    }

    function initItinerary(map) {
        mapInstance = map;
        itineraryRoutePaneCache = {};
        itineraryDom = {
            card: document.getElementById('itinerary-card'),
            summaryStatusText: document.getElementById('summary-status-text'),
            summaryActionType: document.getElementById('summary-action-type'),
            summaryAddress: document.getElementById('summary-address'),
            summaryMeta: document.getElementById('summary-meta'),
            summaryActionBtn: document.getElementById('summary-action-btn'),
            summaryStopNum: document.getElementById('summary-stop-num'),
            summaryStopTotal: document.getElementById('summary-stop-total'),
            summaryCapacity: document.getElementById('summary-capacity'),
            expandBtn: document.getElementById('itinerary-expand-btn'),
            collapseBtn: document.getElementById('itinerary-collapse-btn'),
            fullBookingCount: document.getElementById('full-booking-count'),
            fullCapacity: document.getElementById('full-capacity'),
            fullEarnings: document.getElementById('full-earnings'),
            bookingsContainer: document.getElementById('itinerary-bookings'),
            stopList: document.getElementById('itinerary-stop-list'),
            summaryContainer: document.getElementById('itinerary-summary'),
            fullContainer: document.getElementById('itinerary-full'),
            chatBtn: document.getElementById('open-chat-btn'),
        };

        if (!itineraryDom.card) {
            return;
        }

        itineraryExpanded = false;
        itineraryDom.card.classList.add('collapsed');

        if (itineraryDom.expandBtn) {
            itineraryDom.expandBtn.addEventListener('click', () => toggleItinerary());
        }
        if (itineraryDom.collapseBtn) {
            itineraryDom.collapseBtn.addEventListener('click', () => toggleItinerary(false));
        }
        if (itineraryDom.summaryActionBtn) {
            itineraryDom.summaryActionBtn.addEventListener('click', handleSummaryActionClick);
        }
        if (itineraryDom.chatBtn) {
            itineraryDom.chatBtn.addEventListener('click', openTripChatFromUI);
        }

        fetchItineraryData();
        itineraryTimer = setInterval(fetchItineraryData, 12000);
    }

    function toggleItinerary(expand) {
        if (!itineraryDom.card) return;
        if (typeof expand === 'undefined') {
            itineraryExpanded = !itineraryExpanded;
        } else {
            itineraryExpanded = !!expand;
        }
        itineraryDom.card.classList.toggle('expanded', itineraryExpanded);
        itineraryDom.card.classList.toggle('collapsed', !itineraryExpanded);
        if (itineraryDom.fullContainer) {
            itineraryDom.fullContainer.style.display = itineraryExpanded ? 'block' : 'none';
        }
        if (itineraryDom.expandBtn) {
            itineraryDom.expandBtn.textContent = itineraryExpanded ? 'Close Itinerary' : 'View Full Itinerary';
            itineraryDom.expandBtn.setAttribute('aria-expanded', itineraryExpanded ? 'true' : 'false');
        }
    }

    function clearItineraryMarkers() {
        if (!mapInstance) return;
        itineraryMarkers.forEach(marker => {
            try { mapInstance.removeLayer(marker); } catch (err) { /* ignore */ }
        });
        itineraryMarkers = [];
    }

    function resetItineraryRoute() {
        if (!mapInstance) {
            itineraryRouteLayer = null;
            itineraryRouteSignature = null;
            return;
        }
        if (itineraryRouteLayer && mapInstance.hasLayer(itineraryRouteLayer)) {
            try { mapInstance.removeLayer(itineraryRouteLayer); } catch (err) { /* ignore */ }
        }
        itineraryRouteLayer = null;
        itineraryRouteSignature = null;
        itineraryRouteIsFallback = false;
    }

    function clearItineraryMapLayers() {
        clearItineraryMarkers();
        resetItineraryRoute();
    }

    function getStopActionLabel(stop) {
        if (!stop) return 'Proceed';
        if (stop.type === 'PICKUP') {
            return stop.status === 'CURRENT' ? 'Start Pickup' : 'Queue Pickup';
        }
        return stop.status === 'CURRENT' ? 'Confirm Drop-off' : 'Queue Drop-off';
    }

    function buildStopStatusClass(status) {
        if (status === 'COMPLETED') return 'completed';
        if (status === 'CURRENT') return 'current';
        return 'pending';
    }

    function formatStatusLabel(status) {
        switch ((status || 'UPCOMING').toUpperCase()) {
            case 'COMPLETED':
                return 'Completed';
            case 'CURRENT':
                return 'Current';
            default:
                return 'Upcoming';
        }
    }

    function renderStopList(stops) {
        if (!itineraryDom.stopList) return;
        itineraryDom.stopList.innerHTML = '';

        const fragment = document.createDocumentFragment();
        stops.forEach((stop, index) => {
            const li = document.createElement('li');
            li.className = `stop-item ${buildStopStatusClass(stop.status)}`;

            const typeLabel = stop.type === 'PICKUP' ? 'Pick Up' : 'Drop Off';
            const badgeClass = stop.type === 'PICKUP' ? '' : 'dropoff';
            const statusClass = stop.status ? stop.status.toLowerCase() : 'upcoming';
            const statusLabel = formatStatusLabel(stop.status);
            const passengerLabel = stop.passengerCount === 1 ? '1 passenger' : `${stop.passengerCount} passengers`;
            const fareText = stop.bookingFareDisplay || (Number.isFinite(stop.bookingFare) ? `₱${Number(stop.bookingFare).toFixed(2)}` : null);

            li.innerHTML = `
                <div class="stop-header">
                    <div>
                        <span class="stop-badge ${badgeClass}">${index + 1}</span>
                        ${escapeHtml(typeLabel)} &ndash; ${escapeHtml(stop.passengerName || 'Passenger')}
                    </div>
                    <span class="stop-status-pill ${escapeHtml(statusClass)}">${escapeHtml(statusLabel)}</span>
                </div>
                <div class="stop-meta">${escapeHtml(stop.address || '--')}</div>
                <div class="stop-meta">${escapeHtml(passengerLabel)}</div>
                ${stop.isFirstForBooking && fareText ? `<div class="stop-meta">Fare: ${escapeHtml(fareText)}</div>` : ''}
                ${stop.note ? `<div class="stop-note">${escapeHtml(stop.note)}</div>` : ''}
            `;

            fragment.appendChild(li);
        });

        itineraryDom.stopList.appendChild(fragment);
    }

    function renderBookingSummaries(bookings) {
        if (!itineraryDom.bookingsContainer) return;
        itineraryDom.bookingsContainer.innerHTML = '';

        const list = Array.isArray(bookings) ? bookings : [];
        if (!list.length) {
            const empty = document.createElement('p');
            empty.className = 'booking-summary-empty';
            empty.textContent = 'No active bookings.';
            itineraryDom.bookingsContainer.appendChild(empty);
            return;
        }

        const heading = document.createElement('h4');
        heading.textContent = 'Active Bookings';
        itineraryDom.bookingsContainer.appendChild(heading);

        const ul = document.createElement('ul');
        ul.className = 'booking-summary-list';

        list.forEach(booking => {
            const li = document.createElement('li');
            li.className = 'booking-summary-item';

            const passengerName = booking.passengerName || 'Passenger';
            const passengerCount = Number(booking.passengers) || 1;
            const seatsLabel = passengerCount === 1 ? '1 seat' : `${passengerCount} seats`;
            const statusText = booking.status ? booking.status.replace(/_/g, ' ').toUpperCase() : '';
            const fareText = booking.fareDisplay || (Number.isFinite(booking.fare) ? `₱${Number(booking.fare).toFixed(2)}` : '--');
            const bookingId = booking.bookingId || '';
            const etaLabel = formatEtaMinutes(Number(booking.remainingDurationMinutes));
            const distanceLabel = formatKilometers(Number(booking.remainingDistanceKm));
            const extraMetaParts = [];
            if (distanceLabel) extraMetaParts.push(escapeHtml(distanceLabel));
            if (etaLabel) extraMetaParts.push(escapeHtml(etaLabel));
            const extraMetaHtml = extraMetaParts.length ? `<div class="meta meta-secondary">${extraMetaParts.join(' • ')}</div>` : '';

            li.innerHTML = `
                <div style="flex:1;">
                    <strong>Booking #${escapeHtml(String(bookingId))}</strong>
                    <div class="meta">${escapeHtml(passengerName)} • ${escapeHtml(seatsLabel)}${statusText ? ` • ${escapeHtml(statusText)}` : ''}</div>
                    ${extraMetaHtml}
                </div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;">
                    <div class="fare">${escapeHtml(fareText)}</div>
                    <button data-single-click class="btn btn-sm btn-danger cancel-booking-btn" data-booking-id="${escapeHtml(String(bookingId))}" style="font-size:11px;padding:4px 8px;">Cancel</button>
                </div>
            `;

            ul.appendChild(li);
        });

        itineraryDom.bookingsContainer.appendChild(ul);
        
        // Wire up cancel buttons
        const cancelButtons = itineraryDom.bookingsContainer.querySelectorAll('.cancel-booking-btn');
        cancelButtons.forEach(btn => {
            btn.addEventListener('click', async function(e) {
                e.preventDefault();
                const bookingId = this.getAttribute('data-booking-id');
                if (!bookingId || !confirm(`Cancel booking #${bookingId}?`)) return;
                const el = this;
                try {
                    if (window.singleClickHelper && typeof window.singleClickHelper.setLoading === 'function') {
                        try { window.singleClickHelper.setLoading(el); } catch (err) {}
                        try { el.dataset.processing = 'true'; } catch (err) {}
                    } else {
                        el.disabled = true;
                        el.textContent = 'Cancelling...';
                    }

                    const response = await fetch(`/booking/${bookingId}/cancel/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': cfg.csrfToken || getCookie('csrftoken'),
                            'Content-Type': 'application/json'
                        },
                        credentials: 'same-origin'
                    });

                    if (response.ok) {
                        // Refresh itinerary and wait for UI update before clearing
                        // the loading state so the button stays loading until
                        // changes are visible to the user.
                        if (typeof fetchItineraryData === 'function') {
                            try { await fetchItineraryData(); } catch (e) { /* ignore */ }
                        }
                        if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') {
                            try { window.singleClickHelper.clearLoading(el); } catch (err) {}
                            try { el.dataset.processing = 'false'; } catch (err) {}
                        } else {
                            el.disabled = false;
                            el.textContent = 'Cancel';
                        }
                        alert('Booking cancelled successfully');
                    } else {
                        const errorText = await response.text();
                        alert(`Failed to cancel: ${errorText}`);
                        if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') {
                            try { window.singleClickHelper.clearLoading(el); } catch (err) {}
                            try { el.dataset.processing = 'false'; } catch (err) {}
                        } else {
                            el.disabled = false;
                            el.textContent = 'Cancel';
                        }
                    }
                } catch (err) {
                    console.error('Cancel booking error:', err);
                    alert('Failed to cancel booking');
                    if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') {
                        try { window.singleClickHelper.clearLoading(el); } catch (err) {}
                        try { el.dataset.processing = 'false'; } catch (err) {}
                    } else {
                        el.disabled = false;
                        el.textContent = 'Cancel';
                    }
                }
            });
        });
    }

    function buildItineraryRoutePoints(itinerary) {
        const points = [];
        const pushPoint = (lat, lon) => {
            const latNum = Number(lat);
            const lonNum = Number(lon);
            if (!Number.isFinite(latNum) || !Number.isFinite(lonNum)) return;
            if (points.length > 0) {
                const [prevLat, prevLon] = points[points.length - 1];
                if (Math.abs(prevLat - latNum) < 1e-5 && Math.abs(prevLon - lonNum) < 1e-5) {
                    return;
                }
            }
            points.push([latNum, lonNum]);
        };

        if (Array.isArray(itinerary?.fullRoutePolyline) && itinerary.fullRoutePolyline.length >= 2) {
            itinerary.fullRoutePolyline.forEach(pt => {
                if (Array.isArray(pt) && pt.length >= 2) {
                    pushPoint(pt[0], pt[1]);
                }
            });
        }

        if (points.length < 2 && Array.isArray(itinerary?.stops)) {
            itinerary.stops.forEach(stop => {
                if (!Array.isArray(stop.coordinates) || stop.coordinates.length !== 2) return;
                pushPoint(stop.coordinates[0], stop.coordinates[1]);
            });
        }

        return points;
    }

    async function requestORSRouteFeature(points) {
        const coordPairs = points.map(([lat, lon]) => {
            const latNum = Number(lat);
            const lonNum = Number(lon);
            if (!Number.isFinite(latNum) || !Number.isFinite(lonNum)) return null;
            return [lonNum, latNum];
        }).filter(Boolean);

        if (coordPairs.length < 2) {
            return null;
        }

        try {
            const response = await fetch('https://api.openrouteservice.org/v2/directions/driving-car', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': ORS_API_KEY,
                },
                body: JSON.stringify({ coordinates: coordPairs, instructions: false }),
            });

            if (!response.ok) {
                let errText = '';
                try { errText = await response.text(); } catch (e) {/* noop */}
                console.warn('ORS route request failed', response.status, errText);
                return null;
            }

            const data = await response.json();
            if (data && data.features && data.features[0]) {
                return data.features[0];
            }
        } catch (err) {
            console.warn('ORS route request error', err);
        }

        return null;
    }

    const ROUTE_COLORS = {
        PICKUP: '#0b63d6',
        DROPOFF: '#0b63d6'
    };

    function ensureRoutePane(paneName, zIndex) {
        if (!mapInstance || !paneName) {
            return null;
        }

        if (!itineraryRoutePaneCache[paneName]) {
            let pane = mapInstance.getPane(paneName);
            if (!pane) {
                pane = mapInstance.createPane(paneName);
            }
            if (pane) {
                if (typeof zIndex === 'number') {
                    pane.style.zIndex = String(zIndex);
                }
                pane.style.pointerEvents = 'none';
            }
            itineraryRoutePaneCache[paneName] = paneName;
        }

        return paneName;
    }

    function buildSegmentLayer(segments) {
        if (!mapInstance) return null;
        if (!Array.isArray(segments) || segments.length === 0) return null;

        const pickupPane = ensureRoutePane('itinerary-route-pickup', 370);
        const dropoffPane = ensureRoutePane('itinerary-route-dropoff', 360);
        const group = L.layerGroup();
        segments.forEach(segment => {
            const rawPoints = Array.isArray(segment?.points) ? segment.points : [];
            const points = rawPoints.map(pt => {
                if (!Array.isArray(pt) || pt.length < 2) return null;
                const lat = Number(pt[0]);
                const lon = Number(pt[1]);
                if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
                return [lat, lon];
            }).filter(Boolean);

            if (points.length < 2) {
                return;
            }

            const typeKey = (segment?.type || '').toUpperCase();
            const color = ROUTE_COLORS[typeKey] || ROUTE_COLORS.PICKUP;
            const precise = Boolean(segment?.precise);
            const style = precise
                ? { color, weight: 5, opacity: 0.88 }
                : { color, weight: 4, opacity: 0.6, dashArray: '6 8' };

            const paneName = typeKey === 'DROPOFF' ? dropoffPane : pickupPane;
            const layer = L.polyline(points, { ...style, pane: paneName });
            group.addLayer(layer);
            if (typeKey === 'PICKUP' && typeof layer.bringToFront === 'function') {
                layer.bringToFront();
            }
        });

        if (group.getLayers().length === 0) {
            return null;
        }

        group.addTo(mapInstance);
        return group;
    }

    async function ensureItineraryRouteLayer(itinerary) {
        if (!mapInstance) return null;

        const points = buildItineraryRoutePoints(itinerary);
        if (points.length < 2) {
            resetItineraryRoute();
            return null;
        }

        const signature = points.map(pt => `${pt[0].toFixed(5)},${pt[1].toFixed(5)}`).join('|');
        const hasApiKey = ORS_API_KEY && ORS_API_KEY.length > 10;
        const routeSegments = Array.isArray(itinerary?.fullRouteSegments) ? itinerary.fullRouteSegments : [];
        const hasSegmentGeometry = routeSegments.some(seg => Array.isArray(seg?.points) && seg.points.length >= 2);
        const hasServerPreciseRoute = Boolean(itinerary && itinerary.fullRouteIsPrecise && hasSegmentGeometry);
        const shouldRequestORS = hasApiKey && !hasServerPreciseRoute;

        if (itineraryRouteLayer && itineraryRouteSignature === signature) {
            const layerIsUsable = !itineraryRouteIsFallback || !shouldRequestORS;
            if (layerIsUsable) {
                if (!mapInstance.hasLayer(itineraryRouteLayer)) {
                    mapInstance.addLayer(itineraryRouteLayer);
                }
                return typeof itineraryRouteLayer.getBounds === 'function' ? itineraryRouteLayer.getBounds() : null;
            }
        }

        let loaderShown = false;
        const ensureLoader = () => {
            if (!loaderShown) {
                showRouteLoader();
                loaderShown = true;
            }
        };
        const cleanupLoader = () => {
            if (loaderShown) {
                hideRouteLoader();
                loaderShown = false;
            }
        };

        itineraryRouteRequestId += 1;
        const requestId = itineraryRouteRequestId;
        ensureLoader();

        if (itineraryRouteLayer && mapInstance.hasLayer(itineraryRouteLayer)) {
            try { mapInstance.removeLayer(itineraryRouteLayer); } catch (err) { /* ignore */ }
        }
        itineraryRouteLayer = null;

        try {
            let newLayer = null;
            if (hasSegmentGeometry) {
                newLayer = buildSegmentLayer(routeSegments);
                itineraryRouteIsFallback = !Boolean(itinerary?.fullRouteIsPrecise);
            }

            if (shouldRequestORS) {
                const feature = await requestORSRouteFeature(points);
                if (requestId !== itineraryRouteRequestId) {
                    return null;
                }
                if (feature) {
                    if (newLayer && mapInstance.hasLayer(newLayer)) {
                        try { mapInstance.removeLayer(newLayer); } catch (err) { /* ignore */ }
                    }
                    const paneName = ensureRoutePane('itinerary-route-ors', 365);
                    newLayer = L.geoJSON(feature, {
                        style: { color: '#0b63d6', weight: 5, opacity: 0.88 },
                        pane: paneName
                    }).addTo(mapInstance);
                    itineraryRouteIsFallback = false;
                }
            }

            if (!newLayer) {
                const baseStyle = { color: '#0b63d6', weight: 5, opacity: 0.88 };
                const fallbackStyle = { ...baseStyle, weight: 4, opacity: 0.7, dashArray: '6 8' };
                const lineStyle = hasServerPreciseRoute ? baseStyle : fallbackStyle;
                const paneName = ensureRoutePane('itinerary-route-fallback', 355);
                newLayer = L.polyline(points.map(([lat, lon]) => [lat, lon]), { ...lineStyle, pane: paneName }).addTo(mapInstance);
                itineraryRouteIsFallback = !hasServerPreciseRoute;

                if (hasSegmentGeometry && itinerary?.fullRouteIsPrecise) {
                    newLayer.setStyle(baseStyle);
                }
            }

            itineraryRouteLayer = newLayer;
            itineraryRouteSignature = signature;

            return typeof newLayer.getBounds === 'function' ? newLayer.getBounds() : null;
        } catch (err) {
            console.warn('Unable to render itinerary route', err);
            itineraryRouteLayer = null;
            itineraryRouteSignature = null;
            itineraryRouteIsFallback = false;
            return null;
        } finally {
            cleanupLoader();
        }
    }

    async function renderItineraryMap(itinerary) {
        if (!mapInstance) return;

        try {
            clearItineraryMarkers();

            if (!itinerary || !Array.isArray(itinerary.stops) || itinerary.stops.length === 0) {
                resetItineraryRoute();
                return;
            }

            const boundsPoints = [];

            const driverCoord = Array.isArray(itinerary.driverStartCoordinate) ? itinerary.driverStartCoordinate : null;
            if (driverCoord && driverCoord.length === 2) {
                const driverLat = Number(driverCoord[0]);
                const driverLon = Number(driverCoord[1]);
                if (Number.isFinite(driverLat) && Number.isFinite(driverLon)) {
                    const driverIcon = L.divIcon({
                        className: 'driver-marker stop-marker',
                        html: '<div class="marker-inner"></div>',
                        iconSize: [32, 36],
                        iconAnchor: [16, 36],
                    });
                    const driverMarker = L.marker([driverLat, driverLon], { icon: driverIcon }).addTo(mapInstance);
                    driverMarker.bindPopup('Driver start location');
                    itineraryMarkers.push(driverMarker);
                    boundsPoints.push([driverLat, driverLon]);
                }
            }

            itinerary.stops.forEach((stop, idx) => {
                if (!Array.isArray(stop.coordinates) || stop.coordinates.length !== 2) return;
                const lat = Number(stop.coordinates[0]);
                const lon = Number(stop.coordinates[1]);
                if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

                const isPickup = (stop.type || '').toUpperCase() === 'PICKUP';
                const iconClass = isPickup ? 'pickup' : 'dest';
                const markerHtml = '<div class="marker-inner"><span class="marker-number">' + (idx + 1) + '</span></div>';
                const icon = L.divIcon({
                    className: `stop-sequence-marker stop-marker ${iconClass}-marker`,
                    html: markerHtml,
                    iconSize: [30, 36],
                    iconAnchor: [15, 36],
                });
                const markerTitle = isPickup ? 'Pickup' : 'Drop-off';
                const marker = L.marker([lat, lon], { icon }).addTo(mapInstance);
                marker.bindPopup(`${markerTitle}<br>${escapeHtml(stop.address || '--')}`);
                itineraryMarkers.push(marker);
                boundsPoints.push([lat, lon]);
                if (stop.status === 'CURRENT') {
                    marker.openPopup();
                }
            });

            const routeBounds = await ensureItineraryRouteLayer(itinerary);
            let combinedBounds = null;

            if (routeBounds) {
                if (typeof routeBounds.isValid === 'function' && !routeBounds.isValid()) {
                    combinedBounds = null;
                } else {
                    combinedBounds = typeof routeBounds.clone === 'function' ? routeBounds.clone() : routeBounds;
                }
            }

            // Ensure markers render above route layers so they remain visible.
            try {
                itineraryMarkers.forEach(marker => {
                    try {
                        if (marker && typeof marker.setZIndexOffset === 'function') marker.setZIndexOffset(1000);
                        if (marker && typeof marker.bringToFront === 'function') marker.bringToFront();
                    } catch (e) { /* ignore individual marker errors */ }
                });
            } catch (e) { /* ignore */ }

            boundsPoints.forEach(([lat, lon]) => {
                if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
                const point = L.latLng(lat, lon);
                if (!combinedBounds) {
                    combinedBounds = L.latLngBounds(point, point);
                } else {
                    combinedBounds.extend(point);
                }
            });

            if (combinedBounds && typeof combinedBounds.isValid === 'function' ? combinedBounds.isValid() : true) {
                try {
                    mapInstance.fitBounds(combinedBounds, { padding: [60, 60], maxZoom: 17 });
                } catch (err) {
                    console.warn('fitBounds failed', err);
                }
            }
        } catch (err) {
            console.warn('renderItineraryMap failed', err);
        }
    }

    function renderItineraryUI() {
        if (!itineraryDom.summaryStatusText || !itineraryData) {
            if (itineraryDom.summaryStatusText) itineraryDom.summaryStatusText.textContent = 'NO ITINERARY';
            if (itineraryDom.summaryActionBtn) {
                itineraryDom.summaryActionBtn.textContent = 'Start';
                itineraryDom.summaryActionBtn.disabled = true;
            }
            if (itineraryDom.summaryActionType) itineraryDom.summaryActionType.textContent = '--';
            if (itineraryDom.summaryAddress) itineraryDom.summaryAddress.textContent = 'Awaiting assignments.';
            if (itineraryDom.summaryMeta) itineraryDom.summaryMeta.textContent = '';
            if (itineraryDom.fullBookingCount) itineraryDom.fullBookingCount.textContent = '0';
            if (itineraryDom.fullCapacity) itineraryDom.fullCapacity.textContent = '0 / 0';
            if (itineraryDom.fullEarnings) itineraryDom.fullEarnings.textContent = '0.00';
            if (itineraryDom.summaryStopNum) itineraryDom.summaryStopNum.textContent = '0';
            if (itineraryDom.summaryStopTotal) itineraryDom.summaryStopTotal.textContent = '0';
            if (itineraryDom.summaryCapacity) itineraryDom.summaryCapacity.textContent = '0 / 0';
            if (itineraryDom.chatBtn) {
                itineraryDom.chatBtn.disabled = true;
                itineraryDom.chatBtn.removeAttribute('data-chat-booking-id');
            }
            renderStopList([]);
            renderBookingSummaries([]);
            clearItineraryMapLayers();
            hideRouteLoader();
            return;
        }

        const stops = Array.isArray(itineraryData.stops) ? itineraryData.stops : [];
        if (stops.length === 0) {
            itineraryDom.summaryStatusText.textContent = 'NO ITINERARY';
            itineraryDom.summaryActionType.textContent = '--';
            itineraryDom.summaryAddress.textContent = 'Awaiting assignments.';
            if (itineraryDom.summaryMeta) itineraryDom.summaryMeta.textContent = '';
            itineraryDom.summaryActionBtn.disabled = true;
            itineraryDom.summaryActionBtn.textContent = 'Start';
            itineraryDom.summaryActionBtn.removeAttribute('data-stop-id');
            if (itineraryDom.fullBookingCount) itineraryDom.fullBookingCount.textContent = '0';
            if (itineraryDom.fullCapacity) itineraryDom.fullCapacity.textContent = `${itineraryData.totalPassengers || 0} / ${itineraryData.maxCapacity || 0}`;
            if (itineraryDom.fullEarnings) itineraryDom.fullEarnings.textContent = (itineraryData.totalEarnings || 0).toFixed(2);
            if (itineraryDom.summaryStopNum) itineraryDom.summaryStopNum.textContent = '0';
            if (itineraryDom.summaryStopTotal) itineraryDom.summaryStopTotal.textContent = '0';
            if (itineraryDom.summaryCapacity) itineraryDom.summaryCapacity.textContent = `${itineraryData.totalPassengers || 0} / ${itineraryData.maxCapacity || 0}`;
            if (itineraryDom.chatBtn) {
                itineraryDom.chatBtn.disabled = true;
                itineraryDom.chatBtn.removeAttribute('data-chat-booking-id');
            }
            renderStopList([]);
            renderBookingSummaries([]);
            clearItineraryMapLayers();
            hideRouteLoader();
            return;
        }

        currentStopIndex = Math.min(Math.max(Number(itineraryData.currentStopIndex || 0), 0), stops.length - 1);
        const currentStop = stops[currentStopIndex];

        itineraryDom.summaryStatusText.textContent = 'UP NEXT';
        const actionPrefix = currentStop.type === 'PICKUP' ? 'PICK UP' : 'DROP OFF';
        const passengerName = currentStop.passengerName || 'Passenger';
        const passengerSuffix = currentStop.passengerCount > 1 ? ` (+${currentStop.passengerCount})` : ' (+1)';
        itineraryDom.summaryActionType.textContent = `${actionPrefix}: ${passengerName}${passengerSuffix}`;
        itineraryDom.summaryAddress.textContent = currentStop.address || '--';
        itineraryDom.summaryActionBtn.disabled = false;
        itineraryDom.summaryActionBtn.textContent = getStopActionLabel(currentStop);
        itineraryDom.summaryActionBtn.setAttribute('data-stop-id', currentStop.stopId);

        if (itineraryDom.summaryMeta) {
            const remainingSeconds = Number(itineraryData.remainingDurationSec);
            const etaMinutes = secondsToMinutes(remainingSeconds);
            const etaLabel = etaMinutes !== null ? formatEtaMinutes(etaMinutes) : null;
            const distanceLabel = formatKilometers(Number(itineraryData.remainingDistanceKm));
            const parts = [];
            if (etaLabel) parts.push(etaLabel);
            if (distanceLabel) parts.push(`${distanceLabel} remaining`);
            itineraryDom.summaryMeta.textContent = parts.length ? parts.join(' • ') : '';
        }

        if (itineraryDom.summaryStopNum) itineraryDom.summaryStopNum.textContent = String(currentStopIndex + 1);
        if (itineraryDom.summaryStopTotal) itineraryDom.summaryStopTotal.textContent = String(stops.length);

        if (itineraryDom.fullBookingCount) itineraryDom.fullBookingCount.textContent = String(itineraryData.totalBookings || 0);
        if (itineraryDom.fullCapacity) itineraryDom.fullCapacity.textContent = `${itineraryData.totalPassengers || 0} / ${itineraryData.maxCapacity || 0}`;
        if (itineraryDom.fullEarnings) itineraryDom.fullEarnings.textContent = (itineraryData.totalEarnings || 0).toFixed(2);
        if (itineraryDom.summaryCapacity) itineraryDom.summaryCapacity.textContent = `${itineraryData.totalPassengers || 0} / ${itineraryData.maxCapacity || 0}`;

        if (itineraryDom.chatBtn) {
            const chatBookingId = getPreferredChatBookingId();
            if (chatBookingId) {
                itineraryDom.chatBtn.disabled = false;
                itineraryDom.chatBtn.setAttribute('data-chat-booking-id', String(chatBookingId));
            } else {
                itineraryDom.chatBtn.disabled = true;
                itineraryDom.chatBtn.removeAttribute('data-chat-booking-id');
            }
        }

        renderStopList(stops);
        renderBookingSummaries(itineraryData.bookingSummaries);
        renderItineraryMap(itineraryData);
    }

    let itineraryStageSignature = null;

    function computeItineraryStageSignature(itinerary) {
        if (!itinerary) {
            return 'none';
        }
        const base = `${itinerary.tripId || itinerary.id || ''}:${itinerary.status || ''}`;
        const stopsSig = Array.isArray(itinerary.stops)
            ? itinerary.stops.map((stop) => {
                const sid = stop.stopId || stop.stop_uid || stop.bookingId || stop.booking_id || stop.sequence || 0;
                const stat = stop.status || '';
                const typ = stop.type || stop.stop_type || '';
                return `${sid}:${typ}:${stat}`;
            }).join('|')
            : '';
        const bookingsSig = Array.isArray(itinerary.bookingSummaries)
            ? itinerary.bookingSummaries.map((b) => `${b.bookingId || b.booking_id || ''}:${b.status || ''}`).join('|')
            : '';
        return `${base}#${stopsSig}#${bookingsSig}`;
    }

    async function fetchItineraryData(options = {}) {
        if (!cfg.itineraryEndpoint) return;
        const forceLoader = Boolean(options.forceLoader);
        let loaderShown = false;
        if (forceLoader || !itineraryHasLoaded) {
            showRouteLoader(true);
            loaderShown = true;
        }
        try {
            const response = await fetch(cfg.itineraryEndpoint, { credentials: 'same-origin' });
            if (!response.ok) {
                throw new Error(`Status ${response.status}`);
            }
            const payload = await response.json();
            if (payload && payload.driverStatus && typeof window.updateDriverAvailabilityUI === 'function') {
                try {
                    window.updateDriverAvailabilityUI(payload.driverStatus);
                } catch (err) {
                    console.warn('Driver availability sync failed', err);
                }
            }
            if (!payload || payload.status !== 'success') {
                throw new Error('Invalid itinerary payload');
            }

            const newSignature = computeItineraryStageSignature(payload.itinerary);
            if (newSignature !== itineraryStageSignature) {
                itineraryStageSignature = newSignature;
                itineraryHasLoaded = false;
                if (!loaderShown) {
                    showRouteLoader(true);
                    loaderShown = true;
                }
            }
            itineraryData = payload.itinerary || null;
            updateTrackingState();
            renderItineraryUI();
            if (!itineraryHasLoaded) {
                itineraryHasLoaded = true;
            }
        } catch (err) {
            console.warn('Failed to fetch itinerary', err);
        } finally {
            if (loaderShown) {
                hideRouteLoader();
            }
        }
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
        const button = document.getElementById('driver-sos-button');
        if (!button) return;

        const progressEl = button.querySelector('.sos-button__progress');
        const hintEl = button.querySelector('.sos-button__hint');
        const liveRegion = document.getElementById('driver-sos-live-region');
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

    async function completeItineraryStop(stopId) {
        if (!cfg.completeStopEndpoint || !stopId) return;
        try {
            const csrf = cfg.csrfToken || getCookie('csrftoken');
            const response = await fetch(cfg.completeStopEndpoint, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf,
                },
                body: JSON.stringify({ stopId })
            });

            if (!response.ok) {
                const text = await response.text();
                throw new Error(text || response.statusText);
            }

            const payload = await response.json();
            if (payload && payload.driverStatus && typeof window.updateDriverAvailabilityUI === 'function') {
                try {
                    window.updateDriverAvailabilityUI(payload.driverStatus);
                } catch (err) {
                    console.warn('Driver availability sync (stop completion) failed', err);
                }
            }
            if (payload && payload.itinerary) {
                itineraryData = payload.itinerary;
                updateTrackingState();
                renderItineraryUI();
                
                // Check if payment modal should be shown (dropoff completed)
                if (payload.showPaymentModal && payload.completedBookings && payload.completedBookings.length > 0) {
                    // Prefer the booking that triggered this dropoff completion
                    const targetId = payload.paymentModalBookingId;
                    const booking = (targetId !== undefined && targetId !== null)
                        ? payload.completedBookings.find(b => String(b.id) === String(targetId))
                        : payload.completedBookings[0];

                    if (booking) {
                        setTimeout(() => {
                            if (typeof window.showPaymentPINModal === 'function') {
                                window.showPaymentPINModal(booking.id, booking.fare);
                            }
                        }, 500);
                    }
                }
            } else {
                // Ensure we wait for the itinerary refresh to finish before
                // resolving — otherwise callers may clear loading while the
                // UI is still updating, causing the button to revert to text
                // though changes aren't visible yet.
                if (typeof fetchItineraryData === 'function') {
                    await fetchItineraryData();
                }
            }
        } catch (err) {
            console.warn('Failed to complete stop', err);
            alert('Unable to update stop. Please try again.');
        }
    }

    function handleSummaryActionClick() {
        if (!itineraryDom.summaryActionBtn || !itineraryData) return;
        const stopId = itineraryDom.summaryActionBtn.getAttribute('data-stop-id');
        if (!stopId) return;
        const btn = itineraryDom.summaryActionBtn;
        try {
            if (window.singleClickHelper && typeof window.singleClickHelper.setLoading === 'function') {
                window.singleClickHelper.setLoading(btn);
            } else {
                btn.disabled = true;
            }
        } catch (e) {
            btn.disabled = true;
        }

        completeItineraryStop(stopId).then(() => {
            // dispatch success so helper can clear loading
            try { btn.dispatchEvent(new CustomEvent('single-click-success', { bubbles: true })); } catch (e) {}
            try {
                if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') {
                    window.singleClickHelper.clearLoading(btn);
                    btn.dataset.processing = 'false';
                }
            } catch (e) {}
        }).catch(() => {
            try { btn.dispatchEvent(new CustomEvent('single-click-error', { bubbles: true })); } catch (e) {}
            try {
                if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') {
                    window.singleClickHelper.clearLoading(btn);
                    btn.dataset.processing = 'false';
                }
            } catch (e) {}
        }).finally(() => {
            try { if (!window.singleClickHelper) btn.disabled = false; } catch (e) {}
        });
    }

    function openTripChatFromUI(event) {
        if (event) {
            event.preventDefault();
        }
        const preferredIdAttr = itineraryDom.chatBtn ? itineraryDom.chatBtn.getAttribute('data-chat-booking-id') : null;
        const parsedId = preferredIdAttr ? Number(preferredIdAttr) : NaN;
        const bookingId = Number.isFinite(parsedId) ? parsedId : getPreferredChatBookingId();
        if (typeof window.openDriverChatModal === 'function') {
            window.openDriverChatModal(bookingId);
        }
    }

    // Driver chat modal and helpers
    (function(){
        // create modal HTML and append to body (if not present)
        if (!document.getElementById('driverChatModal')) {
            const modal = document.createElement('div'); 
            modal.id = 'driverChatModal'; 
            modal.style.display = 'none'; 
            modal.style.position = 'fixed'; 
            modal.style.left = '108px'; // Match driver-info-card positioning
            modal.style.bottom = '20px'; 
            modal.style.width = '320px'; 
            modal.style.maxWidth = '320px'; 
            modal.style.background = 'rgba(15, 23, 36, 0.96)'; 
            modal.style.border = '1px solid rgba(255, 255, 255, 0.08)'; 
            modal.style.boxShadow = '0 18px 36px rgba(11, 38, 56, 0.28)'; 
            modal.style.zIndex = '2200'; 
            modal.style.borderRadius = '18px'; 
            modal.style.padding = '0';
            modal.style.backdropFilter = 'blur(3px)';
            modal.style.webkitBackdropFilter = 'blur(3px)';
            modal.style.color = '#f4f7ff';
            modal.style.transition = 'left 0.3s ease';
            modal.className = 'driver-chat-modal';
            modal.innerHTML = `
                <div style="display:flex; align-items:center; justify-content:space-between; padding:8px 12px; border-bottom:1px solid rgba(255, 255, 255, 0.08); background:rgba(255, 255, 255, 0.05);">
                    <strong id="driverChatTitle" style="color:#f4f7ff;">Trip Chat</strong>
                    <div><button id="driverChatClose" class="btn btn-sm" style="background:#dc3545;color:#fff;border:none;padding:4px 8px;border-radius:6px;cursor:pointer;">✕</button></div>
                </div>
                <div id="driverChatMessages" style="height:300px; overflow:auto; padding:12px; background:#ffffff; color:#1a1a1a;"><p style="color:#666;">Loading messages...</p></div>
                <form id="driverChatForm" style="display:flex; gap:8px; padding:12px; border-top:1px solid rgba(255, 255, 255, 0.08);">
                    <textarea id="driverChatInput" rows="2" style="flex:1; padding:8px; background:#ffffff; border:1px solid rgba(255,255,255,0.3); border-radius:6px; color:#1a1a1a;" placeholder="Type a message"></textarea>
                    <button type="submit" class="btn btn-primary">Send</button>
                </form>
            `; document.body.appendChild(modal);
        }

        let _driverChatBookingId = null; let _driverChatPolling = null;
        function getCookie(name) { let cookieValue = null; if (document.cookie && document.cookie !== '') { const cookies = document.cookie.split(';'); for (let i = 0; i < cookies.length; i++) { const cookie = cookies[i].trim(); if (cookie.substring(0, name.length + 1) === (name + '=')) { cookieValue = decodeURIComponent(cookie.substring(name.length + 1)); break; } } } return cookieValue; }

        async function loadDriverMessages() {
            if (!_driverChatBookingId) {
                return;
            }

            const container = document.getElementById('driverChatMessages');
            let response;
            try {
                response = await fetch(`/chat/api/booking/${_driverChatBookingId}/messages/`, { credentials: 'same-origin' });
            } catch (fetchErr) {
                container.innerHTML = '<p class="muted">Unable to load messages.</p>';
                return;
            }

            if (!response.ok) {
                container.innerHTML = '<p class="muted">Unable to load messages.</p>';
                return;
            }

            let payload;
            try {
                payload = await response.json();
            } catch (parseErr) {
                container.innerHTML = '<p class="muted">Unable to load messages.</p>';
                return;
            }

            const messages = Array.isArray(payload.messages) ? payload.messages : [];
            if (!messages.length) {
                container.innerHTML = '<p class="muted">No messages yet.</p>';
                const titleEl = document.getElementById('driverChatTitle');
                if (titleEl) titleEl.textContent = 'Trip Chat';
                return;
            }

            const bookingIds = new Set();
            messages.forEach(msg => {
                if (msg && msg.booking_id) {
                    bookingIds.add(msg.booking_id);
                }
            });

            container.innerHTML = '';
            let lastDate = null;
            messages.forEach(msg => {
                const timestamp = new Date(msg.timestamp);
                const dateKey = timestamp.toDateString();
                if (dateKey !== lastDate) {
                    const sep = document.createElement('div');
                    sep.className = 'chat-date-sep';
                    sep.textContent = timestamp.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
                    container.appendChild(sep);
                    lastDate = dateKey;
                }

                const div = document.createElement('div');
                div.style.marginBottom = '8px';
                const own = Number(msg.sender_id) === Number(userId);
                div.className = own ? 'chat-msg-own' : 'chat-msg-other';

                const senderName = escapeHtml(msg.sender_display_name || msg.sender_username || 'Participant');
                const senderRole = msg.sender_role ? ` • ${escapeHtml(msg.sender_role)}` : '';
                const timeLabel = timestamp.toLocaleTimeString();
                const showBookingContext = bookingIds.size > 1;
                const bookingLabel = showBookingContext ? `<div class="chat-msg-booking">${escapeHtml(msg.booking_label || `Booking ${msg.booking_id}`)}</div>` : '';

                div.innerHTML = `
                    <div class="chat-msg-meta">${senderName}${senderRole} • ${timeLabel}</div>
                    ${bookingLabel}
                    <div>${escapeHtml(msg.message)}</div>
                `;
                container.appendChild(div);
            });

            try {
                const newest = container.lastElementChild;
                container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
                if (newest) {
                    newest.classList.add('flash-animate');
                    setTimeout(() => newest.classList.remove('flash-animate'), 900);
                }
            } catch (e) {
                container.scrollTop = container.scrollHeight;
            }

            const titleEl = document.getElementById('driverChatTitle');
            if (titleEl) {
                titleEl.textContent = bookingIds.size > 1 ? `Trip Chat (${bookingIds.size} bookings)` : 'Trip Chat';
            }
        }

        function openDriverChatModal(bookingId) {
            const normalizedId = Number.isFinite(Number(bookingId)) ? Number(bookingId) : null;
            _driverChatBookingId = normalizedId || getPreferredChatBookingId();
            if (!_driverChatBookingId) {
                alert('No active bookings to chat with yet.');
                return;
            }
            const el = document.getElementById('driverChatModal');
            el.style.display = 'block';
            
            // Match the left positioning of driver-info-card based on open panels
            if (document.body.classList.contains('history-panel-open') || 
                document.body.classList.contains('wallet-panel-open') || 
                document.body.classList.contains('rides-panel-open')) {
                el.style.left = '508px';
            } else {
                el.style.left = '108px';
            }
            
            // Hide itinerary card and show chat in its place
            const itineraryCard = document.getElementById('itinerary-card');
            if (itineraryCard) {
                itineraryCard.style.display = 'none';
            }
            
            const titleEl = document.getElementById('driverChatTitle');
            if (titleEl) {
                titleEl.textContent = 'Trip Chat';
            }
            loadDriverMessages();
                if (navigator.serviceWorker && navigator.serviceWorker.controller) {
                    // Rely on push messages forwarded by the service worker
                    console.log('Using push for driver chat updates');
                } else {
                    _driverChatPolling = setInterval(loadDriverMessages, 6000);
                }
        }

        function closeDriverChatModal() {
            const el = document.getElementById('driverChatModal');
            el.style.display = 'none';
            
            // Restore itinerary card visibility
            const itineraryCard = document.getElementById('itinerary-card');
            if (itineraryCard) {
                itineraryCard.style.display = 'block';
            }
            
            _driverChatBookingId = null;
            if (_driverChatPolling) {
                clearInterval(_driverChatPolling);
                _driverChatPolling = null;
            }
        }

        // Listen for push messages to refresh chat when appropriate
        try {
            if (navigator.serviceWorker && navigator.serviceWorker.addEventListener) {
                navigator.serviceWorker.addEventListener('message', function (evt) {
                    try {
                        const payload = evt.data || {};
                        const data = (payload && payload.data) ? payload.data : payload;
                        if (!data || data.type !== 'chat_message') return;
                        const bid = data.booking_id;
                        if (!bid) return;
                        if (_driverChatBookingId && String(_driverChatBookingId) === String(bid)) {
                            loadDriverMessages();
                        } else {
                            // Optionally, flash a UI indicator for new messages on other bookings
                        }
                    } catch (e) { /* ignore */ }
                });
            }
        } catch (e) { /* ignore */ }

        // Attach events
        document.getElementById('driverChatClose').addEventListener('click', (e) => { e.preventDefault(); closeDriverChatModal(); });
        document.getElementById('driverChatForm').addEventListener('submit', async (e) => { e.preventDefault(); if (!_driverChatBookingId) return; const txt = (document.getElementById('driverChatInput').value || '').trim(); if (!txt) return; const res = await fetch(`/chat/api/booking/${_driverChatBookingId}/messages/send/`, { method:'POST', credentials:'same-origin', headers: { 'Content-Type':'application/json','X-CSRFToken': getCookie('csrftoken') }, body: JSON.stringify({ message: txt }) }); if (!res.ok) { alert('Failed to send'); return; } document.getElementById('driverChatInput').value = ''; loadDriverMessages(); });

        // Expose open function for sidebar button
        window.openDriverChatModal = openDriverChatModal;
        window.showDriverChatButton = function() {
            const card = document.getElementById('itinerary-card');
            if (card) {
                try { card.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) { /* ignore */ }
                card.classList.add('pulse-highlight');
                setTimeout(() => card.classList.remove('pulse-highlight'), 2400);
            }
        };
    })();

    // Map + active booking initialization
    document.addEventListener('DOMContentLoaded', function() {
        try {
            const map = L.map('map-container').setView([10.3157, 123.8854], 13);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors', maxZoom: 19 }).addTo(map);
            // Leaflet needs an invalidateSize() after layout changes so the map paints full area
            setTimeout(() => { try { map.invalidateSize(); } catch(e){} }, 250);
            if (navigator.geolocation) navigator.geolocation.getCurrentPosition((pos) => { map.setView([pos.coords.latitude, pos.coords.longitude], 15); }, () => {}, { enableHighAccuracy: true, timeout: 5000 });

            // Expose map instance for review buttons and wire review button clicks
            window.DRIVER_MAP = map;
            try {
                document.dispatchEvent(new CustomEvent('driver:mapReady', { detail: { map } }));
            } catch (err) {
                console.warn('driver:mapReady dispatch failed', err);
            }
            initItinerary(map);
            startAvailableRidesPolling();
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) {
                    refreshAvailableRidesList(true);
                }
            });
            document.addEventListener('driver:rideAccepted', () => {
                try {
                    if (typeof window.clearDriverReviewOverlays === 'function') {
                        window.clearDriverReviewOverlays();
                    }
                } catch (err) {
                    console.warn('Failed to clear preview overlays on accept event', err);
                }
                refreshAvailableRidesList(true);
            });
            document.addEventListener('driver:rideCancelled', () => {
                try {
                    if (typeof window.clearDriverReviewOverlays === 'function') {
                        window.clearDriverReviewOverlays();
                    }
                } catch (err) {
                    console.warn('Failed to clear preview overlays on cancel event', err);
                }
                refreshAvailableRidesList(true);
            });
            // Sidebar toggles: rides icon opens the hidden sidebar-content; open-rides button also opens it
            try {
                const ridesIconEl = document.getElementById('rides-icon');
                if (ridesIconEl) {
                    ridesIconEl.addEventListener('click', function(e) {
                        if (typeof window.openDriverRidesPanel === 'function') {
                            window.openDriverRidesPanel(e);
                        }
                    });
                }
            } catch(e){ console.warn('Rides panel init failed', e); }

            // Helpful debug: show console message if ORS API key missing
            if (!ORS_API_KEY || ORS_API_KEY.length < 10) {
                console.warn('OpenRouteService API key appears missing or short; client-side route preview may fail. Set OPENROUTESERVICE_API_KEY in settings and render it into DRIVER_DASH_CONFIG.');
            }
            initEmergencySOSButton();
            function reviewBooking(bookingId) {
                console.log('reviewBooking called for', bookingId);
                if (!bookingId) return;
                const routeDetails = document.getElementById('route-details');
                let loaderShown = false;
                const ensureLoader = () => {
                    if (!loaderShown) {
                        showRouteLoader(true);
                        loaderShown = true;
                    }
                };
                const finalizeLoader = () => {
                    if (loaderShown) {
                        hideRouteLoader();
                        loaderShown = false;
                    }
                };
                ensureLoader();

                fetch(`/api/booking/${bookingId}/route_info/`).then(r => r.json()).then(async (info) => {
                    if (!info || info.status !== 'success') { console.log('route_info returned', info); if (routeDetails) routeDetails.textContent = 'No route info available.'; return; }
                    
                    console.log('[Driver Dashboard Review] Route info received:', {
                        driver_lat: info.driver_lat,
                        driver_lon: info.driver_lon,
                        booking_status: info.booking_status,
                        driver: info.driver
                    });
                    
                    // Draw pickup->destination route for review
                    const pLat = Number(info.pickup_lat); const pLon = Number(info.pickup_lon); const xLat = Number(info.destination_lat); const xLon = Number(info.destination_lon);
                    if (!(Number.isFinite(pLat) && Number.isFinite(pLon) && Number.isFinite(xLat) && Number.isFinite(xLon))) {
                        if (routeDetails) routeDetails.textContent = 'Insufficient coordinates to preview route.'; return;
                    }
                    try {
                        console.log('ORS route request for review:', pLat,pLon,xLat,xLon);
                        // request ORS for pickup->dest
                        const rdUrl = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${ORS_API_KEY}&start=${pLon},${pLat}&end=${xLon},${xLat}`;
                        const rdRes = await fetch(rdUrl);
                        if (!rdRes.ok) { if (routeDetails) routeDetails.textContent = 'Routing service error.'; return; }
                        const rd = await rdRes.json();
                        if (rd && rd.features && rd.features[0]) {
                            console.log('ORS returned route features', rd.features[0]);
                            try { clearDriverReviewOverlays(); } catch(e) { console.warn('Failed to clear prior review overlays', e); }

                            // add route layer (pickup->destination)
                            window._driverReviewLayer = L.geoJSON(rd.features[0], { style: { color: '#007bff', weight: 5, opacity: 0.8 } }).addTo(window.DRIVER_MAP);

                            // Additionally, draw driver -> pickup route if driver coords exist so drivers can see how far they must travel
                            try {
                                const dLat = (info.driver_lat != null) ? Number(info.driver_lat) : null;
                                const dLon = (info.driver_lon != null) ? Number(info.driver_lon) : null;
                                if (dLat != null && dLon != null && Number.isFinite(dLat) && Number.isFinite(dLon) && Number.isFinite(pLat) && Number.isFinite(pLon)) {
                                    const dpUrl = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${ORS_API_KEY}&start=${dLon},${dLat}&end=${pLon},${pLat}`;
                                    try {
                                        const dpRes = await fetch(dpUrl);
                                        if (dpRes.ok) {
                                            const dpData = await dpRes.json();
                                            if (dpData && dpData.features && dpData.features[0]) {
                                                // draw solid green driver->pickup route (solid line - not dashed)
                                                window._driverReviewDriverToPickupLayer = L.geoJSON(dpData.features[0], { style: { color: '#0b63d6', weight: 5, opacity: 0.8 } }).addTo(window.DRIVER_MAP);
                                                try { const dpBounds = window._driverReviewDriverToPickupLayer.getBounds(); if (dpBounds) { window._driverReviewLayer.getBounds().extend(dpBounds); } } catch(e){}
                                            } else { console.log('Driver->pickup ORS returned no features', dpData); }
                                        } else {
                                            console.warn('Driver->pickup ORS request failed', dpRes.status);
                                        }
                                    } catch(e) { console.warn('Driver->pickup ORS fetch failed', e); }
                                }
                            } catch(e) { console.warn('Driver->pickup route generation failed', e); }

                            // create and add markers for driver, pickup and destination when coords are present
                            const markersToBounds = [];
                            try {
                                // driver location if available
                                const dLat = (info.driver_lat != null) ? Number(info.driver_lat) : null;
                                const dLon = (info.driver_lon != null) ? Number(info.driver_lon) : null;
                                if (dLat != null && dLon != null && Number.isFinite(dLat) && Number.isFinite(dLon)) {
                                    const driverIcon = L.divIcon({ className: 'driver-marker', html: '<div class="marker-inner"></div>', iconSize: [28,28] });
                                    window._driverReviewDriverMarker = L.marker([dLat, dLon], { icon: driverIcon }).addTo(window.DRIVER_MAP).bindPopup('Driver');
                                    markersToBounds.push(window._driverReviewDriverMarker.getLatLng());
                                }
                                // pickup
                                if (Number.isFinite(pLat) && Number.isFinite(pLon)) {
                                    const pickupIcon = L.divIcon({ className: 'pickup-marker', html: '<div class="marker-inner"></div>', iconSize: [24,24] });
                                    window._driverReviewPickupMarker = L.marker([pLat, pLon], { icon: pickupIcon }).addTo(window.DRIVER_MAP).bindPopup('Pickup');
                                    markersToBounds.push(window._driverReviewPickupMarker.getLatLng());
                                }
                                // destination
                                if (Number.isFinite(xLat) && Number.isFinite(xLon)) {
                                    const destIcon = L.divIcon({ className: 'dest-marker', html: '<div class="marker-inner"></div>', iconSize: [24,24] });
                                    window._driverReviewDestMarker = L.marker([xLat, xLon], { icon: destIcon }).addTo(window.DRIVER_MAP).bindPopup('Destination');
                                    markersToBounds.push(window._driverReviewDestMarker.getLatLng());
                                }
                            } catch(e) { console.warn('Add review markers failed', e); }

                            // fit bounds to route layer plus markers
                            try {
                                let bounds = window._driverReviewLayer.getBounds();
                                if (markersToBounds.length > 0) { markersToBounds.forEach(ll => bounds.extend(ll)); }
                                window.DRIVER_MAP.fitBounds(bounds, { padding: [40,40] });
                            } catch(e) { console.warn('Fit bounds failed', e); }
                            // populate details
                            const seg = rd.features[0].properties?.segments?.[0];
                            if (routeDetails) routeDetails.innerHTML = `<strong>Pickup:</strong> ${info.pickup_address || '--'}<br><strong>Destination:</strong> ${info.destination_address || '--'}<br><strong>ETA:</strong> ${seg?Math.ceil(seg.duration/60)+' min':'--'} <strong>Distance:</strong> ${seg?(seg.distance/1000).toFixed(2)+' km':'--'}`;
                        } else { if (routeDetails) routeDetails.textContent = 'No route geometry returned.'; }
                    } catch (e) { console.error('Review route error', e); if (routeDetails) routeDetails.textContent = 'Error fetching route.'; }
                }).catch(e => { console.warn('Failed to fetch route_info', e); }).finally(finalizeLoader);
            }

            // Expose reviewBooking globally so other scripts or delegated handlers can call it
            try {
                window.reviewBooking = reviewBooking;
                // If any clicks were queued before initialization, process them now
                if (window._queuedReviewCalls && window._queuedReviewCalls.length) {
                    const queued = window._queuedReviewCalls.slice();
                    window._queuedReviewCalls = [];
                    queued.forEach(bid => {
                        try { reviewBooking(bid); } catch(e) { console.warn('queued reviewBooking call failed', bid, e); }
                    });
                }
            } catch(e) { /* ignore */ }

            // Event delegation handles review button clicks and accept submissions
            document.addEventListener('click', function(event) {
                const reviewBtn = event.target.closest('.review-ride-btn');
                if (reviewBtn) {
                    event.preventDefault();
                    const bid = reviewBtn.getAttribute('data-booking-id');
                    if (bid) {
                        reviewBooking(bid);
                    }
                }
            });

            document.addEventListener('submit', function(event) {
                const form = event.target.closest('form.accept-ride-form');
                if (!form) return;
                event.preventDefault();
                handleAcceptRide(form);
            });
            // Cancel booking handler: use fetch POST to avoid nested form issues
            document.addEventListener('click', function(e) {
                try {
                    const cb = e.target.closest && e.target.closest('#cancel-booking-btn');
                    if (!cb) return;
                    e.preventDefault();
                    const url = cb.getAttribute('data-cancel-url');
                    if (!url) { alert('Cancel URL missing'); return; }
                    // simple getCookie utility
                    function getCookie(name){ let cookieValue = null; if (document.cookie && document.cookie !== '') { const cookies = document.cookie.split(';'); for (let i=0;i<cookies.length;i++){ const cookie = cookies[i].trim(); if (cookie.substring(0, name.length+1) === (name + '=')) { cookieValue = decodeURIComponent(cookie.substring(name.length+1)); break; } } } return cookieValue; }
                    const csrf = getCookie('csrftoken');
                    try {
                        if (window.singleClickHelper && typeof window.singleClickHelper.setLoading === 'function') {
                            try { window.singleClickHelper.setLoading(cb); } catch (err) {}
                            try { cb.dataset.processing = 'true'; } catch (err) {}
                        } else {
                            cb.disabled = true;
                        }
                    } catch (e) { cb.disabled = true; }
                    fetch(url, {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {
                            'X-CSRFToken': csrf,
                            'Accept': 'application/json'
                        }
                    }).then(async (res) => {
                        let payload = null;
                        try {
                            const raw = await res.text();
                            payload = raw ? JSON.parse(raw) : null;
                        } catch (parseErr) {
                            payload = null;
                        }

                        if (res.ok && payload && payload.status === 'success') {
                            document.dispatchEvent(new CustomEvent('driver:rideCancelled', { detail: payload.booking }));
                            if (cb.closest('.driver-ride-card')) {
                                cb.closest('.driver-ride-card').remove();
                            }
                            // Refresh itinerary and wait for UI update before
                            // clearing the loading/disabled state so the user sees
                            // the final state that matches the server.
                            if (typeof fetchItineraryData === 'function') {
                                await fetchItineraryData();
                            }
                            try { if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') { window.singleClickHelper.clearLoading(cb); cb.dataset.processing = 'false'; } } catch (err) {}
                        } else {
                            try { if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') { window.singleClickHelper.clearLoading(cb); cb.dataset.processing = 'false'; } } catch (err) {}
                            cb.disabled = false;
                            const errMsg = (payload && payload.message) ? payload.message : (res.statusText || 'Unable to cancel booking');
                            alert('Cancel failed: ' + errMsg);
                        }
                    }).catch(err => { try { if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') { window.singleClickHelper.clearLoading(cb); cb.dataset.processing = 'false'; } } catch (err) {} cb.disabled = false; alert('Network error when cancelling'); console.warn(err); });
                } catch(err) { console.warn('cancel handler', err); }
            });

            // Delegated click handler fallback: in case buttons are added later or initial binding fails
            document.addEventListener('click', function(e) {
                try {
                    const btn = e.target.closest && e.target.closest('.review-ride-btn');
                    if (!btn) return;
                    e.preventDefault(); const bid = btn.getAttribute('data-booking-id'); if (!bid) return;
                    if (typeof reviewBooking === 'function') reviewBooking(bid);
                } catch(err) { console.warn('Delegated review click handler failed', err); }
            });

        } catch (e) { console.warn('Driver map init failed', e); }
    });

    // Location broadcasting (moved from template) - keep minimal here; uses getCookie
    (function(){
        let locationWatchId = null; let isTracking = false;
        function getCookie(name){ let cookieValue = null; if (document.cookie && document.cookie !== '') { const cookies = document.cookie.split(';'); for (let i=0;i<cookies.length;i++){ const cookie = cookies[i].trim(); if (cookie.substring(0,name.length+1) === (name + '=')) { cookieValue = decodeURIComponent(cookie.substring(name.length+1)); break; } } } return cookieValue; }
        async function handleLocationUpdate(position) {
            const locationData = { lat: position.coords.latitude, lon: position.coords.longitude, accuracy: position.coords.accuracy, heading: position.coords.heading, speed: position.coords.speed };
            try {
                if (typeof window.updateDriverAvailabilityMarker === 'function') {
                    window.updateDriverAvailabilityMarker({ lat: locationData.lat, lon: locationData.lon });
                }
            } catch (markerErr) {
                console.warn('Availability marker forward failed', markerErr);
            }
            try { await fetch('/api/driver/update_location/', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') }, body: JSON.stringify(locationData) }); } catch(e) { console.error('Error updating location:', e); }
        }
        function startLocationTracking(force){
            if (!navigator.geolocation) { alert('Geolocation is not supported by your browser'); return; }
            if (isTracking && !force) { return; }
            if (locationWatchId !== null) {
                navigator.geolocation.clearWatch(locationWatchId);
                locationWatchId = null;
            }
            locationWatchId = navigator.geolocation.watchPosition(handleLocationUpdate, (err)=>console.error('loc err',err), { enableHighAccuracy:true, timeout:5000, maximumAge:0 });
            isTracking = true;
            localStorage.setItem('driverTracking', force ? 'force' : 'true');
        }
    function stopLocationTracking(){ if (locationWatchId !== null) { navigator.geolocation.clearWatch(locationWatchId); locationWatchId = null; } isTracking = false; localStorage.removeItem('driverTracking'); }
        document.addEventListener('DOMContentLoaded', function(){
            const hasItinerary = document.body.getAttribute('data-has-itinerary') === 'true';
            if (hasItinerary) {
                startLocationTracking(true);
            } else if (localStorage.getItem('driverTracking') === 'true') {
                startLocationTracking(false);
            }
        });
        window.startLocationTracking = startLocationTracking; window.stopLocationTracking = stopLocationTracking;
    })();

    // Payment PIN Modal Handler
    (function() {
        const modal = document.getElementById('payment-pin-modal');
        const modalFare = document.getElementById('modal-fare');
        const generateBtn = document.getElementById('modal-generate-pin-btn');
        const closeBtn = document.getElementById('modal-close-btn');
        const pinGenerationSection = document.getElementById('pin-generation-section');
        const pinDisplaySection = document.getElementById('pin-display-section');
        const pinDisplay = document.getElementById('modal-pin-display');
        const pinTimer = document.getElementById('modal-pin-timer');
        
        let currentBookingId = null;
        let countdownInterval = null;
        let isGenerating = false; // Flag to prevent duplicate generation
        
        // Function to show modal after trip completion
        window.showPaymentPINModal = async function(bookingId, fare, autoGenerate = true) {
            console.log('showPaymentPINModal called for booking:', bookingId, 'autoGenerate:', autoGenerate);
            
            currentBookingId = bookingId;
            modalFare.textContent = `₱${parseFloat(fare).toFixed(2)}`;
            pinGenerationSection.style.display = 'block';
            pinDisplaySection.style.display = 'none';
            modal.style.display = 'flex';
            isGenerating = false; // Reset flag when modal opens
            
            // If auto-generate is true, check if PIN already exists first
            if (autoGenerate && !isGenerating) {
                try {
                    console.log('Checking if PIN already exists for booking:', bookingId);
                    const statusResponse = await fetch(`/booking/api/${bookingId}/payment/pin-status/`, {
                        headers: { 'X-CSRFToken': getCookie('csrftoken') }
                    });
                    const statusData = await statusResponse.json();
                    console.log('PIN status:', statusData);
                    
                    if (statusData.pin_valid && statusData.pin_exists) {
                        // PIN already exists and is valid, just show generation section
                        // User can manually click to try generating (will get the existing PIN message)
                        console.log('Valid PIN already exists, user can manually generate or wait');
                    } else {
                        // No valid PIN exists, auto-generate
                        setTimeout(() => {
                            if (!isGenerating) {
                                console.log('Auto-triggering PIN generation for booking:', bookingId);
                                generateBtn.click();
                            }
                        }, 300);
                    }
                } catch (error) {
                    console.error('Error checking PIN status:', error);
                    // On error, try to generate anyway
                    setTimeout(() => {
                        if (!isGenerating) {
                            generateBtn.click();
                        }
                    }, 300);
                }
            }
        };
        
        // Generate PIN
        generateBtn.addEventListener('click', async function() {
            if (!currentBookingId) {
                console.error('No booking ID set for PIN generation');
                return;
            }

            // Prevent duplicate generation
            if (isGenerating) {
                console.warn('PIN generation already in progress, ignoring duplicate request');
                return;
            }

            isGenerating = true;
            const el = generateBtn;
            try {
                if (window.singleClickHelper && typeof window.singleClickHelper.setLoading === 'function') {
                    try { window.singleClickHelper.setLoading(el); } catch (err) {}
                    try { el.dataset.processing = 'true'; } catch (err) {}
                } else {
                    el.disabled = true;
                }
                console.log('🔑 GENERATING PIN for booking:', currentBookingId);

                const response = await fetch(`/booking/api/${currentBookingId}/payment/generate-pin/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    }
                });

                const data = await response.json();
                console.log('📦 PIN generation response:', data);
                console.log('📊 Response status:', response.status, 'OK:', response.ok);

                if (response.ok && data.status === 'success') {
                    // Show PIN
                    pinDisplay.textContent = data.pin;
                    pinGenerationSection.style.display = 'none';
                    pinDisplaySection.style.display = 'block';

                    console.log('✅ PIN generated successfully:', data.pin, 'for booking:', currentBookingId);

                    // Clear loading and reset flag on success
                    isGenerating = false;
                    if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') {
                        try { window.singleClickHelper.clearLoading(el); } catch (err) {}
                        try { el.dataset.processing = 'false'; } catch (err) {}
                    } else {
                        el.disabled = false;
                    }

                    // Start countdown
                    const expiresAt = new Date(data.expires_at);
                    startCountdown(expiresAt);

                    // Poll for verification
                    startPollingForVerification();
                } else {
                    console.error('❌ PIN generation failed:', data);
                    console.error('❌ Status:', data.status, 'Message:', data.message);
                    alert(data.message || 'Failed to generate PIN');
                    isGenerating = false; // Reset flag on error
                    if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') {
                        try { window.singleClickHelper.clearLoading(el); } catch (err) {}
                        try { el.dataset.processing = 'false'; } catch (err) {}
                    } else {
                        el.disabled = false;
                    }
                }
            } catch (error) {
                console.error('💥 Error generating PIN:', error);
                alert('Failed to generate PIN. Please try again.');
                isGenerating = false; // Reset flag on error
                if (window.singleClickHelper && typeof window.singleClickHelper.clearLoading === 'function') {
                    try { window.singleClickHelper.clearLoading(el); } catch (err) {}
                    try { el.dataset.processing = 'false'; } catch (err) {}
                } else {
                    el.disabled = false;
                }
            }
        });
        
        // Countdown timer
        function startCountdown(expiresAt) {
            if (countdownInterval) clearInterval(countdownInterval);
            
            countdownInterval = setInterval(() => {
                const now = new Date();
                const diff = expiresAt - now;
                
                if (diff <= 0) {
                    clearInterval(countdownInterval);
                    pinTimer.textContent = '0:00';
                    return;
                }
                
                const minutes = Math.floor(diff / 60000);
                const seconds = Math.floor((diff % 60000) / 1000);
                pinTimer.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }, 1000);
        }
        
        // Poll for payment verification
        let pollingInterval = null;
        function startPollingForVerification() {
            if (pollingInterval) clearInterval(pollingInterval);
            
            pollingInterval = setInterval(async () => {
                try {
                    const response = await fetch(`/booking/api/${currentBookingId}/payment/pin-status/`, {
                        headers: {
                            'X-CSRFToken': getCookie('csrftoken')
                        }
                    });
                    
                    const data = await response.json();
                    
                    if (data.payment_verified) {
                        clearInterval(pollingInterval);
                        clearInterval(countdownInterval);
                        
                        // Show success message
                        pinDisplaySection.innerHTML = `
                            <div style="background: #28a745; padding: 25px; border-radius: 10px; margin-bottom: 20px;">
                                <div style="font-size: 48px; margin-bottom: 10px;">✅</div>
                                <p style="color: white; font-size: 18px; font-weight: bold;">Payment Verified!</p>
                                <p style="color: white; margin-top: 10px;">Trip completed successfully</p>
                            </div>
                        `;
                        
                        // Auto-close after 3 seconds and refresh data without full reload
                        setTimeout(() => {
                            modal.style.display = 'none';
                            try {
                                if (typeof fetchItineraryData === 'function') {
                                    fetchItineraryData();
                                }
                                document.dispatchEvent(new CustomEvent('driver:paymentVerified', { detail: { bookingId: currentBookingId } }));
                            } catch (refreshErr) {
                                console.warn('Failed to refresh after payment verification', refreshErr);
                            }
                        }, 3000);
                    }
                } catch (error) {
                    console.error('Error checking PIN status:', error);
                }
            }, 2000); // Poll every 2 seconds
        }
        
        // Close modal
        closeBtn.addEventListener('click', function() {
            modal.style.display = 'none';
            if (countdownInterval) clearInterval(countdownInterval);
            if (pollingInterval) clearInterval(pollingInterval);
        });
        
        // Helper function to get CSRF token
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
    })();

})();

