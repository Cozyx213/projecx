const search = document.getElementById("project-search");
if (search) {
    const cards = [...document.querySelectorAll(".project-card")];
    const empty = document.getElementById("no-results");
    search.parentElement.hidden = false;
    search.addEventListener("input", () => {
        const term = search.value.trim().toLowerCase();
        let shown = 0;
        cards.forEach((card) => {
            card.hidden = !card.dataset.search.includes(term);
            if (!card.hidden) shown += 1;
        });
        empty.hidden = shown > 0;
    });
}

const proposal = document.getElementById("proposal-form");
if (proposal) {
    const fields = [...proposal.querySelectorAll("input[type=text], textarea")];
    const progress = document.getElementById("proposal-progress");
    const update = () => {
        const filled = fields.filter((field) => field.value.trim()).length;
        progress.textContent = `${filled} of ${fields.length} sections filled in`;
    };
    progress.hidden = false;
    proposal.addEventListener("input", update);
    update();
}
