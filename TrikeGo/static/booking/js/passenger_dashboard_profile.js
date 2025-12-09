document.addEventListener('DOMContentLoaded', function() {

    const profileIcon = document.getElementById('passenger-profile-icon');
    const profilePanel = document.getElementById('passenger-profile-panel');
    const closeProfilePanel = document.getElementById('close-passenger-profile-panel');
    const profileContent = document.getElementById('passenger-profile-content');

    // Redeem section element
    const redeemSection = document.getElementById('redeem-points-section');

    let discountCodes = [];

    async function loadPassengerProfile() {
        if (!profileContent) return;

        profileContent.innerHTML = `<p style="text-align:center; padding:20px;">Loading...</p>`;

        try {
            const response = await fetch('/api/passenger/profile/');
            const data = await response.json();

            if (data.status !== 'success') {
                profileContent.innerHTML = `<p style="text-align:center; color:#c00;">Failed to load profile</p>`;
                if (redeemSection) redeemSection.style.display = 'none';
                return;
            }

            const profile = data.profile;

            profileContent.innerHTML = `
                <div class="driver-history-card-list">
                    <div class="driver-history-card">
                        <div class="driver-history-card__header">
                            <span class="driver-history-card__title">Personal Information</span>
                        </div>
                        <div class="driver-history-card__details">
                            <div class="driver-history-card__row">
                                <span class="driver-history-card__label">Name</span>
                                <span class="driver-history-card__value">${profile.full_name}</span>
                            </div>
                            <div class="driver-history-card__row">
                                <span class="driver-history-card__label">Email</span>
                                <span class="driver-history-card__value">${profile.email}</span>
                            </div>
                            <div class="driver-history-card__row">
                                <span class="driver-history-card__label">Phone</span>
                                <span class="driver-history-card__value">${profile.phone || 'Not set'}</span>
                            </div>
                            <div class="driver-history-card__row">
                                <span class="driver-history-card__label">Loyalty points available</span>
                                <span class="driver-history-card__value" id="redeem-loyalty-points">${profile.loyalty_points}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Now that the element exists, query it
            const redeemPointsDisplay = document.getElementById('redeem-loyalty-points');

            if (redeemSection) {
                redeemSection.style.display = 'block';
                redeemPointsDisplay.textContent = profile.loyalty_points;
            }

            // Fetch available discount codes
            const discountResponse = await fetch('/api/discount_codes/available/');
            const discountData = await discountResponse.json();

            if (discountData.status === 'success') {
                discountCodes = discountData.codes;

                if (redeemSection) {
                    // Remove old dropdown if exists
                    const existingDropdown = document.getElementById('redeem-code-select');
                    if (existingDropdown) existingDropdown.remove();

                    // Create dropdown
                    const dropdown = document.createElement('select');
                    dropdown.id = 'redeem-code-select';
                    dropdown.style.cssText = `
                        width:220px;
                        height:50px;
                        font-size:16px;
                        text-align:center;
                        border:2px solid #ddd;
                        border-radius:8px;
                        margin-bottom:10px;
                    `;

                    const defaultOption = document.createElement('option');
                    defaultOption.value = '';
                    defaultOption.disabled = true;
                    defaultOption.selected = true;
                    defaultOption.textContent = 'Select a discount code';
                    dropdown.appendChild(defaultOption);

                    discountCodes.forEach(dc => {
                        const option = document.createElement('option');
                        option.value = dc.id;
                        option.textContent = `${dc.code} - ${dc.cost} points`;
                        dropdown.appendChild(option);
                    });

                    redeemSection.insertBefore(dropdown, redeemSection.firstChild);

                    // Add redeem button dynamically
                    const redeemBtn = document.createElement('button');
                    redeemBtn.textContent = 'Redeem';
                    redeemBtn.style.cssText = `
                        background:#0f2341;
                        color:white;
                        border:none;
                        padding:12px 25px;
                        font-size:16px;
                        border-radius:8px;
                        cursor:pointer;
                        margin-bottom:10px;
                    `;
                    redeemSection.appendChild(redeemBtn);

                    // Add error & success messages
                    const redeemError = document.createElement('p');
                    redeemError.id = 'redeem-error';
                    redeemError.style.cssText = 'color:#dc3545; display:none; font-size:14px; margin-top:5px;';
                    redeemSection.appendChild(redeemError);

                    const redeemSuccess = document.createElement('div');
                    redeemSuccess.id = 'redeem-success';
                    redeemSuccess.style.cssText = 'display:none; margin-top:20px; color:green; font-weight:bold;';
                    redeemSuccess.textContent = '✅ Points successfully redeemed!';
                    redeemSection.appendChild(redeemSuccess);

                    // Redeem button click
                    redeemBtn.addEventListener('click', async () => {
                        const selectedCodeId = parseInt(dropdown.value, 10);
                        const availablePointsVal = parseInt(redeemPointsDisplay.textContent, 10);

                        if (isNaN(selectedCodeId)) {
                            redeemError.textContent = "Please select a discount code.";
                            redeemError.style.display = 'block';
                            redeemSuccess.style.display = 'none';
                            return;
                        }

                        const selectedCode = discountCodes.find(dc => dc.id === selectedCodeId);
                        if (!selectedCode) {
                            redeemError.textContent = "Invalid discount code.";
                            redeemError.style.display = 'block';
                            redeemSuccess.style.display = 'none';
                            return;
                        }

                        if (availablePointsVal < selectedCode.cost) {
                            redeemError.textContent = "You don't have enough points to redeem this code.";
                            redeemError.style.display = 'block';
                            redeemSuccess.style.display = 'none';
                            return;
                        }

                        try {
                            const response = await fetch(`/api/discount_codes/redeem/${selectedCode.id}/`, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': getCSRFToken(),
                                },
                            });
                            const result = await response.json();

                            if (result.status === 'success') {
                                // Update points display
                                redeemPointsDisplay.textContent = result.remaining_points;
                                redeemSuccess.style.display = 'block';
                                redeemError.style.display = 'none';

                                // Set hidden input in booking form
                                let discountInput = document.getElementById('discount_code_input');
                                if (!discountInput) {
                                    discountInput = document.createElement('input');
                                    discountInput.type = 'hidden';
                                    discountInput.name = 'discount_code_input';
                                    discountInput.id = 'discount_code_input';
                                    const bookingForm = document.querySelector('form#booking-form');
                                    if (bookingForm) {
                                        bookingForm.appendChild(discountInput);
                                    }
                                }
                                discountInput.value = selectedCode.code;

                            } else {
                                redeemError.textContent = result.message || "Failed to redeem points.";
                                redeemError.style.display = 'block';
                                redeemSuccess.style.display = 'none';
                            }
                        } catch (err) {
                            console.error("Error redeeming points:", err);
                            redeemError.textContent = "An error occurred. Please try again.";
                            redeemError.style.display = 'block';
                            redeemSuccess.style.display = 'none';
                        }
                    });
                }
            }

        } catch (error) {
            console.error('Error loading passenger profile:', error);
            profileContent.innerHTML = `<p style="text-align:center; color:#c00;">Error loading profile</p>`;
            if (redeemSection) redeemSection.style.display = 'none';
        }
    }

    // OPEN PROFILE PANEL (close other panels first)
    if (profileIcon) {
        profileIcon.addEventListener('click', function (e) {
            if (typeof window.closeAllPanels === 'function') window.closeAllPanels('passenger-profile-panel');
            profilePanel.style.display = 'block';
            profilePanel.setAttribute('aria-hidden', 'false');
            document.body.classList.add('history-panel-open');
            loadPassengerProfile();
        });
    }

    // CLOSE PROFILE PANEL
    if (closeProfilePanel) {
        closeProfilePanel.addEventListener('click', function () {
            profilePanel.style.display = 'none';
            profilePanel.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('history-panel-open');
        });
    }

    function getCSRFToken() {
    const token = document.querySelector('meta[name="csrf-token"]');
    return token ? token.content : '';
    }

})();
