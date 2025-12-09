(function(){
    // Driver profile panel behaviors: open/close, save name, toggle status, realtime subscribe via Supabase (if configured)
    const panelId = 'driver-profile-panel';
    const panel = document.getElementById(panelId);
    if (!panel) return;

    const csrftoken = document.body.getAttribute('data-csrf-token');
    const userId = document.body.getAttribute('data-user-id');
    const supabaseUrl = document.body.getAttribute('data-supabase-url');
    const supabaseAnonKey = document.body.getAttribute('data-supabase-anon-key');

    function closePanel(){
        panel.style.display = 'none'; panel.setAttribute('aria-hidden','true'); document.body.classList.remove('profile-panel-open');
        // hide itinerary if we positioned it
        const itinerary = document.getElementById('itinerary-card');
        if (itinerary && itinerary.dataset.moved === '1'){
            itinerary.style.position = '';
            itinerary.style.left = '';
            itinerary.style.top = '';
            itinerary.style.right = '';
            itinerary.style.bottom = '';
            itinerary.style.width = '';
            itinerary.dataset.moved = '0';
            itinerary.classList.remove('panel-aligned');
        }
    }

    function openPanel(){
        // close any other panels first
        if (typeof window.closeAllPanels === 'function') window.closeAllPanels(panelId);
        panel.style.display = 'block'; panel.setAttribute('aria-hidden','false'); document.body.classList.add('profile-panel-open');

        // Move itinerary-card to bottom-right corner to behave like a panel
        try{
            const itinerary = document.getElementById('itinerary-card');
            if (itinerary){
                itinerary.style.position = 'fixed';
                itinerary.style.right = '20px';
                itinerary.style.bottom = '20px';
                itinerary.style.left = '';
                itinerary.style.top = '';
                itinerary.style.width = '360px';
                itinerary.dataset.moved = '1';
                itinerary.classList.add('panel-aligned');
                itinerary.style.zIndex = 1700;
            }
        }catch(e){ console.warn('Could not move itinerary-card', e); }

        // Fetch latest driver profile fields (phone, plate, status) from Supabase if available
        try{
            if (supabaseUrl && supabaseAnonKey){
                fetchDriverProfileFromSupabase();
            }
        }catch(err){ console.warn('Supabase fetch error', err); }
    }

    // Helper: ensure supabase client exists then query likely profile tables for driver info
    async function fetchDriverProfileFromSupabase(){
        try{
            // ensure client
            if (typeof window.supabase === 'undefined'){
                await new Promise((resolve, reject) => {
                    try{
                        const s = document.createElement('script');
                        s.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/supabase.min.js';
                        s.onload = function(){
                            try{ window.supabase = supabase.createClient(supabaseUrl, supabaseAnonKey); }catch(e){}
                            resolve();
                        };
                        s.onerror = function(e){ resolve(); };
                        document.head.appendChild(s);
                    }catch(e){ resolve(); }
                });
            }

            if (typeof window.supabase === 'undefined') return;

            const tables = ['driver_profile','driver_profiles','drivers','profiles','users'];
            for (let t of tables){
                try{
                    // try by driver_id first
                    let q = window.supabase.from(t).select('phone,plate_number,plate,status,name,email,driver_id,user_id').eq('driver_id', userId).limit(1);
                    let res = await q;
                    if ((!res || res.error) && t !== 'users'){
                        // try by user_id
                        res = await window.supabase.from(t).select('phone,plate_number,plate,status,name,email,driver_id,user_id').eq('user_id', userId).limit(1);
                    }
                    if (res && !res.error && Array.isArray(res.data) && res.data.length){
                        const row = res.data[0];
                        try{ if (row.phone){ const phoneEl = document.getElementById('driver-phone-display'); if (phoneEl) phoneEl.textContent = row.phone; } }catch(e){}
                        try{ if (row.plate_number || row.plate){ const plateEl = document.getElementById('driver-plate-display'); if (plateEl) plateEl.textContent = row.plate_number || row.plate; } }catch(e){}
                        try{ if (row.status){ updateStatusUI(row.status); if (statusToggle) statusToggle.checked = (row.status === 'Online'); } }catch(e){}
                        try{ if (row.name){ const nameEl = document.getElementById('driver-name-input'); if (nameEl) nameEl.value = row.name; } }catch(e){}
                        try{ if (row.email){ const emailEl = document.getElementById('driver-email-display'); if (emailEl) emailEl.textContent = row.email; } }catch(e){}
                        break;
                    }
                }catch(e){ /* ignore and try next table */ }
            }
        }catch(err){ console.warn('fetchDriverProfileFromSupabase error', err); }
    }

    const closeBtn = document.getElementById('close-driver-profile-panel');
    if (closeBtn) closeBtn.addEventListener('click', closePanel);

    // Wire up save button
    const saveBtn = document.getElementById('save-driver-name-btn');
    const resetBtn = document.getElementById('reset-driver-name-btn');
    const nameInput = document.getElementById('driver-name-input');

    if (saveBtn && nameInput){
        saveBtn.addEventListener('click', function(){
            saveBtn.disabled = true;
            fetch('/drivers/profile/update-name/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                },
                body: JSON.stringify({ name: nameInput.value.trim() })
            }).then(r=>r.json()).then(data=>{
                if (data.status === 'success'){
                    // show temporary feedback and update UI
                    saveBtn.textContent = 'Saved';
                    setTimeout(()=> saveBtn.textContent = 'Save', 1500);
                } else {
                    alert(data.message || 'Error saving name');
                }
            }).catch(err=>{ console.error(err); alert('Network error'); }).finally(()=>{ saveBtn.disabled = false; });
        });
    }
    if (resetBtn && nameInput){ resetBtn.addEventListener('click', function(){ nameInput.value = nameInput.defaultValue || nameInput.value; }); }

    // Toggle status
    const statusToggle = document.getElementById('driver-status-toggle');
    const statusLabel = document.getElementById('driver-status-label');
    const statusDisplay = document.getElementById('driver-status-display');

    function updateStatusUI(newStatus){ if (statusLabel) statusLabel.textContent = newStatus; if (statusDisplay) statusDisplay.textContent = newStatus; }

    if (statusToggle){
        statusToggle.addEventListener('change', function(){
            const newStatus = statusToggle.checked ? 'Online' : 'Offline';
            fetch('/drivers/profile/toggle-status/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                },
                body: JSON.stringify({ status: newStatus })
            }).then(r=>r.json()).then(data=>{
                if (data.status === 'success'){
                    updateStatusUI(newStatus);
                } else {
                    alert(data.message || 'Error updating status');
                }
            }).catch(err=>{ console.error(err); alert('Network error'); });
        });
    }

    // Opener: prefer explicit profile icon IDs, fallback to first sidebar icon
    const profileIcon = document.getElementById('profile-icon') || document.getElementById('passenger-profile-icon');
    const firstSidebarIcon = document.querySelector('.sidebar .nav-center .nav-icon');
    const opener = profileIcon || firstSidebarIcon;
    if (opener){
        opener.addEventListener('click', function(e){ e.preventDefault(); openPanel(); });
    }

    // Supabase realtime subscription for driver_status table (if configured)
    if (supabaseUrl && supabaseAnonKey && typeof window.supabase === 'undefined'){
        try {
            // load supabase client if needed
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/supabase.min.js';
            script.onload = function(){
                try{
                    window.supabase = supabase.createClient(supabaseUrl, supabaseAnonKey);
                    window.supabase.channel('public:driver_status').on('postgres_changes', { event: '*', schema: 'public', table: 'driver_status' }, payload => {
                        const p = payload.new || payload.record || null;
                        if (!p) return;
                        if (String(p.driver_id) === String(userId)){
                                updateStatusUI(p.status);
                                if (statusToggle) statusToggle.checked = (p.status === 'Online');
                                // update other driver profile fields if present
                                try{
                                    if (p.name){ const nameEl = document.getElementById('driver-name-input'); if (nameEl) { nameEl.value = p.name; } }
                                    if (p.email){ const emailEl = document.getElementById('driver-email-display'); if (emailEl) emailEl.textContent = p.email; }
                                    if (p.phone){ const phoneEl = document.getElementById('driver-phone-display'); if (phoneEl) phoneEl.textContent = p.phone; }
                                    if (p.plate_number || p.plate){ const plateEl = document.getElementById('driver-plate-display'); if (plateEl) plateEl.textContent = p.plate_number || p.plate; }
                                }catch(err){ console.warn('Failed to apply realtime driver fields', err); }
                        }
                    }).subscribe();
                }catch(err){ console.warn('Supabase realtime init failed', err); }
            };
            document.head.appendChild(script);
        } catch (e){ console.warn('Could not load supabase client', e); }
    }
})();