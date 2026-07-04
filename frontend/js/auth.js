/**
 * @file auth.js
 * @description Core client-side session guard. Verifies token validity, handles dynamic greeting rendering, and clears authentication state upon logout.
 */

// Enforcement guard: Redirect unauthenticated requests to login interface
if (!token || !user) {
    window.location.href = "login.html";
}

// Update the user greeting container dynamically
const greetingElem = document.getElementById("userGreeting");
if (greetingElem && user) {
    greetingElem.textContent = `Hello, ${user.name} (${user.role.toUpperCase()})`;
}

/**
 * Clears cached local session state and redirects to the index homepage.
 */
function logout() {
    localStorage.clear();
    window.location.href = "index.html";
}

