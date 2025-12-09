document.addEventListener('DOMContentLoaded', function(){
    try{
        // Add password visibility toggle for every password input we find on the page
        document.querySelectorAll('input[type="password"]').forEach(function(pwdInput){
            // avoid adding toggle twice
            if (pwdInput.dataset.hasToggle) return;
            pwdInput.dataset.hasToggle = '1';

            // ensure the input's container can be positioned
            const parent = pwdInput.parentNode;
            const wrapper = document.createElement('div');
            wrapper.style.position = 'relative';
            wrapper.style.display = 'inline-block';
            wrapper.style.width = pwdInput.offsetWidth ? pwdInput.offsetWidth + 'px' : '100%';

            // move input into wrapper
            parent.insertBefore(wrapper, pwdInput);
            wrapper.appendChild(pwdInput);

            // style input to take full width of wrapper
            pwdInput.style.boxSizing = 'border-box';
            pwdInput.style.width = '100%';

            const toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.setAttribute('aria-label','Toggle password visibility');
            // Eye SVG icon (same used across auth forms)
            // Eye (visible) and Eye-off (hidden) SVGs
            const eyeSVG = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5C21.27 7.61 17 4.5 12 4.5z" stroke="#000" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="12" r="3" stroke="#000" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
            const eyeOffSVG = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M3 3l18 18" stroke="#000" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M10.58 10.58A3 3 0 0113.42 13.42" stroke="#000" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M14.12 14.12C12.96 15.08 11.53 15.6 10 15.6c-5 0-9.27-3.11-11-7.5a15.27 15.27 0 013.13-4.77" stroke="#000" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
            toggle.innerHTML = eyeSVG;
            // black icon style
            toggle.style.color = '#000';
            toggle.style.fontSize = '16px';
            toggle.style.position = 'absolute';
            toggle.style.right = '10px';
            toggle.style.top = '50%';
            toggle.style.transform = 'translateY(-50%)';
            toggle.style.border = 'none';
            toggle.style.background = 'transparent';
            toggle.style.cursor = 'pointer';
            toggle.style.padding = '0';
            toggle.style.lineHeight = '1';
            wrapper.appendChild(toggle);

            toggle.addEventListener('click', function(){
                if (pwdInput.type === 'password'){
                    pwdInput.type = 'text';
                    toggle.setAttribute('aria-pressed','true');
                    toggle.innerHTML = eyeOffSVG;
                } else {
                    pwdInput.type = 'password';
                    toggle.setAttribute('aria-pressed','false');
                    toggle.innerHTML = eyeSVG;
                }
            });
        });

        // tighten Remember Me spacing across the page
        document.querySelectorAll('label.remember').forEach(function(rememberLabel){
            const cb = rememberLabel.querySelector('input[type="checkbox"]');
            if (cb) cb.style.marginRight = '6px';
            // reduce gap between checkbox and text
            rememberLabel.style.display = 'inline-flex';
            rememberLabel.style.alignItems = 'center';
            rememberLabel.style.gap = '6px';
        });
    }catch(e){ console.warn('login_ui init error', e); }
});
