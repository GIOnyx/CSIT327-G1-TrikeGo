(function () {
    const statsIcon = document.getElementById('statistics-icon');
    const statsPanel = document.getElementById('driver-statistics-panel');
    if (!statsIcon || !statsPanel) {
        return;
    }

    const closeButton = document.getElementById('close-driver-statistics-panel');
    const loader = document.getElementById('driver-statistics-loader');
    const errorBox = document.getElementById('driver-statistics-error');
    const content = document.getElementById('driver-statistics-content');
    const chartImage = document.getElementById('driver-statistics-daily-chart');
    const fallbackList = document.getElementById('driver-statistics-daily-list');
    const ratingMeta = document.getElementById('driver-stats-average-rating-meta');

    const summaryEls = {
        total_rides: document.getElementById('driver-stats-total-rides'),
        completed_rides: document.getElementById('driver-stats-completed-rides'),
        active_rides: document.getElementById('driver-stats-active-rides'),
        cancelled_rides: document.getElementById('driver-stats-cancelled-rides'),
        completion_rate: document.getElementById('driver-stats-completion-rate'),
        cancellation_rate: document.getElementById('driver-stats-cancellation-rate'),
        average_rating: document.getElementById('driver-stats-average-rating'),
        today_earnings: document.getElementById('driver-stats-today-earnings'),
    };

    function showLoader() {
        if (loader) loader.style.display = 'flex';
        if (content) content.style.display = 'none';
        if (errorBox) errorBox.style.display = 'none';
    }

    function showError(message) {
        if (loader) loader.style.display = 'none';
        if (!errorBox) return;
        errorBox.textContent = message || 'Unable to load statistics.';
        errorBox.style.display = 'block';
        if (content) content.style.display = 'none';
    }

    function hideError() {
        if (errorBox) {
            errorBox.style.display = 'none';
            errorBox.textContent = '';
        }
    }

    function showContent() {
        if (loader) loader.style.display = 'none';
        hideError();
        if (content) content.style.display = 'flex';
    }

    function formatPercentage(value) {
        const numeric = Number(value);
        return Number.isFinite(numeric) ? `${numeric.toFixed(1)}%` : '—';
    }

    function formatRating(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric) || numeric <= 0) {
            return '—';
        }
        return `${numeric.toFixed(2)} ★`;
    }

    function renderSummary(summary) {
        if (!summary) {
            Object.values(summaryEls).forEach((el) => {
                if (el) el.textContent = '—';
            });
            if (ratingMeta) {
                ratingMeta.textContent = 'Recent feedback';
            }
            return;
        }

        if (summaryEls.total_rides) {
            summaryEls.total_rides.textContent = summary.total_rides ?? '0';
        }
        if (summaryEls.completed_rides) {
            summaryEls.completed_rides.textContent = summary.completed_rides ?? '0';
        }
        if (summaryEls.active_rides) {
            summaryEls.active_rides.textContent = summary.active_rides ?? '0';
        }
        if (summaryEls.cancelled_rides) {
            summaryEls.cancelled_rides.textContent = summary.cancelled_rides ?? '0';
        }
        if (summaryEls.completion_rate) {
            summaryEls.completion_rate.textContent = formatPercentage(summary.completion_rate);
        }
        if (summaryEls.cancellation_rate) {
            summaryEls.cancellation_rate.textContent = formatPercentage(summary.cancellation_rate);
        }
        if (summaryEls.average_rating) {
            summaryEls.average_rating.textContent = formatRating(summary.average_rating);
        }
        if (summaryEls.today_earnings) {
            const earningsDisplay = summary.earnings_today?.display || '₱0.00';
            summaryEls.today_earnings.textContent = earningsDisplay;
        }
        if (ratingMeta) {
            const sampleSize = Number(summary.ratings_sample_size || 0);
            ratingMeta.textContent = sampleSize > 0
                ? `Recent feedback (${sampleSize})`
                : 'No feedback yet';
        }
    }

    function renderDailyList(labels, values) {
        if (!fallbackList) {
            return;
        }
        fallbackList.innerHTML = '';
        if (!labels || !values || !labels.length || labels.length !== values.length) {
            fallbackList.style.display = 'none';
            return;
        }
        const fragment = document.createDocumentFragment();
        labels.forEach((label, idx) => {
            const item = document.createElement('li');
            item.className = 'driver-statistics-daily-item';
            const value = Number(values[idx] || 0);
            item.innerHTML = `
                <span class="driver-statistics-daily-item__label">${label}</span>
                <span class="driver-statistics-daily-item__value">${value}</span>
            `;
            fragment.appendChild(item);
        });
        fallbackList.appendChild(fragment);
        fallbackList.style.display = 'flex';
    }

    async function fetchStatistics() {
        showLoader();
        try {
            const response = await fetch('/statistics/api/driver/summary/', {
                credentials: 'same-origin',
                headers: {
                    'Accept': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }

            const payload = await response.json();
            if (!payload || payload.status !== 'success' || !payload.data) {
                throw new Error('Unexpected response payload.');
            }

            const { summary, trends } = payload.data;
            renderSummary(summary);

            const chart = trends?.daily_trips;
            const hasChart = Boolean(chart?.chart_image);
            if (chartImage) {
                if (hasChart) {
                    chartImage.src = chart.chart_image;
                    chartImage.style.display = 'block';
                } else {
                    chartImage.removeAttribute('src');
                    chartImage.style.display = 'none';
                }
            }

            if (!hasChart) {
                renderDailyList(chart?.labels, chart?.values);
            } else if (fallbackList) {
                fallbackList.style.display = 'none';
                fallbackList.innerHTML = '';
            }

            showContent();
        } catch (error) {
            console.error('Driver statistics load failed:', error);
            showError('Unable to load statistics. Please try again soon.');
        }
    }

    function closePanel(event) {
        if (event && typeof event.preventDefault === 'function') {
            event.preventDefault();
        }
        statsPanel.style.display = 'none';
        statsPanel.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('stats-panel-open');
    }

    function openPanel(event) {
        if (event) {
            event.preventDefault();
        }

        if (window.DriverPanelManager && typeof window.DriverPanelManager.closeAll === 'function') {
            window.DriverPanelManager.closeAll('stats');
        } else {
            const wallet = document.getElementById('driver-wallet-panel');
            const history = document.getElementById('driver-history-panel');
            const rides = document.getElementById('driver-rides-panel');
            if (wallet) {
                wallet.style.display = 'none';
                wallet.setAttribute('aria-hidden', 'true');
                document.body.classList.remove('wallet-panel-open');
            }
            if (history) {
                history.style.display = 'none';
                history.setAttribute('aria-hidden', 'true');
                document.body.classList.remove('history-panel-open');
            }
            if (rides) {
                rides.style.display = 'none';
                rides.setAttribute('aria-hidden', 'true');
                document.body.classList.remove('rides-panel-open');
            }
        }

        statsPanel.style.display = 'flex';
        statsPanel.setAttribute('aria-hidden', 'false');
        document.body.classList.add('stats-panel-open');
        fetchStatistics();
    }

    statsIcon.addEventListener('click', openPanel);
    if (closeButton) {
        closeButton.addEventListener('click', closePanel);
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && statsPanel.style.display === 'flex') {
            closePanel();
        }
    });

    window.openDriverStatisticsPanel = openPanel;
    window.closeDriverStatisticsPanel = closePanel;
})();
