// Prevent double submissions while a check is running.
document.querySelectorAll(".run-form").forEach((form) => {
    form.addEventListener("submit", () => {
        const button = form.querySelector("button");
        button.disabled = true;
        button.textContent = "Checking…";
    });
});
