# Payment PIN Verification - System Flow Diagram

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TRIP COMPLETION & PAYMENT FLOW                        │
└─────────────────────────────────────────────────────────────────────────────┘

    DRIVER SIDE                    SERVER                      RIDER SIDE
    ───────────                    ──────                      ──────────

1. Trip ends (status: 'started')
   │
   │ ┌──────────────┐
   └─┤ End Ride Btn │
     └──────┬───────┘
            │
            ▼
   ┌─────────────────┐
   │ Generate PIN Btn│
   └────────┬────────┘
            │
            ├───────────────►  POST /payment/generate-pin/
            │                         │
            │                         ▼
            │                  ┌──────────────┐
            │                  │ Generate PIN │
            │                  │   "1234"     │
            │                  └──────┬───────┘
            │                         │
            │                         ├─ Hash PIN (PBKDF2)
            │                         ├─ Set expiry (5 min)
            │                         ├─ Reset attempts (0)
            │                         ├─ Save to database
            │                         │
            │                  ┌──────▼───────┐
            │◄─────────────────┤ Return PIN   │
                               │ (plaintext)  │
                               └──────────────┘
            │
            ▼
   ┌─────────────────┐
   │  Display PIN:   │
   │    "1234"       │
   │                 │
   │ Expires: 4:32   │
   └─────────────────┘
            │
            │ (Driver verbally tells
            │  PIN to rider)
            │
            ▼                                           ┌─────────────────┐
   ┌─────────────────┐                                 │ Rider pays cash │
   │ Poll for status │                                 │   ₱50.00        │
   │   (every 2s)    │                                 └────────┬────────┘
   └────────┬────────┘                                          │
            │                                                   ▼
            │                                          ┌─────────────────┐
            │                                          │ Poll for PIN    │
            │                                          │   (every 2s)    │
            │                                          └────────┬────────┘
            │                                                   │
            │                  GET /payment/pin-status/        │
            ├◄─────────────────────────┬────────────────────────┤
            │                          │                        │
            │                   ┌──────▼───────┐               │
            │                   │ Check status │               │
            │                   │ pin_exists?  │               │
            │                   └──────┬───────┘               │
            │                          │                        │
            │                          ├─ YES ────────────────► │
            │                          │                        ▼
            │                          │               ┌─────────────────┐
            │                          │               │  Show PIN entry │
            │                          │               │    [ _ _ _ _ ]  │
            │                          │               └────────┬────────┘
            │                          │                        │
            │                          │                        │ (Rider enters
            │                          │                        │  "1234")
            │                          │                        │
            │                          │                        ▼
            │                          │               ┌─────────────────┐
            │                          │               │ Verify Btn Click│
            │                          │               └────────┬────────┘
            │                          │                        │
            │                  POST /payment/verify-pin/        │
            │                  { "pin": "1234" }               │
            │                          │◄────────────────────────┘
            │                          │
            │                   ┌──────▼───────┐
            │                   │ Verify PIN   │
            │                   │ check_hash() │
            │                   └──────┬───────┘
            │                          │
            │                    ┌─────┴─────┐
            │                    │           │
            │                 CORRECT     INCORRECT
            │                    │           │
            │             ┌──────▼─────┐    │
            │             │ Update DB: │    │
            │             │ - verified │    │
            │             │ - status=  │    │
            │             │   completed│    │
            │             └──────┬─────┘    │
            │                    │           │
            │             ┌──────▼─────┐    ├──────────┐
            │             │ Return     │    │ Increment│
            │             │ Success ✅ │    │ attempts │
            │◄────────────┤            │    │          │
            │             └────────────┘    │ Return   │
            │                               │ Error ❌ │
            │                               │ (2 left) │
            │                               └─────┬────┘
            │                                     │
            ▼                                     ▼
   ┌─────────────────┐               ┌─────────────────┐
   │   ✅ SUCCESS    │               │   ❌ ERROR      │
   │                 │               │                 │
   │ Payment Verified│               │ "Incorrect PIN" │
   │ Trip Completed! │               │ "2 attempts     │
   └─────────────────┘               │  remaining"     │
                                     └─────────────────┘
                                              │
                                              │ (Rider tries
                                              │  again)
                                              │
                                              └──┐
                                                 │
                                        (Max 3 attempts,
                                         then locked)
