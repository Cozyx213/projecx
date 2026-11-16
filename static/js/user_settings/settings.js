const darkMode = document.getElementById("id_dark_mode");
const preview = document.getElementById("settings-preview");
const updateTheme = () => { document.documentElement.dataset.theme = darkMode.checked ? "dark" : "light"; };
darkMode.addEventListener("change", updateTheme);
document.getElementById("settings-form").addEventListener("change", () => {
    preview.hidden = false;
    preview.textContent = "You have unsaved changes. Save settings to keep them.";
});
updateTheme();
