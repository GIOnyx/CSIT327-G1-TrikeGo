(function(){
    async function loadPassengerRides(){
        const content = document.getElementById('passenger-rides-content');
        if (!content) return;
        content.innerHTML = '<p style="text-align:center; padding:20px; color:#fff;">Loading your rides...</p>';
        try{
            const res = await fetch('/api/passenger/rides/');
            if (!res.ok) throw new Error('Network response not ok');
            const data = await res.json();
            if (data.status !== 'success' && !Array.isArray(data.rides)){
                content.innerHTML = '<p style="text-align:center; color:#c00;">No rides found.</p>';
                return;
            }
            const rides = data.rides || data.results || [];
            if (!rides.length){
                content.innerHTML = '<p style="text-align:center; color:#fff;">No rides available.</p>';
                return;
            }
            const list = document.createElement('div');
            list.className = 'ride-list';
            rides.forEach(r => {
                const card = document.createElement('div');
                card.className = 'driver-history-card';
                card.style.marginBottom = '10px';
                card.innerHTML = `
                    <div class="driver-history-card__details">
                        <div class="driver-history-card__row"><span class="driver-history-card__label">From</span><span class="driver-history-card__value">${r.pickup_address || r.origin || '—'}</span></div>
                        <div class="driver-history-card__row"><span class="driver-history-card__label">To</span><span class="driver-history-card__value">${r.destination_address || r.destination || '—'}</span></div>
                        <div class="driver-history-card__row"><span class="driver-history-card__label">Status</span><span class="driver-history-card__value">${r.status || r.state || '—'}</span></div>
                        <div class="driver-history-card__row"><span class="driver-history-card__label">Fare</span><span class="driver-history-card__value">${r.fare ? '₱'+r.fare : '--'}</span></div>
                    </div>
                `;
                list.appendChild(card);
            });
            content.innerHTML = '';
            content.appendChild(list);
        }catch(err){
            console.error('Failed to load passenger rides', err);
            content.innerHTML = '<p style="text-align:center; color:#ff8a80;">Error loading rides.</p>';
        }
    }

    document.addEventListener('DOMContentLoaded', function(){
        const icon = document.getElementById('passenger-rides-icon');
        const panel = document.getElementById('passenger-rides-panel');
        const closeBtn = panel ? panel.querySelector('.panel-close') : null;
        if (icon && panel){
            icon.addEventListener('click', function(e){
                e.preventDefault();
                if (typeof window.closeAllPanels === 'function') window.closeAllPanels('passenger-rides-panel');
                panel.style.display = 'block';
                panel.setAttribute('aria-hidden','false');
                loadPassengerRides();
            });
        }
        if (closeBtn){
            closeBtn.addEventListener('click', function(){
                if (panel){ panel.style.display = 'none'; panel.setAttribute('aria-hidden','true'); }
            });
        }
    });
})();