```

---

## State Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                       BOOKING STATE TRANSITIONS                      │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────┐
  │ PENDING  │  (Booking created)
  └────┬─────┘
       │
       │ driver accepts
       ▼
  ┌──────────┐
  │ ACCEPTED │  (Driver assigned)
  └────┬─────┘
       │
       │ driver arrives
       ▼
  ┌──────────┐
  │ ON_THE_  │  (Driver at pickup)
  │   WAY    │
  └────┬─────┘
       │
       │ trip starts
       ▼
  ┌──────────┐  ◄──── **PIN VERIFICATION HAPPENS HERE**
  │ STARTED  │        
  └────┬─────┘        payment_verified = False
       │              payment_pin_hash = NULL
       │
       │ [Driver clicks "Generate PIN"]
       │
       ├─────► PIN Generated
       │       payment_pin_hash = "hashed_1234"
       │       payment_pin_expires_at = now + 5 min
       │       payment_pin_attempts = 0
       │
       │ [Rider enters correct PIN]
       │
       │ ✅ PIN Verified
       ▼
  ┌──────────┐
  │COMPLETED │  payment_verified = True ✅
  └──────────┘  payment_verified_at = [timestamp]
                end_time = [timestamp]
```

---

## Database State Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      BOOKING MODEL - PIN FIELDS                      │
└─────────────────────────────────────────────────────────────────────┘

INITIAL STATE (Trip started)
┌──────────────────────────────────────┐
│ payment_pin_hash:        NULL        │
│ payment_pin_created_at:  NULL        │
│ payment_pin_expires_at:  NULL        │
│ payment_pin_attempts:    0           │
│ payment_pin_max_attempts: 3          │
│ payment_verified:        False       │
│ payment_verified_at:     NULL        │
│ status:                  'started'   │
└──────────────────────────────────────┘
                │
                │ Driver generates PIN
                ▼
AFTER PIN GENERATION
┌──────────────────────────────────────┐
│ payment_pin_hash:        "pbkdf2..." │ ◄─ Hashed
│ payment_pin_created_at:  2025-11-01  │ ◄─ Timestamp
│                          15:30:00    │
│ payment_pin_expires_at:  2025-11-01  │ ◄─ +5 minutes
│                          15:35:00    │
│ payment_pin_attempts:    0           │
│ payment_pin_max_attempts: 3          │
│ payment_verified:        False       │
│ payment_verified_at:     NULL        │
│ status:                  'started'   │
└──────────────────────────────────────┘
                │
                │ Rider enters wrong PIN
                ▼
AFTER WRONG ATTEMPT
┌──────────────────────────────────────┐
│ payment_pin_hash:        "pbkdf2..." │
│ payment_pin_created_at:  2025-11-01  │
│                          15:30:00    │
│ payment_pin_expires_at:  2025-11-01  │
│                          15:35:00    │
│ payment_pin_attempts:    1           │ ◄─ Incremented
│ payment_pin_max_attempts: 3          │
│ payment_verified:        False       │
│ payment_verified_at:     NULL        │
│ status:                  'started'   │
└──────────────────────────────────────┘
                │
                │ Rider enters correct PIN
                ▼
