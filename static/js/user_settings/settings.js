const darkMode = document.getElementById("id_dark_mode");
const preview = document.getElementById("settings-preview");
const form = document.getElementById("settings-form");
const headerToggle = document.getElementById("header-theme-toggle");

if (darkMode) {
    const updateTheme = () => {
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
    darkMode.addEventListener("change", updateTheme);
    updateTheme();
}

if (form && preview) {
    form.addEventListener("change", () => {
        preview.hidden = false;
        preview.textContent = "Previewing changes. Click Save settings to keep them.";
    });
}
