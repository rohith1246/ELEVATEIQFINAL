// Check Authentication session state
if (!token || !user) {
    window.location.href = "login.html";
}

// Update Greeting
const greetingElem = document.getElementById("userGreeting");
if (greetingElem && user) {
    greetingElem.textContent = `Hello, ${user.name} (${user.role.toUpperCase()})`;
}

// Logout Helper
function logout() {
    localStorage.clear();
    window.location.href = "index.html";
}
