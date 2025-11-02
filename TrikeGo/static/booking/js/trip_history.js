// Trip History Management for Driver and Rider Dashboards
(function() {
    // Driver elements
    const historyIcon = document.getElementById('history-icon');
    const driverHistoryPanel = document.getElementById('driver-history-panel');
    const closeDriverHistoryPanel = document.getElementById('close-driver-history-panel');
    const historyList = document.getElementById('history-trips-list');
    const walletPanel = document.getElementById('driver-wallet-panel');
    const ridesPanel = document.getElementById('driver-rides-panel');
    
    // Rider elements  
    const riderHistoryIcon = document.getElementById('rider-history-icon');
    const riderHistoryPanel = document.getElementById('rider-history-panel');
    const closeRiderHistoryPanel = document.getElementById('close-rider-history-panel');
    const riderHistoryList = document.getElementById('rider-history-list');
    
    function getStatusBadge(status) {
        const mapping = {
            pending: { label: 'Pending', tone: 'warning' },
            accepted: { label: 'Accepted', tone: 'info' },
            on_the_way: { label: 'On the Way', tone: 'info' },
            started: { label: 'In Progress', tone: 'progress' },
            completed: { label: 'Completed', tone: 'success' },
            cancelled: { label: 'Cancelled', tone: 'danger' },
            cancelled_by_rider: { label: 'Cancelled (Rider)', tone: 'danger' },
            cancelled_by_driver: { label: 'Cancelled (Driver)', tone: 'danger' },
            no_driver_found: { label: 'No Driver Found', tone: 'warning' }
        };

        const fallbackLabel = status ? status.replace(/_/g, ' ') : 'Status';
        const config = mapping[status] || { label: fallbackLabel, tone: 'muted' };
        return `<span class="status-badge status-badge--${config.tone}">${config.label.toUpperCase()}</span>`;
    }
    
    function getPaymentBadge(status, verified) {
        if (status !== 'completed') {
            return '<span class="status-badge status-badge--muted">N/A</span>';
        }
        return verified
            ? '<span class="status-badge status-badge--success">PAID</span>'
            : '<span class="status-badge status-badge--danger">UNPAID</span>';
    }

    function formatDistance(kilometers) {
        if (kilometers === null || kilometers === undefined) {
            return '';
        }
        const numeric = Number(kilometers);
        if (!Number.isFinite(numeric)) {
            return '';
        }
        const precision = numeric >= 100 ? 0 : 2;
        return `${numeric.toFixed(precision)} km`;
    }
    
    async function loadDriverTripHistory() {
        historyList.innerHTML = '<p class="driver-history-panel__empty">Loading trip history...</p>';
        try {
            const response = await fetch('/api/driver/trip-history/');
            const data = await response.json();
            if (data.status === 'success' && data.trips.length > 0) {
                let html = '<div class="driver-history-card-list">';
                data.trips.forEach(trip => {
                    const needsPayment = trip.status === 'completed' && !trip.paymentVerified;
                    const distanceDisplay = formatDistance(trip.distanceKm);
                    html += `
                        <div class="driver-history-card">
                            <div class="driver-history-card__header">
                                <span class="driver-history-card__title">Trip #${trip.id}</span>
                                <span class="driver-history-card__date">${trip.date}</span>
                            </div>
                            <div class="driver-history-card__details">
                                <div class="driver-history-card__row">
                                    <span class="driver-history-card__label">rider</span>
                                    <span class="driver-history-card__value">${trip.riderName}</span>
                                </div>
                                <div class="driver-history-card__row">
                                    <span class="driver-history-card__label">from:</span>
                                    <span class="driver-history-card__value">${trip.pickup}</span>
                                </div>
                                <div class="driver-history-card__row">
                                    <span class="driver-history-card__label">to:</span>
                                    <span class="driver-history-card__value">${trip.destination}</span>
                                </div>
                                ${distanceDisplay ? `
                                <div class="driver-history-card__row">
                                    <span class="driver-history-card__label">distance:</span>
                                    <span class="driver-history-card__value">${distanceDisplay}</span>
                                </div>` : ''}
                            </div>
                            <div class="driver-history-card__footer">
                                <span class="driver-history-card__fare">₱${trip.fare.toFixed(2)}</span>
                                <div class="driver-history-card__badges">
                                    ${getStatusBadge(trip.status)}
                                    ${getPaymentBadge(trip.status, trip.paymentVerified)}
                                </div>
                            </div>
                            ${needsPayment ? `
                                <button class="driver-history-card__action" onclick="window.showPaymentPINModal(${trip.id}, ${trip.fare})">
                                    Generate PIN to Verify Payment
                                </button>
                            ` : ''}
                        </div>
                    `;
                });
                html += '</div>';
                historyList.innerHTML = html;
            } else {
                historyList.innerHTML = '<p class="driver-history-panel__empty">No trip history yet</p>';
            }
        } catch (error) {
            console.error('Error loading trip history:', error);
            historyList.innerHTML = '<p class="driver-history-panel__empty" style="color:#c0392b;">Failed to load trips</p>';
        }
    }
    
    async function loadRiderTripHistory() {
        const riderHistoryList = document.getElementById('rider-history-list');
        if (!riderHistoryList) return;
        
        riderHistoryList.innerHTML = '<p style="text-align:center;padding:20px;">Loading...</p>';
        try {
            const response = await fetch('/api/rider/trip-history/');
            const data = await response.json();
            if (data.status === 'success' && data.trips.length > 0) {
                let html = '<div class="driver-history-card-list">';
                data.trips.forEach(trip => {
                    const needsPayment = trip.status === 'completed' && !trip.paymentVerified;
                    const distanceDisplay = formatDistance(trip.distanceKm);
                    html += `
                        <div class="driver-history-card">
                            <div class="driver-history-card__header">
                                <span class="driver-history-card__title">Trip #${trip.id}</span>
                                <span class="driver-history-card__date">${trip.date}</span>
                            </div>
                            <div class="driver-history-card__details">
                                <div class="driver-history-card__row">
                                    <span class="driver-history-card__label">driver</span>
                                    <span class="driver-history-card__value">${trip.driverName}</span>
                                </div>
                                <div class="driver-history-card__row">
                                    <span class="driver-history-card__label">from:</span>
                                    <span class="driver-history-card__value">${trip.pickup}</span>
                                </div>
                                <div class="driver-history-card__row">
                                    <span class="driver-history-card__label">to:</span>
                                    <span class="driver-history-card__value">${trip.destination}</span>
                                </div>
                                ${distanceDisplay ? `
                                <div class="driver-history-card__row">
                                    <span class="driver-history-card__label">distance:</span>
                                    <span class="driver-history-card__value">${distanceDisplay}</span>
                                </div>` : ''}
                            </div>
                            <div class="driver-history-card__footer">
                                <span class="driver-history-card__fare">₱${trip.fare.toFixed(2)}</span>
                                <div class="driver-history-card__badges">
                                    ${getStatusBadge(trip.status)}
                                    ${getPaymentBadge(trip.status, trip.paymentVerified)}
                                </div>
                            </div>
                            ${needsPayment ? `
                                <button class="driver-history-card__action" onclick="window.showRiderPaymentPINModal(${trip.id}, ${trip.fare})">
                                    Enter PIN to Verify Payment
                                </button>
                            ` : ''}
                        </div>
                    `;
                });
                html += '</div>';
                riderHistoryList.innerHTML = html;
            } else {
                riderHistoryList.innerHTML = '<p style="text-align:center;padding:20px;color:#666;">No trip history yet</p>';
            }
        } catch (error) {
            console.error('Error loading trip history:', error);
            riderHistoryList.innerHTML = '<p style="text-align:center;padding:20px;color:#dc3545;">Failed to load trips</p>';
        }
    }
    
    function hideDriverHistoryPanelOverlay() {
        if (!driverHistoryPanel) {
            return;
        }
        driverHistoryPanel.style.display = 'none';
        document.body.classList.remove('history-panel-open');
        driverHistoryPanel.setAttribute('aria-hidden', 'true');
    }

    function showDriverHistoryPanelOverlay() {
        if (!driverHistoryPanel) {
            return;
        }
        driverHistoryPanel.style.display = 'flex';
        document.body.classList.add('history-panel-open');
        driverHistoryPanel.setAttribute('aria-hidden', 'false');
    }

    window.hideDriverHistoryPanel = hideDriverHistoryPanelOverlay;
    window.closeDriverHistoryPanel = hideDriverHistoryPanelOverlay;

    // Driver history icon handler - Show overlay panel
    if (historyIcon && driverHistoryPanel) {
        historyIcon.addEventListener('click', function(e) {
            e.preventDefault();
            if (window.DriverPanelManager && typeof window.DriverPanelManager.closeAll === 'function') {
                window.DriverPanelManager.closeAll('history');
            } else {
                if (typeof window.closeDriverWalletPanel === 'function') {
                    window.closeDriverWalletPanel();
                } else if (walletPanel) {
                    walletPanel.style.display = 'none';
                    walletPanel.setAttribute('aria-hidden', 'true');
                    document.body.classList.remove('wallet-panel-open');
                }
                if (typeof window.closeDriverRidesPanel === 'function') {
                    window.closeDriverRidesPanel();
                } else if (ridesPanel) {
                    ridesPanel.style.display = 'none';
                    ridesPanel.setAttribute('aria-hidden', 'true');
                    document.body.classList.remove('rides-panel-open');
                }
            }

            showDriverHistoryPanelOverlay();
            loadDriverTripHistory();
        });
    }
    
    // Close driver panel handler
    if (closeDriverHistoryPanel) {
        closeDriverHistoryPanel.addEventListener('click', function() {
            hideDriverHistoryPanelOverlay();
        });
    }
    
    // Rider history icon handler - Show overlay panel
    if (riderHistoryIcon && riderHistoryPanel) {
        riderHistoryIcon.addEventListener('click', function(e) {
            e.preventDefault();
            if (typeof window.closeDriverWalletPanel === 'function') {
                window.closeDriverWalletPanel();
            }
            if (window.DriverPanelManager && typeof window.DriverPanelManager.closeAll === 'function') {
                window.DriverPanelManager.closeAll('history');
            } else if (typeof window.closeDriverWalletPanel === 'function') {
                window.closeDriverWalletPanel();
            }
            riderHistoryPanel.style.display = 'block';
            riderHistoryPanel.setAttribute('aria-hidden', 'false');
            document.body.classList.add('history-panel-open');
            loadRiderTripHistory();
        });
    }
    
    // Close rider panel handler
    if (closeRiderHistoryPanel) {
        closeRiderHistoryPanel.addEventListener('click', function() {
            if (riderHistoryPanel) {
                riderHistoryPanel.style.display = 'none';
                riderHistoryPanel.setAttribute('aria-hidden', 'true');
            }
            document.body.classList.remove('history-panel-open');
        });
    }
})();
