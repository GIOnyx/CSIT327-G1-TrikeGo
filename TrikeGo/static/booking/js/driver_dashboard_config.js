(function () {
    const body = document.body;
    if (!body) {
        return;
    }

    const dataset = body.dataset || {};

    const rawUserId = dataset.userId || dataset.userid || '';
    const parsedUserId = rawUserId !== '' ? Number.parseInt(rawUserId, 10) : null;

    const rawCsrfToken = dataset.csrfToken || '';
    window.DRIVER_DASH_CONFIG = {
        ORS_API_KEY: dataset.orsApiKey || '',
        userId: Number.isNaN(parsedUserId) ? null : parsedUserId,
        csrfToken: rawCsrfToken && rawCsrfToken !== 'NOTPROVIDED' ? rawCsrfToken : '',
        itineraryEndpoint: dataset.itineraryEndpoint || '',
        completeStopEndpoint: dataset.completeStopEndpoint || '',
        availableRidesEndpoint: dataset.availableRidesEndpoint || '',
        acceptRideUrlTemplate: dataset.acceptUrlTemplate || '',
        driverStatusEndpoint: dataset.driverStatusEndpoint || '',
        driverStatus: dataset.driverStatus || 'Offline',
        hasActiveTrip: dataset.activeTrip === '1',
    };
})();
