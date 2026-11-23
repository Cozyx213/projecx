const darkMode = document.getElementById("id_dark_mode");
const preview = document.getElementById("settings-preview");
const form = document.getElementById("settings-form");
const headerToggle = document.getElementById("header-theme-toggle");

const updateTheme = () => {
    if (!darkMode) return;
    const isDark = darkMode.checked;
    document.documentElement.dataset.theme = isDark ? "dark" : "light";
    if (headerToggle) {
        headerToggle.setAttribute("aria-pressed", String(isDark));
        headerToggle.setAttribute(
            "aria-label",
            isDark ? "Switch to light mode" : "Switch to dark mode"
        );
        const icon = headerToggle.querySelector(".theme-icon");
        const label = headerToggle.querySelector(".theme-label");
        if (icon) icon.textContent = isDark ? "☀" : "☾";
        if (label) label.textContent = isDark ? "Light mode" : "Dark mode";
    }
};

if (darkMode) {
    darkMode.addEventListener("change", updateTheme);
    updateTheme();
}

if (form && preview) {
    let saveCounter = 0;
    form.addEventListener("change", async () => {
        const current = ++saveCounter;
        preview.hidden = false;
        preview.textContent = "Saving…";
        try {
            const response = await fetch(form.getAttribute("action") || window.location.pathname, {
                method: "POST",
                body: new URLSearchParams(new FormData(form)),
                credentials: "same-origin",
                keepalive: true,
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            if (current === saveCounter) {
                preview.textContent = "Settings saved.";
            }
        } catch {
            if (current === saveCounter) {
                preview.textContent = "Could not auto-save. Click Save settings to keep your changes.";
            }
        }
    });
}
