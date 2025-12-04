(function () {
    const body = document.body;
    if (!body) {
        return;
    }

    const dataset = body.dataset || {};

    const rawBookingId = dataset.bookingId || dataset.bookingid || '';
    const rawUserId = dataset.userId || dataset.userid || '';

    const parseNumeric = (value) => {
        if (value === '' || value === null || value === undefined) {
            return null;
        }
        const parsed = Number.parseInt(value, 10);
        return Number.isNaN(parsed) ? null : parsed;
    };

    const toBoolean = (value) => String(value).toLowerCase() === 'true';

    window.BOOKING_DETAIL_CONFIG = {
        bookingId: parseNumeric(rawBookingId),
        userId: parseNumeric(rawUserId),
        csrfToken: dataset.csrfToken || '',
        cancelUrl: dataset.cancelUrl || '',
        isPassenger: toBoolean(dataset.isPassenger),
        bookingStatus: dataset.bookingStatus || '',
        paymentVerified: toBoolean(dataset.paymentVerified)
    };
})();
