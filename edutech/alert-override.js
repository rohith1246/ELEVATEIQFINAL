/**
 * @file alert-override.js
 * @description Drop-in replacement override for native browser alert() dialogs inside the EduTech portal.
 * Integrates a themed, custom glassmorphism modal popup that matches the EduTech branding theme.
 */

(function () {
    // 1. Inject custom modal alert styling dynamically into the document head
    const styleId = "custom-alert-override-styles";
    if (!document.getElementById(styleId)) {
        const style = document.createElement("style");
        style.id = styleId;
        style.textContent = `
            .custom-alert-backdrop {
                position: fixed;
                inset: 0;
                z-index: 999999;
                background: rgba(2, 6, 23, 0.80);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                display: flex;
                justify-content: center;
                align-items: center;
                opacity: 0;
                transition: opacity 0.25s ease;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                pointer-events: none;
            }
            .custom-alert-backdrop.show {
                opacity: 1;
                pointer-events: auto;
            }
            .custom-alert-box {
                background: linear-gradient(135deg, #050b1f 0%, #020617 100%);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 24px;
                width: 90%;
                max-width: 400px;
                padding: 32px 24px;
                text-align: center;
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
                transform: scale(0.9);
                transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
            }
            .custom-alert-backdrop.show .custom-alert-box {
                transform: scale(1);
            }
            .custom-alert-icon-wrapper {
                width: 64px;
                height: 64px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 20px auto;
            }
            .custom-alert-icon-wrapper.success {
                background: rgba(34, 197, 94, 0.12);
                color: #22C55E;
                border: 1.5px solid rgba(34, 197, 94, 0.3);
            }
            .custom-alert-icon-wrapper.error {
                background: rgba(239, 68, 68, 0.12);
                color: #EF4444;
                border: 1.5px solid rgba(239, 68, 68, 0.3);
            }
            .custom-alert-icon-wrapper.info {
                background: rgba(255, 122, 0, 0.12);
                color: #FF7A00;
                border: 1.5px solid rgba(255, 122, 0, 0.3);
            }
            .custom-alert-title {
                font-size: 18px;
                font-weight: 700;
                color: #ffffff;
                margin-bottom: 12px;
                letter-spacing: 0.5px;
            }
            .custom-alert-message {
                font-size: 14px;
                color: #94A3B8;
                line-height: 1.6;
                margin-bottom: 24px;
                font-weight: 400;
                word-break: break-word;
            }
            .custom-alert-btn {
                background: linear-gradient(90deg, #FF7A00 0%, #FF8A00 100%);
                color: #ffffff;
                border: none;
                border-radius: 12px;
                padding: 12px 32px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
                box-shadow: 0 4px 15px rgba(255, 122, 0, 0.35);
                outline: none;
            }
            .custom-alert-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(255, 122, 0, 0.5);
            }
            .custom-alert-btn:active {
                transform: translateY(0);
            }
        `;
        document.head.appendChild(style);
    }

    // Escape function to prevent script injections
    function escapeHTML(str) {
        if (!str) return '';
        return str.replace(/[&<>'"]/g, 
            tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
        );
    }

    // Override the window.alert method
    window.alert = function (message) {
        const lowerMsg = String(message).toLowerCase();
        let type = 'info';
        let title = 'Notification';
        let iconSvg = '';

        const isSuccess = ['success', 'successfully', 'saved', 'created', 'updated', 'approved', 'posted', 'deleted', 'resolved', 'sent', 'completed', 'enrolled'].some(kw => lowerMsg.includes(kw));
        const isError = ['error', 'failed', 'invalid', 'could not', 'cannot', 'failed to', 'unauthorized', 'fail'].some(kw => lowerMsg.includes(kw));

        if (isError) {
            type = 'error';
            title = 'Action Failed';
            iconSvg = `
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
            `;
        } else if (isSuccess) {
            type = 'success';
            title = 'Success';
            iconSvg = `
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
            `;
        } else {
            type = 'info';
            title = 'EduTech Alert';
            iconSvg = `
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                </svg>
            `;
        }

        // Get or construct backdrop overlay
        let backdrop = document.getElementById('custom-alert-backdrop');
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.id = 'custom-alert-backdrop';
            backdrop.className = 'custom-alert-backdrop';
            document.body.appendChild(backdrop);
        }

        // Inject content layout dynamically
        backdrop.innerHTML = `
            <div class="custom-alert-box">
                <div class="custom-alert-icon-wrapper ${type}">
                    ${iconSvg}
                </div>
                <div class="custom-alert-title">${title}</div>
                <div class="custom-alert-message">${escapeHTML(String(message))}</div>
                <button class="custom-alert-btn" id="custom-alert-ok-btn">OK</button>
            </div>
        `;

        // Render transition open
        setTimeout(() => {
            backdrop.classList.add('show');
        }, 10);

        // Accessibilities: Focus the OK button, store previous active focus
        const previousActiveElement = document.activeElement;
        const okBtn = backdrop.querySelector('#custom-alert-ok-btn');
        if (okBtn) {
            okBtn.focus();
        }

        // Clean close helper
        const closeAlert = () => {
            backdrop.classList.remove('show');
            document.removeEventListener('keydown', handleKeyDown);
            if (previousActiveElement && typeof previousActiveElement.focus === 'function') {
                previousActiveElement.focus();
            }
        };

        // Accessibility keydown handler
        const handleKeyDown = (e) => {
            if (e.key === 'Escape' || e.key === 'Enter') {
                e.preventDefault();
                closeAlert();
            }
        };

        // Add listeners
        document.addEventListener('keydown', handleKeyDown);
        okBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            closeAlert();
        });
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                closeAlert();
            }
        });
    };
})();
