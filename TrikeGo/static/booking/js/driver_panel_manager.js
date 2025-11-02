(function () {
    const panels = {
        wallet: document.getElementById('driver-wallet-panel'),
        history: document.getElementById('driver-history-panel'),
        rides: document.getElementById('driver-rides-panel'),
    };

    const bodyClasses = {
        wallet: 'wallet-panel-open',
        history: 'history-panel-open',
        rides: 'rides-panel-open',
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

        if (panelEl) {
            panelEl.style.display = 'none';
            panelEl.setAttribute('aria-hidden', 'true');
        }
        if (bodyClass) {
            document.body.classList.remove(bodyClass);
        }
    }

    function closeAll(exceptKey) {
        ['wallet', 'history', 'rides'].forEach((key) => {
            if (key !== exceptKey) {
                safeHide(key);
            }
        });
    }

    window.DriverPanelManager = {
        closeAll,
        closeWallet: () => safeHide('wallet'),
        closeHistory: () => safeHide('history'),
        closeRides: () => safeHide('rides'),
    };
})();
