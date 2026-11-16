const toggle = document.getElementById("show-passwords");
const passwords = document.querySelectorAll('#register-form input[type="password"]');
toggle.hidden = false;
toggle.addEventListener("click", () => {
    const show = passwords[0].type === "password";
    passwords.forEach((input) => { input.type = show ? "text" : "password"; });
    toggle.textContent = show ? "Hide passwords" : "Show passwords";
    toggle.setAttribute("aria-pressed", String(show));
});
