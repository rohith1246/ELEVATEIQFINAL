const API_BASE = window.location.origin.startsWith('file:') ? "http://localhost:5000" : window.location.origin;
const token = localStorage.getItem("token");
const user = JSON.parse(localStorage.getItem("user") || "null");

let csrfToken = null;
let isRefreshing = false;
let refreshQueue = [];

async function fetchCsrfToken() {
    try {
        const res = await fetch(`${API_BASE}/api/auth/csrf-token`, {
            headers: { "Authorization": `Bearer ${localStorage.getItem("token")}` }
        });
        if (res.ok) {
            const data = await res.json();
            csrfToken = data.csrf_token;
        }
    } catch (e) {
        // silent fail — CSRF not critical for GETs
    }
}

async function refreshAccessToken() {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) return false;
    try {
        const res = await fetch(`${API_BASE}/api/auth/refresh`, {
            method: "POST",
            headers: { "X-Refresh-Token": refreshToken }
        });
        if (res.ok) {
            const data = await res.json();
            localStorage.setItem("token", data.token);
            localStorage.setItem("refresh_token", data.refresh_token);
            if (data.csrf_token) csrfToken = data.csrf_token;
            return true;
        }
    } catch (e) {
        return false;
    }
    return false;
}

async function apiCall(endpoint, method = "GET", body = null) {
    const activeBtn = document.activeElement;
    const isButton = activeBtn && (activeBtn.tagName === 'BUTTON' || (activeBtn.tagName === 'INPUT' && ['submit', 'button'].includes(activeBtn.type)));
    let originalHtml = "";
    if (isButton && !activeBtn.disabled) {
        activeBtn.disabled = true;
        originalHtml = activeBtn.innerHTML;
        if (!activeBtn.querySelector('.spinner')) {
            activeBtn.innerHTML = `<span class="spinner"></span> ` + (activeBtn.textContent.trim() || 'Loading...');
        }
    }

    try {
        const options = {
            method,
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${localStorage.getItem("token")}`
            }
        };
        if (body) options.body = JSON.stringify(body);
        if (csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
            options.headers["X-CSRF-Token"] = csrfToken;
        }

        try {
            const res = await fetch(`${API_BASE}${endpoint}`, options);
            let data = null;
            const contentType = res.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                data = await res.json();
            }
            if (res.status === 401 && !isRefreshing) {
                isRefreshing = true;
                const refreshed = await refreshAccessToken();
                isRefreshing = false;
                if (refreshed) {
                    options.headers["Authorization"] = `Bearer ${localStorage.getItem("token")}`;
                    if (csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
                        options.headers["X-CSRF-Token"] = csrfToken;
                    }
                    const retryRes = await fetch(`${API_BASE}${endpoint}`, options);
                    let retryData = null;
                    const retryContentType = retryRes.headers.get("content-type");
                    if (retryContentType && retryContentType.includes("application/json")) {
                        retryData = await retryRes.json();
                    }
                    if (!retryRes.ok) {
                        const errMsg = (retryData && retryData.error) ? retryData.error : `Request failed with status ${retryRes.status}`;
                        throw new Error(errMsg);
                    }
                    return retryData;
                }
                localStorage.removeItem("token");
                localStorage.removeItem("refresh_token");
                localStorage.removeItem("user");
                localStorage.removeItem("csrf_token");
                window.location.href = "/";
                return;
            }
            if (!res.ok) {
                const errMsg = (data && data.error) ? data.error : `Request failed with status ${res.status}`;
                throw new Error(errMsg);
            }
            return data;
        } catch (err) {
            throw err;
        }
    } finally {
        if (isButton) {
            activeBtn.disabled = false;
            activeBtn.innerHTML = originalHtml;
        }
    }
}

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}

function getPlatformIcon(platform) {
    platform = (platform || '').trim();
    if (platform === 'Zoom') {
        return `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="24" height="24" rx="6" fill="#2D8CFF"/>
                <path d="M6 9C6 8.17157 6.67157 7.5 7.5 7.5H13.5C14.3284 7.5 15 8.17157 15 9V15C15 15.8284 14.3284 16.5 13.5 16.5H7.5C6.67157 16.5 6 15.8284 6 15V9Z" fill="white"/>
                <path d="M16 11L18.5 9.125C19.1667 8.625 20 9.125 20 10V14C20 14.875 19.1667 15.375 18.5 14.875L16 13V11Z" fill="white"/>
            </svg>
        `;
    } else if (platform === 'Google Meet') {
        return `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 6.5C3 5.39543 3.89543 4.5 5 4.5H10.5C11.6046 4.5 12.5 5.39543 12.5 6.5V12H3V6.5Z" fill="#EA4335"/>
                <path d="M3 12H12.5V17.5C12.5 18.6046 11.6046 19.5 10.5 19.5H5C3.89543 19.5 3 18.6046 3 17.5V12Z" fill="#4285F4"/>
                <path d="M12.5 4.5H14.5C15.6046 4.5 16.5 5.39543 16.5 6.5V12H12.5V4.5Z" fill="#FBBC05"/>
                <path d="M12.5 12H16.5V17.5C16.5 18.6046 15.6046 19.5 14.5 19.5H12.5V12Z" fill="#34A853"/>
                <path d="M16.5 11L21 7.5V16.5L16.5 13V11Z" fill="#34A853"/>
            </svg>
        `;
    } else if (platform === 'Microsoft Teams') {
        return `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="24" height="24" rx="6" fill="#464EB8"/>
                <circle cx="9.5" cy="8.5" r="2.5" fill="white" fill-opacity="0.9"/>
                <path d="M5.5 15.5C5.5 13.2909 7.29086 11.5 9.5 11.5H10.5C12.7091 11.5 14.5 13.2909 14.5 15.5V16.5H5.5V15.5Z" fill="white" fill-opacity="0.9"/>
                <circle cx="15" cy="10" r="2" fill="white"/>
                <path d="M12 16.5C12 14.8431 13.3431 13.5 15 13.5H16C17.6569 13.5 19 14.8431 19 16.5V17H12V16.5Z" fill="white"/>
            </svg>
        `;
    } else if (platform === 'Slack') {
        return `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="24" height="24" rx="6" fill="#4A154B"/>
                <g transform="translate(3, 3) scale(0.75)">
                    <rect x="2" y="7" width="6" height="3" rx="1.5" fill="#36C5F0"/>
                    <circle cx="3.5" cy="3.5" r="1.5" fill="#36C5F0"/>
                    <rect x="14" y="2" width="3" height="6" rx="1.5" fill="#2EB67D"/>
                    <circle cx="20.5" cy="3.5" r="1.5" fill="#2EB67D"/>
                    <rect x="16" y="14" width="6" height="3" rx="1.5" fill="#E01E5A"/>
                    <circle cx="20.5" cy="20.5" r="1.5" fill="#E01E5A"/>
                    <rect x="7" y="16" width="3" height="6" rx="1.5" fill="#ECB22E"/>
                    <circle cx="3.5" cy="20.5" r="1.5" fill="#ECB22E"/>
                </g>
            </svg>
        `;
    } else if (platform === 'Webex') {
        return `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="24" height="24" rx="6" fill="#1F57C3"/>
                <circle cx="12" cy="12" r="5" stroke="white" stroke-width="2" stroke-dasharray="6 3" fill="none"/>
                <circle cx="12" cy="12" r="2.5" fill="#00FFD1"/>
            </svg>
        `;
    } else {
        return `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="24" height="24" rx="6" fill="#3A4D62"/>
                <rect x="5" y="7.5" width="14" height="11.5" rx="2" stroke="white" stroke-width="1.5"/>
                <line x1="5" y1="11.5" x2="19" y2="11.5" stroke="white" stroke-width="1.5"/>
                <line x1="8" y1="11.5" x2="8" y2="19" stroke="white" stroke-width="1.5"/>
                <line x1="16" y1="11.5" x2="16" y2="19" stroke="white" stroke-width="1.5"/>
            </svg>
        `;
    }
}

function getPlatformBg(platform) {
    platform = (platform || '').trim();
    if (platform === 'Zoom') return 'rgba(45, 140, 255, 0.12)';
    if (platform === 'Google Meet') return 'rgba(52, 168, 83, 0.12)';
    if (platform === 'Microsoft Teams') return 'rgba(70, 78, 184, 0.12)';
    if (platform === 'Slack') return 'rgba(224, 30, 90, 0.12)';
    if (platform === 'Webex') return 'rgba(31, 87, 195, 0.12)';
    return 'rgba(255, 255, 255, 0.08)';
}

function getPlatformColor(platform) {
    platform = (platform || '').trim();
    if (platform === 'Zoom') return '#4a9cff';
    if (platform === 'Google Meet') return '#4dbb6d';
    if (platform === 'Microsoft Teams') return '#8b93eb';
    if (platform === 'Slack') return '#ec5b84';
    if (platform === 'Webex') return '#5891f7';
    return 'var(--ink-soft)';
}
