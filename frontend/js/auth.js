const token = localStorage.getItem("token") || localStorage.getItem("edutech_token");
const user = JSON.parse(localStorage.getItem("user") || localStorage.getItem("edutech_user") || "null");

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

