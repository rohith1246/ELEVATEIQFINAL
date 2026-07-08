/**
 * @file alert-override.js
 * @description Drop-in replacement override for native browser alert() dialogs.
 * Integrates a themed, custom glassmorphism modal popup that matches the ElevateIQ dark aesthetic.
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
                background: rgba(4, 10, 24, 0.75);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                display: flex;
                justify-content: center;
                align-items: center;
                opacity: 0;
                transition: opacity 0.25s ease;
                font-family: 'Poppins', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                pointer-events: none;
            }
            .custom-alert-backdrop.show {
                opacity: 1;
                pointer-events: auto;
            }
            .custom-alert-box {
                background: linear-gradient(135deg, #0d1928 0%, #08101b 100%);
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
                background: rgba(63, 208, 255, 0.12);
                color: #3FD0FF;
                border: 1.5px solid rgba(63, 208, 255, 0.3);
            }
            .custom-alert-icon-wrapper.error {
                background: rgba(236, 47, 123, 0.12);
                color: #EC2F7B;
                border: 1.5px solid rgba(236, 47, 123, 0.3);
            }
            .custom-alert-icon-wrapper.info {
                background: rgba(255, 138, 61, 0.12);
                color: #FF8A3D;
                border: 1.5px solid rgba(255, 138, 61, 0.3);
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
                color: #9FB0CC;
                line-height: 1.6;
                margin-bottom: 24px;
                font-weight: 400;
                word-break: break-word;
            }
            .custom-alert-btn {
                background: linear-gradient(90deg, #FF8A3D 0%, #F2701C 100%);
                color: #ffffff;
                border: none;
                border-radius: 12px;
                padding: 12px 32px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
                box-shadow: 0 4px 15px rgba(255, 138, 61, 0.35);
                outline: none;
            }
            .custom-alert-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(255, 138, 61, 0.5);
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

        const isSuccess = ['success', 'successfully', 'saved', 'created', 'updated', 'approved', 'posted', 'deleted', 'resolved', 'sent', 'completed'].some(kw => lowerMsg.includes(kw));
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
            title = 'ElevateIQ Alert';
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
