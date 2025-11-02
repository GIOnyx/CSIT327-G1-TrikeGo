# Cash Payment PIN Verification System

## Overview

The TrikeGo app now includes a secure PIN-based verification system for cash payments. This ensures both driver and rider confirm the cash transaction through a "digital handshake" before marking a trip as completed and paid.

## How It Works

### 1. Trip Completion Flow

1. **Driver completes the ride** - The trip must be in "started" status
2. **Driver generates PIN** - A random 4-digit PIN is generated
3. **Driver receives cash** - The rider hands cash to the driver
4. **Driver shares PIN** - Driver verbally tells the PIN to the rider
5. **Rider enters PIN** - Rider enters the PIN in their app
6. **System verifies** - If correct, trip is marked "Completed & Paid"

### 2. Security Features

- **PIN Hashing**: PINs are stored hashed (not plaintext) in the database
- **Expiry Time**: PINs expire after 5 minutes
- **Attempt Limiting**: Maximum 3 incorrect attempts allowed
- **Authorization**: Only assigned driver can generate, only assigned rider can verify
- **Atomic Updates**: Database transactions prevent race conditions
- **Audit Trail**: Timestamps for generation and verification

### 3. API Endpoints

#### Generate Payment PIN (Driver Only)

**Endpoint:** `POST /booking/api/<booking_id>/payment/generate-pin/`

**Authorization:** Must be authenticated as the assigned driver

**Request Body:** `{}` (empty)

**Success Response (200):**
```json
{
    "status": "success",
    "pin": "1234",
    "expires_at": "2025-11-01T12:35:00Z",
    "max_attempts": 3,
    "message": "PIN generated successfully. Please share this PIN with the rider to confirm payment."
}
```

**Error Responses:**
- `400`: PIN already exists and is valid
- `400`: Booking not in "started" status
- `400`: Payment already verified
- `403`: Not the assigned driver
- `404`: Booking not found

---

#### Verify Payment PIN (Rider Only)

**Endpoint:** `POST /booking/api/<booking_id>/payment/verify-pin/`

**Authorization:** Must be authenticated as the assigned rider

**Request Body:**
```json
{
    "pin": "1234"
}
```

**Success Response (200):**
```json
{
    "status": "success",
    "message": "Payment verified successfully! Trip completed.",
    "booking_id": 123,
    "verified_at": "2025-11-01T12:30:00Z",
    "fare": "50.00"
}
```

**Error Responses:**
- `400`: Incorrect PIN (includes attempts remaining)
- `400`: PIN expired
- `400`: Maximum attempts reached
- `400`: No PIN generated yet
- `400`: Payment already verified
- `400`: Invalid PIN format
- `403`: Not the assigned rider
- `404`: Booking not found

---

#### Get PIN Status (Driver or Rider)

**Endpoint:** `GET /booking/api/<booking_id>/payment/pin-status/`

**Authorization:** Must be authenticated as the assigned driver or rider

**Success Response (200):**
```json
{
    "status": "success",
    "pin_exists": true,
    "pin_valid": true,
    "payment_verified": false,
    "expires_at": "2025-11-01T12:35:00Z",
    "attempts_remaining": 3,
    "max_attempts": 3,
    "booking_status": "started",
    "fare": "50.00"
}
```

**Error Responses:**
- `403`: Not the assigned driver or rider
- `404`: Booking not found

---

## Database Schema

### New Fields in `Booking` Model

| Field | Type | Description |
|-------|------|-------------|
| `payment_pin_hash` | CharField(128) | Hashed 4-digit PIN (uses Django password hasher) |
| `payment_pin_created_at` | DateTimeField | When PIN was generated |
| `payment_pin_expires_at` | DateTimeField | PIN expiry time (5 minutes from creation) |
| `payment_pin_attempts` | PositiveSmallIntegerField | Number of failed verification attempts |
| `payment_pin_max_attempts` | PositiveSmallIntegerField | Maximum allowed attempts (default: 3) |
| `payment_verified` | BooleanField | Whether cash payment has been verified |
| `payment_verified_at` | DateTimeField | When payment was verified |

### Model Properties

- **`is_pin_valid`**: Returns `True` if PIN exists, not expired, and attempts remaining
- **`pin_attempts_remaining`**: Returns number of attempts remaining (0 if no PIN)

---

## Usage Examples

### Example 1: Complete Flow (JavaScript/Fetch)

```javascript
// Step 1: Driver generates PIN after ride ends
async function generatePIN(bookingId) {
    const response = await fetch(`/booking/api/${bookingId}/payment/generate-pin/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({})
    });
    
    const data = await response.json();
    if (response.ok) {
        // Display PIN to driver
        showPINToDriver(data.pin, data.expires_at);
    }
}

