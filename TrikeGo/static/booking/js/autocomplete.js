(function () {
    const DEFAULT_API_KEY = '5b3ce3597851110001cf62488c26abeb';

    function resolveApiKey() {
        const body = document.body;
        if (body && body.dataset && body.dataset.orsApiKey) {
            const trimmed = body.dataset.orsApiKey.trim();
            if (trimmed.length > 0) {
                return trimmed;
            }
        }
        return DEFAULT_API_KEY;
    }

    class ORSAutocomplete {
        constructor(inputEl, resultsEl, hiddenLatId, hiddenLonId, apiKey) {
            this.input = inputEl;
            this.results = resultsEl;
            this.hiddenLat = document.getElementById(hiddenLatId);
            this.hiddenLon = document.getElementById(hiddenLonId);
            this.timeout = null;
            this.apiKey = apiKey;
            this.bind();
        }

        bind() {
            if (!this.input) {
                return;
            }

            this.input.addEventListener('input', (event) => {
                clearTimeout(this.timeout);
                const query = event.target.value.trim();
                if (query.length < 3) {
                    this.clearResults();
                    return;
                }
                this.showSearching();
                this.timeout = window.setTimeout(() => {
                    this.search(query).catch((error) => {
                        console.error('ORS autocomplete search failed:', error);
                        this.results.innerHTML = '<div class="autocomplete-item">Unable to fetch suggestions.</div>';
                    });
                }, 300);
            });
        }

        clearResults() {
            if (this.results) {
                this.results.innerHTML = '';
            }
        }

        showSearching() {
            if (this.results) {
                this.results.innerHTML = '<div class="autocomplete-item">Searching...</div>';
            }
        }

        async search(query) {
            if (!this.results) {
                return;
            }

            const params = new URLSearchParams({
                api_key: this.apiKey,
                text: query,
                size: '12',
                'boundary.country': 'PH',
                layers: 'address'
            });

            const response = await fetch(`https://api.openrouteservice.org/geocode/search?${params.toString()}`);
            if (!response.ok) {
                throw new Error(`ORS response ${response.status}`);
            }

            const data = await response.json();
            const features = (data && data.features) || [];
            this.renderResults(features);
        }

        renderResults(features) {
            if (!this.results) {
                return;
            }

            this.results.innerHTML = '';

            if (!features.length) {
                const empty = document.createElement('div');
                empty.className = 'autocomplete-item';
                empty.textContent = 'No matches found.';
                this.results.appendChild(empty);
                return;
            }

            features.forEach((feature) => {
                const div = document.createElement('div');
                const props = feature.properties || {};

                div.className = 'autocomplete-item';
                div.textContent = props.label || props.name || 'Unknown';
                div.addEventListener('click', () => this.select(feature));

                this.results.appendChild(div);
            });
        }

        select(feature) {
            if (!feature || !feature.geometry || !Array.isArray(feature.geometry.coordinates)) {
                return;
            }

            const [lon, lat] = feature.geometry.coordinates;
            const props = feature.properties || {};
            let label = props.label || props.name || '';

            if (!label && props.street) {
                label = props.street;
            }
            if (!label) {
                label = `${lat}, ${lon}`;
            }

            if (this.input) {
                const current = this.input.value || '';
                if (current.trim() === label.trim()) {
                    label = `${label} (${lat.toFixed(5)}, ${lon.toFixed(5)})`;
                }
                this.input.value = label;
            }

            if (this.hiddenLat) {
                this.hiddenLat.value = lat;
            }
            if (this.hiddenLon) {
                this.hiddenLon.value = lon;
            }
            this.clearResults();
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        const apiKey = resolveApiKey();
        const pickupInput = document.getElementById('pickup_location_input');
        const pickupResults = document.getElementById('pickup-results');
        const destinationInput = document.getElementById('destination_location_input');
        const destinationResults = document.getElementById('destination-results');

        if (pickupInput && pickupResults) {
            new ORSAutocomplete(pickupInput, pickupResults, 'id_pickup_latitude', 'id_pickup_longitude', apiKey);
        }
        if (destinationInput && destinationResults) {
            new ORSAutocomplete(destinationInput, destinationResults, 'id_destination_latitude', 'id_destination_longitude', apiKey);
        }
    });
})();
