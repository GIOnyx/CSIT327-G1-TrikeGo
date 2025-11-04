(function () {
    const body = document.body;
    if (!body) {
        return;
    }

    const dataset = body.dataset || {};

    const rawUserId = dataset.userId || dataset.userid || '';
    const parsedUserId = rawUserId !== '' ? Number.parseInt(rawUserId, 10) : null;

    window.DRIVER_DASH_CONFIG = {
        ORS_API_KEY: dataset.orsApiKey || '',
        userId: Number.isNaN(parsedUserId) ? null : parsedUserId,
        csrfToken: dataset.csrfToken || '',
        itineraryEndpoint: dataset.itineraryEndpoint || '',
        completeStopEndpoint: dataset.completeStopEndpoint || '',
        availableRidesEndpoint: dataset.availableRidesEndpoint || '',
        acceptRideUrlTemplate: dataset.acceptUrlTemplate || '',
    };
})();