AFTER SUCCESSFUL VERIFICATION ✅
┌──────────────────────────────────────┐
│ payment_pin_hash:        "pbkdf2..." │
│ payment_pin_created_at:  2025-11-01  │
│                          15:30:00    │
│ payment_pin_expires_at:  2025-11-01  │
│                          15:35:00    │
│ payment_pin_attempts:    1           │
│ payment_pin_max_attempts: 3          │
│ payment_verified:        True        │ ◄─ VERIFIED ✅
│ payment_verified_at:     2025-11-01  │ ◄─ Timestamp
│                          15:32:15    │
│ status:                  'completed' │ ◄─ COMPLETED ✅
└──────────────────────────────────────┘
```

---

## API Endpoint Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        API ENDPOINT FLOW                             │
└─────────────────────────────────────────────────────────────────────┘

ENDPOINT 1: Generate PIN (Driver Only)
═════════════════════════════════════

Request:
  POST /booking/api/123/payment/generate-pin/
  Headers: Cookie: sessionid=xxx
  Body: {}

Validation:
  ├─ User is driver? ──NO──► 403 Forbidden
  ├─ User is assigned driver? ──NO──► 403 Forbidden
  ├─ Booking status is 'started'? ──NO──► 400 Bad Request
  ├─ Already verified? ──YES──► 400 Bad Request
  └─ Valid PIN exists? ──YES──► 400 Bad Request (use existing)

Generate:
  ├─ generate_payment_pin() → "1234"
  ├─ hash_payment_pin("1234") → "pbkdf2_sha256$..."
  ├─ get_pin_expiry_time(5) → 2025-11-01 15:35:00
  └─ Save to database (atomic transaction)

Response:
  200 OK
  {
    "status": "success",
    "pin": "1234",  ◄─── ONLY TIME PIN IS SHOWN IN PLAINTEXT
    "expires_at": "2025-11-01T15:35:00Z",
    "max_attempts": 3
  }


ENDPOINT 2: Verify PIN (Rider Only)
══════════════════════════════════

Request:
  POST /booking/api/123/payment/verify-pin/
  Headers: Cookie: sessionid=xxx
  Body: {"pin": "1234"}

Validation:
  ├─ User is rider? ──NO──► 403 Forbidden
  ├─ User is assigned rider? ──NO──► 403 Forbidden
  ├─ Already verified? ──YES──► 400 Bad Request
  ├─ PIN exists? ──NO──► 400 Bad Request
  ├─ PIN expired? ──YES──► 400 Bad Request
  ├─ Max attempts reached? ──YES──► 400 Bad Request
  └─ PIN format valid (4 digits)? ──NO──► 400 Bad Request

Verify:
  ├─ verify_payment_pin("1234", hash)
  │
  ├─ IF CORRECT:
  │   ├─ Set payment_verified = True
  │   ├─ Set payment_verified_at = now
  │   ├─ Set status = 'completed'
  │   ├─ Set end_time = now
  │   └─ Return success
  │
  └─ IF INCORRECT:
      ├─ Increment payment_pin_attempts
      └─ Return error with attempts remaining

Response (Success):
  200 OK
  {
    "status": "success",
    "message": "Payment verified successfully!",
    "booking_id": 123,
    "verified_at": "2025-11-01T15:32:15Z",
    "fare": "50.00"
  }

Response (Error):
  400 Bad Request
  {
    "status": "error",
    "message": "Incorrect PIN. 2 attempt(s) remaining.",
    "attempts_remaining": 2
  }


ENDPOINT 3: Get PIN Status (Driver or Rider)
════════════════════════════════════════════

Request:
  GET /booking/api/123/payment/pin-status/

Validation:
  └─ User is driver or rider? ──NO──► 403 Forbidden

Response:
  200 OK
  {
    "status": "success",
    "pin_exists": true,
    "pin_valid": true,
    "payment_verified": false,
    "expires_at": "2025-11-01T15:35:00Z",
    "attempts_remaining": 3,
    "max_attempts": 3,
    "booking_status": "started",
    "fare": "50.00"
  }
```

---

## Security Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SECURITY MEASURES                             │
└─────────────────────────────────────────────────────────────────────┘

1. AUTHENTICATION
   ├─ Django session authentication required
   └─ No anonymous access allowed

