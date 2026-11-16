// Bars are sized from data-score so the page needs no inline styles.
document.querySelectorAll(".score-bar span").forEach((bar) => {
    requestAnimationFrame(() => { bar.style.width = `${bar.dataset.score}%`; });
});

document.querySelectorAll(".run-form").forEach((form) => {
    form.addEventListener("submit", () => {
        const button = form.querySelector("button");
        button.disabled = true;
        button.textContent = "Checking…";
    });
});
