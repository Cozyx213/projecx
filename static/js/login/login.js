const toggle = document.getElementById("show-password");
const password = document.getElementById("id_password");
toggle.hidden = false;
toggle.addEventListener("click", () => {
    const show = password.type === "password";
    password.type = show ? "text" : "password";
    toggle.textContent = show ? "Hide password" : "Show password";
    toggle.setAttribute("aria-pressed", String(show));
});
