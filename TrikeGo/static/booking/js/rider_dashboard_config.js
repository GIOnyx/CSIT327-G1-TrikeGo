(function () {
    const body = document.body;
    if (!body) {
        return;
    }

    const dataset = body.dataset || {};
    const userIdRaw = dataset.userId || dataset.userid || '';
    const parsedUserId = userIdRaw !== '' ? Number.parseInt(userIdRaw, 10) : null;

    const config = {
        ORS_API_KEY: dataset.orsApiKey || '',
        userId: Number.isNaN(parsedUserId) ? null : parsedUserId,
        csrfToken: dataset.csrfToken || '',
        cancelBookingUrlTemplate: dataset.cancelBookingUrlTemplate || '',
        pendingPaymentBookings: []
    };

    const pendingNodes = document.querySelectorAll('.pending-payment-data');
    config.pendingPaymentBookings = Array.from(pendingNodes)
        .map((node) => {
            const bookingId = Number.parseInt(node.dataset.bookingId, 10);
            const fare = Number.parseFloat(node.dataset.fare || '0');
            return Number.isNaN(bookingId) ? null : {
                id: bookingId,
                fare: Number.isFinite(fare) ? fare : 0
            };
        })
        .filter(Boolean);

    window.PASSENGER_DASH_CONFIG = config;
})();
