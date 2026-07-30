function getStoredSession() {
    let token = localStorage.getItem("token") || localStorage.getItem("edutech_token") ||
                sessionStorage.getItem("token") || sessionStorage.getItem("edutech_token");
    let userStr = localStorage.getItem("user") || localStorage.getItem("edutech_user") ||
                  sessionStorage.getItem("user") || sessionStorage.getItem("edutech_user");

    if (!token) {
        const match = document.cookie.match(/(?:^|; )token=([^;]*)/);
        if (match) token = decodeURIComponent(match[1]);
    }
    if (!userStr) {
        const match = document.cookie.match(/(?:^|; )user=([^;]*)/);
        if (match) userStr = decodeURIComponent(match[1]);
    }

    let user = null;
    try {
        if (userStr) user = JSON.parse(userStr);
    } catch(e) {}

    return { token, user };
}

const { token, user } = getStoredSession();

// Enforcement guard: Redirect unauthenticated requests on protected pages to login interface
const currentPath = window.location.pathname.toLowerCase();
const isPublicPage = currentPath.endsWith("login.html") || 
                     currentPath.endsWith("register.html") || 
                     currentPath.endsWith("forgot-password.html") || 
                     currentPath.endsWith("reset-password.html") || 
                     currentPath.endsWith("index.html") || 
                     currentPath === "/" || 
                     currentPath.endsWith("/edutech/");

if ((!token || !user) && !isPublicPage) {
    window.location.href = "login.html";
}

// Update the user greeting container dynamically
const greetingElem = document.getElementById("userGreeting");
if (greetingElem && user) {
    greetingElem.textContent = `Hello, ${user.name} (${(user.role || 'User').toUpperCase()})`;
}

/**
 * Clears all cached session tokens, user data, and cookies across local storage, 
 * session storage, and document cookies before redirecting to login.html.
 */
async function logout(e) {
    if (e && e.preventDefault) e.preventDefault();
    try {
        const activeToken = localStorage.getItem("token") || sessionStorage.getItem("token");
        const apiBase = (typeof API_BASE !== 'undefined') ? API_BASE : (window.location.origin.startsWith('file:') ? "http://localhost:5000" : window.location.origin);
        if (activeToken) {
            await fetch(`${apiBase}/logout`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${activeToken}` }
            }).catch(() => {});
        }
    } catch(err) {}

    localStorage.clear();
    sessionStorage.clear();

    const cookieList = document.cookie.split(";");
    for (let i = 0; i < cookieList.length; i++) {
        const cookie = cookieList[i];
        const eqPos = cookie.indexOf("=");
        const name = eqPos > -1 ? cookie.substr(0, eqPos).trim() : cookie.trim();
        if (name) {
            document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC; max-age=0; SameSite=Lax`;
        }
    }

    window.location.href = "login.html";
}


