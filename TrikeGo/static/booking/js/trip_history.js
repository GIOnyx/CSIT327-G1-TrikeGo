// Trip History Management for Driver and Rider Dashboards
(function() {
    // Driver elements
    const historyIcon = document.getElementById('history-icon');
    const driverHistoryPanel = document.getElementById('driver-history-panel');
    const closeDriverHistoryPanel = document.getElementById('close-driver-history-panel');
    const historyList = document.getElementById('history-trips-list');
    
    // Rider elements  
    const riderHistoryIcon = document.getElementById('rider-history-icon');
    const riderHistoryPanel = document.getElementById('rider-history-panel');
    const closeRiderHistoryPanel = document.getElementById('close-rider-history-panel');
    const riderHistoryList = document.getElementById('rider-history-list');
    
    function getStatusBadge(status) {
        const badges = {
            'pending': '<span style="background:#ffc107;color:#000;padding:2px 8px;border-radius:4px;font-size:11px;">PENDING</span>',
            'accepted': '<span style="background:#17a2b8;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">ACCEPTED</span>',
            'on_the_way': '<span style="background:#007bff;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">ON THE WAY</span>',
            'started': '<span style="background:#28a745;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">STARTED</span>',
            'completed': '<span style="background:#6c757d;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">COMPLETED</span>',
            'cancelled': '<span style="background:#dc3545;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">CANCELLED</span>'
        };
        return badges[status] || status;
    }
    
    function getPaymentBadge(status, verified) {
        if (status !== 'completed') {
            return '<span style="background:#e9ecef;color:#6c757d;padding:2px 8px;border-radius:4px;font-size:11px;">N/A</span>';
        }
        return verified 
            ? '<span style="background:#28a745;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">✅ PAID</span>'
            : '<span style="background:#dc3545;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">⚠️ UNPAID</span>';
    }
    
    async function loadDriverTripHistory() {
        historyList.innerHTML = '<p style="text-align:center;padding:20px;">Loading...</p>';
        try {
            const response = await fetch('/api/driver/trip-history/');
            const data = await response.json();
            if (data.status === 'success' && data.trips.length > 0) {
                let html = '<div style="display:flex;flex-direction:column;gap:12px;">';
                data.trips.forEach(trip => {
                    const needsPayment = trip.status === 'completed' && !trip.paymentVerified;
                    html += `
                        <div style="background:white;padding:14px;border-radius:8px;border:1px solid #dee2e6;box-shadow:0 2px 4px rgba(0,0,0,0.08);">
                            <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
                                <strong style="font-size:14px;color:#0b2340;">Trip #${trip.id}</strong>
                                <span style="font-size:11px;color:#6c757d;">${trip.date}</span>
                            </div>
                            <div style="font-size:12px;color:#495057;margin-bottom:6px;">
                                <strong>Rider:</strong> ${trip.riderName}
                            </div>
                            <div style="font-size:12px;color:#6c757d;margin-bottom:4px;">
                                <strong style="color:#495057;">From:</strong> ${trip.pickup}
                            </div>
                            <div style="font-size:12px;color:#6c757d;margin-bottom:10px;">
                                <strong style="color:#495057;">To:</strong> ${trip.destination}
                            </div>
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                                <span style="font-weight:bold;color:#0b2340;font-size:16px;">₱${trip.fare.toFixed(2)}</span>
                                <div style="display:flex;gap:6px;">
                                    ${getStatusBadge(trip.status)}
                                    ${getPaymentBadge(trip.status, trip.paymentVerified)}
                                </div>
                            </div>
                            ${needsPayment ? `
                                <button onclick="window.showPaymentPINModal(${trip.id}, ${trip.fare})" 
                                        style="width:100%;background:#007bff;color:white;border:none;padding:10px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;">
                                    Generate PIN to Verify Payment
                                </button>
                            ` : ''}
                        </div>
                    `;
                });
                html += '</div>';
                historyList.innerHTML = html;
            } else {
                historyList.innerHTML = '<p style="text-align:center;padding:20px;color:#666;">No trip history yet</p>';
            }
        } catch (error) {
            console.error('Error loading trip history:', error);
            historyList.innerHTML = '<p style="text-align:center;padding:20px;color:#dc3545;">Failed to load trips</p>';
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
                let html = '<div style="display:flex;flex-direction:column;gap:12px;">';
                data.trips.forEach(trip => {
                    const needsPayment = trip.status === 'completed' && !trip.paymentVerified;
                    html += `
                        <div style="background:white;padding:14px;border-radius:8px;border:1px solid #dee2e6;box-shadow:0 2px 4px rgba(0,0,0,0.08);">
                            <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
                                <strong style="font-size:14px;color:#0b2340;">Trip #${trip.id}</strong>
                                <span style="font-size:11px;color:#6c757d;">${trip.date}</span>
                            </div>
                            <div style="font-size:12px;color:#495057;margin-bottom:6px;">
                                <strong>Driver:</strong> ${trip.driverName}
                            </div>
                            <div style="font-size:12px;color:#6c757d;margin-bottom:4px;">
                                <strong style="color:#495057;">From:</strong> ${trip.pickup}
                            </div>
                            <div style="font-size:12px;color:#6c757d;margin-bottom:10px;">
                                <strong style="color:#495057;">To:</strong> ${trip.destination}
                            </div>
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                                <span style="font-weight:bold;color:#0b2340;font-size:16px;">₱${trip.fare.toFixed(2)}</span>
                                <div style="display:flex;gap:6px;">
                                    ${getStatusBadge(trip.status)}
                                    ${getPaymentBadge(trip.status, trip.paymentVerified)}
                                </div>
                            </div>
                            ${needsPayment ? `
                                <button onclick="window.showRiderPaymentPINModal(${trip.id}, ${trip.fare})" 
                                        style="width:100%;background:#28a745;color:white;border:none;padding:10px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;">
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
    
    // Driver history icon handler - Show overlay panel
    if (historyIcon && driverHistoryPanel) {
        historyIcon.addEventListener('click', function(e) {
            e.preventDefault();
            driverHistoryPanel.style.display = 'block';
            
            // Add body class to trigger CSS transitions for itinerary panel
            document.body.classList.add('history-panel-open');
            
            loadDriverTripHistory();
        });
    }
    
    // Close driver panel handler
    if (closeDriverHistoryPanel) {
        closeDriverHistoryPanel.addEventListener('click', function() {
            if (driverHistoryPanel) driverHistoryPanel.style.display = 'none';
            
            // Remove body class to reset itinerary panel position
            document.body.classList.remove('history-panel-open');

        });
    }
    
    // Rider history icon handler - Show overlay panel
    if (riderHistoryIcon && riderHistoryPanel) {
        riderHistoryIcon.addEventListener('click', function(e) {
            e.preventDefault();
            riderHistoryPanel.style.display = 'block';
            // Add body class to shift booking card
            document.body.classList.add('history-panel-open');
            loadRiderTripHistory();
        });
    }
    
    // Close rider panel handler
    if (closeRiderHistoryPanel) {
        closeRiderHistoryPanel.addEventListener('click', function() {
            if (riderHistoryPanel) riderHistoryPanel.style.display = 'none';
            // Remove body class to reset booking card position
            document.body.classList.remove('history-panel-open');
        });
    }
})();
