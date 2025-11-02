(function () {
	const paymentsIcon = document.getElementById('payments-icon');
	const walletPanel = document.getElementById('driver-wallet-panel');
	if (!paymentsIcon || !walletPanel) {
		return;
	}

	const closeButton = document.getElementById('close-driver-wallet-panel');
	const loader = document.getElementById('wallet-panel-loader');
	const errorBox = document.getElementById('wallet-panel-error');
	const content = document.getElementById('wallet-panel-content');
	const todayTotalEl = document.getElementById('wallet-today-total');
	const todayTripsEl = document.getElementById('wallet-today-trips');
	const lifetimeTotalEl = document.getElementById('wallet-lifetime-total');
	const dailyListEl = document.getElementById('wallet-daily-list');
	const tripsListEl = document.getElementById('wallet-trips-list');
	const historyPanel = document.getElementById('driver-history-panel');
	const ridesPanel = document.getElementById('driver-rides-panel');

	let isLoading = false;

	function escapeHtml(value) {
		return String(value || '')
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;')
			.replace(/'/g, '&#39;');
	}

	function formatCurrency(value) {
		const number = Number(value) || 0;
		return '₱' + number.toLocaleString('en-PH', {
			minimumFractionDigits: 2,
			maximumFractionDigits: 2,
		});
	}

	function pluralizeTrips(count) {
		const safeCount = Number(count) || 0;
		return `${safeCount} trip${safeCount === 1 ? '' : 's'}`;
	}

	function formatDistance(value) {
		if (value === null || value === undefined) {
			return '';
		}
		const numeric = Number(value);
		if (!Number.isFinite(numeric)) {
			return '';
		}
		const precision = numeric >= 100 ? 0 : 2;
		return `${numeric.toFixed(precision)} km`;
	}

	function showLoader() {
		if (loader) {
			loader.style.display = 'flex';
		}
		if (content) {
			content.style.display = 'none';
		}
		hideError();
	}

	function hideLoader() {
		if (loader) {
			loader.style.display = 'none';
		}
	}

	function showError(message) {
		if (!errorBox) {
			return;
		}
		errorBox.textContent = message;
		errorBox.style.display = 'block';
		if (content) {
			content.style.display = 'none';
		}
		hideLoader();
	}

	function hideError() {
		if (!errorBox) {
			return;
		}
		errorBox.textContent = '';
		errorBox.style.display = 'none';
	}

	function renderDailyBreakdown(entries) {
		if (!dailyListEl) {
			return;
		}
		if (!entries || !entries.length) {
			dailyListEl.innerHTML = '<p class="wallet-panel__empty">No completed rides yet.</p>';
			return;
		}

		const html = entries
			.map((entry) => {
				const trips = pluralizeTrips(entry.trip_count);
				return `
					<div class="wallet-daily-item">
						<span>${escapeHtml(entry.date_display || '')}</span>
						<span>${escapeHtml(trips)}</span>
						<span>${formatCurrency(entry.total)}</span>
					</div>
				`;
			})
			.join('');
		dailyListEl.innerHTML = html;
	}

	function renderRecentTrips(entries) {
		if (!tripsListEl) {
			return;
		}
		if (!entries || !entries.length) {
			tripsListEl.innerHTML = '<p class="wallet-panel__empty">Recent trips will appear here once rides are completed.</p>';
			return;
		}

		const html = entries
			.map((trip) => {
				const rider = escapeHtml(trip.rider_name || '—');
				const pickup = escapeHtml(trip.pickup || '—');
				const destination = escapeHtml(trip.destination || '—');
				const completed = escapeHtml(trip.completed_display || '');
				const distance = formatDistance(trip.distance);
				return `
					<div class="wallet-trip-item">
						<div class="wallet-trip-header">
							<span class="wallet-trip-date">${completed}</span>
							<span class="wallet-trip-amount">${formatCurrency(trip.fare)}</span>
						</div>
						<div class="wallet-trip-meta">
							<span class="wallet-trip-rider">${rider}</span>
							<div class="wallet-trip-route">
								<span class="wallet-trip-label">From:</span>
								<span class="wallet-trip-location">${pickup}</span>
							</div>
							<div class="wallet-trip-route">
								<span class="wallet-trip-label">To:</span>
								<span class="wallet-trip-location">${destination}</span>
							</div>
							${distance ? `<span class="wallet-trip-distance">Distance: ${escapeHtml(distance)}</span>` : ''}
						</div>
					</div>
				`;
			})
			.join('');
		tripsListEl.innerHTML = html;
	}

	async function fetchWalletData() {
		if (isLoading) {
			return;
		}
		isLoading = true;
		showLoader();

		try {
			const response = await fetch('/wallet/api/driver/summary/', {
				credentials: 'same-origin',
				headers: {
					'Accept': 'application/json',
				},
			});

			if (!response.ok) {
				throw new Error('Unable to load wallet.');
			}

			const payload = await response.json();
			if (!payload || payload.status !== 'success' || !payload.data) {
				throw new Error('Unexpected wallet response.');
			}

			const data = payload.data;

			if (todayTotalEl) {
				todayTotalEl.textContent = formatCurrency(data.today.total);
			}
			if (todayTripsEl) {
				todayTripsEl.textContent = pluralizeTrips(data.today.trip_count);
			}
			if (lifetimeTotalEl) {
				lifetimeTotalEl.textContent = formatCurrency(data.lifetime_total);
			}

			renderDailyBreakdown(data.daily_breakdown);
			renderRecentTrips(data.recent_trips);

			if (content) {
				content.style.display = 'flex';
			}
		} catch (error) {
			console.error('Driver wallet load failed:', error);
			showError('Unable to load wallet data. Please try again shortly.');
		} finally {
			hideLoader();
			isLoading = false;
		}
	}

	function closeWalletPanel(event) {
		if (event && typeof event.preventDefault === 'function') {
			event.preventDefault();
		}
		walletPanel.style.display = 'none';
		walletPanel.setAttribute('aria-hidden', 'true');
		document.body.classList.remove('wallet-panel-open');
	}

	function openWalletPanel(event) {
		if (event) {
			event.preventDefault();
		}

		if (window.DriverPanelManager && typeof window.DriverPanelManager.closeAll === 'function') {
			window.DriverPanelManager.closeAll('wallet');
		} else if (typeof window.hideDriverHistoryPanel === 'function') {
			window.hideDriverHistoryPanel();
		} else {
			if (historyPanel && historyPanel.style.display === 'block') {
				historyPanel.style.display = 'none';
				document.body.classList.remove('history-panel-open');
			}
			if (ridesPanel && ridesPanel.style.display === 'flex') {
				ridesPanel.style.display = 'none';
				ridesPanel.setAttribute('aria-hidden', 'true');
				document.body.classList.remove('rides-panel-open');
			}
		}

		walletPanel.style.display = 'flex';
		walletPanel.setAttribute('aria-hidden', 'false');
		document.body.classList.add('wallet-panel-open');

		fetchWalletData();
	}

	paymentsIcon.addEventListener('click', openWalletPanel);
	if (closeButton) {
		closeButton.addEventListener('click', closeWalletPanel);
	}

	document.addEventListener('keydown', (event) => {
		if (event.key === 'Escape' && walletPanel.style.display === 'block') {
			closeWalletPanel();
		}
	});

	window.openDriverWalletPanel = openWalletPanel;
	window.closeDriverWalletPanel = closeWalletPanel;
})();