2. AUTHORIZATION (Role-Based)
   ├─ Generate PIN: Only assigned driver
   ├─ Verify PIN: Only assigned rider
   └─ Check status: Driver or rider only

3. PIN HASHING
   ├─ Algorithm: PBKDF2 with SHA256
   ├─ Never stored in plaintext
   └─ Only shown once (in generation response)

4. EXPIRY TIME
   ├─ Default: 5 minutes
   ├─ Checked on every verification attempt
   └─ Expired PINs cannot be used

5. ATTEMPT LIMITING
   ├─ Max attempts: 3 (default)
   ├─ Counter incremented on each wrong attempt
   └─ Locked after max attempts reached

6. ATOMIC TRANSACTIONS
   ├─ Uses select_for_update() for locking
   ├─ Prevents race conditions
   └─ Ensures data consistency

7. INPUT VALIDATION
   ├─ PIN format: Exactly 4 digits
   ├─ Booking status: Must be 'started'
   └─ Prevents injection attacks

8. AUDIT TRAIL
   ├─ payment_pin_created_at: When generated
   ├─ payment_verified_at: When verified
   └─ All attempts logged via payment_pin_attempts

┌───────────────────────────────────────┐
│  THREAT          │  MITIGATION        │
├───────────────────────────────────────┤
│ PIN interception │ HTTPS required     │
│ Brute force      │ 3 attempts max     │
│ Replay attack    │ 5-minute expiry    │
│ Database breach  │ Hashed storage     │
│ Unauthorized     │ Role-based auth    │
│ Race conditions  │ Atomic transactions│
└───────────────────────────────────────┘
```

---

## Timeline Example

```
T+0:00  │ Trip ends, driver clicks "End Ride"
        │ Booking status: 'started'
        │
T+0:05  │ Driver clicks "Generate PIN"
        │ Server: Generates PIN "1234"
        │ Server: Hashes and stores with expiry T+5:05
        │ Driver: Sees PIN "1234" on screen
        │
T+0:10  │ Driver verbally tells rider: "PIN is 1234"
        │
T+0:15  │ Rider hands ₱50 cash to driver
        │
T+0:20  │ Rider enters "1234" in app
        │ Rider clicks "Verify Payment"
        │
T+0:21  │ Server: Verifies PIN ✅
        │ Server: Updates booking
        │         - payment_verified = True
        │         - status = 'completed'
        │         - end_time = T+0:21
        │
T+0:22  │ Both driver and rider see success message
        │ Trip completed! 🎉
        │
        │
        └─────────────────────────────────────►
          0        1        2        3        4        5 minutes
          ├────────┼────────┼────────┼────────┼────────┤
          Generate                              Expire
          PIN                                   (if not used)
```

---

## Error Scenarios

```
SCENARIO 1: Wrong PIN
─────────────────────
Attempt 1: "0000" → ❌ "Incorrect. 2 attempts remaining"
Attempt 2: "9999" → ❌ "Incorrect. 1 attempt remaining"
Attempt 3: "5555" → ❌ "Maximum attempts reached"
→ Driver must regenerate PIN


SCENARIO 2: PIN Expired
────────────────────────
T+0:00: PIN generated, expires at T+5:00
T+5:30: Rider tries to verify
→ ❌ "PIN expired. Ask driver for new PIN"
→ Driver regenerates PIN


SCENARIO 3: Already Verified
─────────────────────────────
Payment already verified
Driver tries to generate PIN
→ ❌ "Payment already verified"

Rider tries to verify again
→ ❌ "Payment already verified"


SCENARIO 4: Wrong User
──────────────────────
Rider tries to generate PIN
→ ❌ 403 Forbidden "Only drivers can generate"

Driver tries to verify PIN
→ ❌ 403 Forbidden "Only riders can verify"

Other rider tries to verify
→ ❌ 403 Forbidden "Not assigned rider"
```

This diagram should help visualize the complete system!
