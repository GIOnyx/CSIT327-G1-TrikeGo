(function () {
    const ridesIcon = document.getElementById('rides-icon');
    const ridesPanel = document.getElementById('driver-rides-panel');
    if (!ridesIcon || !ridesPanel) {
        return;
    }

    const closeButton = document.getElementById('close-driver-rides-panel');

    function closePanel(event) {
        if (event && typeof event.preventDefault === 'function') {
            event.preventDefault();
        }
        ridesPanel.style.display = 'none';
        ridesPanel.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('rides-panel-open');
    }

    function openPanel(event) {
        if (event) {
            event.preventDefault();
        }

        if (window.DriverPanelManager && typeof window.DriverPanelManager.closeAll === 'function') {
            window.DriverPanelManager.closeAll('rides');
        }

        ridesPanel.style.display = 'flex';
        ridesPanel.setAttribute('aria-hidden', 'false');
        document.body.classList.add('rides-panel-open');
    }

    ridesIcon.addEventListener('click', openPanel);
    if (closeButton) {
        closeButton.addEventListener('click', closePanel);
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && ridesPanel.style.display === 'flex') {
            closePanel();
        }
    });

    window.openDriverRidesPanel = openPanel;
    window.closeDriverRidesPanel = closePanel;
})();