// Step 2: Rider verifies PIN
async function verifyPIN(bookingId, pin) {
    const response = await fetch(`/booking/api/${bookingId}/payment/verify-pin/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ pin })
    });
    
    const data = await response.json();
    if (response.ok) {
        showSuccess('Payment verified! Trip completed.');
    } else {
        showError(data.message);
    }
}

// Step 3: Check PIN status (polling for updates)
async function checkPINStatus(bookingId) {
    const response = await fetch(`/booking/api/${bookingId}/payment/pin-status/`);
    const data = await response.json();
    
    if (data.payment_verified) {
        showCompletedState();
    } else if (data.pin_exists && data.pin_valid) {
        showPINEntryForm(data.attempts_remaining);
    }
}
```

### Example 2: Python/Django

```python
from booking.utils import generate_payment_pin, hash_payment_pin, verify_payment_pin, get_pin_expiry_time
from django.utils import timezone

# Generate PIN
pin = generate_payment_pin()  # Returns "1234"
pin_hash = hash_payment_pin(pin)

# Save to booking
booking.payment_pin_hash = pin_hash
booking.payment_pin_created_at = timezone.now()
booking.payment_pin_expires_at = get_pin_expiry_time(minutes=5)
booking.payment_pin_attempts = 0
booking.save()

# Verify PIN later
user_input = "1234"
is_valid = verify_payment_pin(user_input, booking.payment_pin_hash)

if is_valid and booking.is_pin_valid:
    booking.payment_verified = True
    booking.payment_verified_at = timezone.now()
    booking.status = 'completed'
    booking.save()
```

---

## UI Recommendations

### Driver UI (After Ride Ends)

```
┌─────────────────────────────────┐
│  Trip Completed!                │
│                                 │
│  Fare: ₱50.00                  │
│                                 │
│  [Generate Payment PIN]         │
│                                 │
│  Share this PIN with rider:     │
│  ┌───────────────────────────┐ │
│  │         1 2 3 4           │ │
│  └───────────────────────────┘ │
│                                 │
│  Expires in: 4:32               │
│                                 │
│  Waiting for rider to          │
│  confirm payment...             │
└─────────────────────────────────┘
```

### Rider UI (After Ride Ends)

```
┌─────────────────────────────────┐
│  Please Pay Driver              │
│                                 │
│  Fare: ₱50.00                  │
│                                 │
│  After paying, enter the        │
│  4-digit PIN from driver:       │
│                                 │
│  ┌─────┬─────┬─────┬─────┐    │
│  │  _  │  _  │  _  │  _  │    │
│  └─────┴─────┴─────┴─────┘    │
│                                 │
│  [Verify Payment]               │
│                                 │
│  Attempts remaining: 3          │
└─────────────────────────────────┘
```

---

## Error Handling

### Common Scenarios

1. **PIN Expired**
   - Driver must generate a new PIN
   - Previous PIN becomes invalid immediately

2. **Maximum Attempts Reached**
   - Driver must generate a new PIN
   - Resets attempt counter

3. **Wrong PIN Entered**
   - Show clear error: "Incorrect PIN. 2 attempts remaining."
   - Don't reveal if PIN exists

4. **Network Error**
   - Retry mechanism recommended
   - Don't increment attempts on network failure

---

## Testing

Run the test suite:

```bash
python manage.py test booking.tests.test_payment_pin
```

### Test Coverage

- ✅ PIN generation (format, uniqueness)
- ✅ PIN hashing and verification
- ✅ Expiry time calculation
- ✅ Model properties (`is_pin_valid`, `pin_attempts_remaining`)
- ✅ API authorization (driver/rider roles)
- ✅ Complete payment flow
- ✅ Error cases (expired, max attempts, wrong PIN)
- ✅ Security (atomic updates, unauthorized access)

---

## Migration

The payment PIN feature requires a database migration:

```bash
python manage.py migrate booking
```

Migration file: `booking/migrations/0009_add_payment_pin_verification.py`

---

## Configuration

Default settings (can be customized in models.py):

- **PIN Length**: 4 digits
- **Expiry Time**: 5 minutes
- **Max Attempts**: 3
- **Hashing Algorithm**: Django's default password hasher (PBKDF2)

---

## Security Considerations

1. **Never log PINs** - Only show PIN in generation response
2. **Use HTTPS** - Prevent PIN interception
3. **Rate limiting** - Consider adding throttling to endpoints
4. **Audit logging** - All generation/verification attempts are timestamped
5. **Session security** - Ensure proper Django session authentication
6. **Database security** - PINs are hashed, but secure your database

---

## Future Enhancements

- SMS/Push notification when PIN is generated
- QR code alternative to manual PIN entry
- Configurable expiry time per booking
- Admin dashboard for payment verification audits
- Dispute resolution workflow
- Multi-currency support with currency symbols

---

## Support

For issues or questions, contact the development team or create an issue in the repository.
