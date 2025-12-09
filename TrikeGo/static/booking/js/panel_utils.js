// Utility to close/open sidebar panels across dashboards
(function(){
    function closeAllPanels(exceptId){
        try{
            document.querySelectorAll('[id$="-panel"]').forEach(function(el){
                if (!exceptId || el.id !== exceptId){
                    el.style.display = 'none';
                    el.setAttribute('aria-hidden','true');
                }
            });
        }catch(e){ console.warn('closeAllPanels error', e); }
        // ensure the excepted panel (if any) is above others
        try{
            if (exceptId){
                var keep = document.getElementById(exceptId);
                if (keep){
                    keep.style.zIndex = 1750;
                    keep.style.display = 'block';
                    keep.setAttribute('aria-hidden','false');
                }
            }
        }catch(e){}
        // If the itinerary card was moved beside the profile, reset it when closing other panels
        try{
            const itinerary = document.getElementById('itinerary-card');
            if (itinerary && itinerary.dataset.moved === '1' && exceptId !== 'driver-profile-panel'){
                itinerary.style.position = '';
                itinerary.style.left = '';
                itinerary.style.top = '';
                itinerary.style.width = '';
                itinerary.dataset.moved = '0';
                itinerary.classList.remove('panel-aligned');
            }
        }catch(e){}
        // also call DriverPanelManager closeAll if present
        try{ if (window.DriverPanelManager && typeof window.DriverPanelManager.closeAll === 'function') window.DriverPanelManager.closeAll(exceptId && exceptId.replace('-panel','')); }catch(e){}
        }

        // Attach close button handlers for any .panel-close buttons
        function initCloseButtons(){
            document.querySelectorAll('.panel-close').forEach(function(btn){
                if (btn.dataset.bound) return;
                btn.dataset.bound = '1';
                btn.addEventListener('click', function(e){
                    e.preventDefault();
                    // find nearest panel ancestor with id ending in -panel
                    var el = btn;
                    var panel = null;
                    while(el && el !== document.body){
                        if (el.id && el.id.slice(-6) === '-panel') { panel = el; break; }
                        el = el.parentElement;
                    }
                    if (panel){ panel.style.display = 'none'; panel.setAttribute('aria-hidden','true'); }
                    // reset itinerary if moved
                    try{
                        var itinerary = document.getElementById('itinerary-card');
                        if (itinerary && itinerary.dataset.moved === '1'){
                            itinerary.style.position = '';
                            itinerary.style.left = '';
                            itinerary.style.top = '';
                            itinerary.style.width = '';
                            itinerary.dataset.moved = '0';
                            itinerary.classList.remove('panel-aligned');
                        }
                    }catch(e){}
                });
            });
        }

        document.addEventListener('DOMContentLoaded', initCloseButtons);

        window.closeAllPanels = closeAllPanels;
    })();
