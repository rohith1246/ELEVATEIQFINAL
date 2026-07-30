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
 * Clears cached local session state and redirects to the index homepage.
 */
function logout() {
    localStorage.clear();
    window.location.href = "index.html";
}

