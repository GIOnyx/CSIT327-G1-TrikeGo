(function () {
    const panels = {
        profile: document.getElementById('driver-profile-panel'),
        wallet: document.getElementById('driver-wallet-panel'),
        history: document.getElementById('driver-history-panel'),
        rides: document.getElementById('driver-rides-panel'),
        stats: document.getElementById('driver-statistics-panel'),
    };

    const bodyClasses = {
        profile: 'profile-panel-open',
        wallet: 'wallet-panel-open',
        history: 'history-panel-open',
        rides: 'rides-panel-open',
        stats: 'stats-panel-open',
    };

    function safeHide(panelKey) {
        const panelEl = panels[panelKey];
        const bodyClass = bodyClasses[panelKey];

        if (panelKey === 'wallet' && typeof window.closeDriverWalletPanel === 'function') {
            window.closeDriverWalletPanel();
            return;
        }
        if (panelKey === 'history' && typeof window.hideDriverHistoryPanel === 'function') {
            window.hideDriverHistoryPanel();
            return;
        }
        if (panelKey === 'rides' && typeof window.closeDriverRidesPanel === 'function') {
            window.closeDriverRidesPanel();
            return;
        }
        if (panelKey === 'stats' && typeof window.closeDriverStatisticsPanel === 'function') {
            window.closeDriverStatisticsPanel();
            return;
        }

        if (panelEl) {
            panelEl.style.display = 'none';
            panelEl.setAttribute('aria-hidden', 'true');
        }
        if (bodyClass) {
            document.body.classList.remove(bodyClass);
        }
    }

    function closeAll(exceptKey) {
        ['profile','wallet', 'history', 'rides', 'stats'].forEach((key) => {
            if (key !== exceptKey) {
                safeHide(key);
            }
        });
    }

    window.DriverPanelManager = {
        closeAll,
        closeProfile: () => safeHide('profile'),
        openProfile: () => { closeAll('profile'); const p = panels.profile; if (p) { p.style.display = 'block'; p.setAttribute('aria-hidden','false'); document.body.classList.add(bodyClasses.profile); } },
        closeWallet: () => safeHide('wallet'),
        closeHistory: () => safeHide('history'),
        closeRides: () => safeHide('rides'),
        closeStats: () => safeHide('stats'),
    };
})();
