const search = document.getElementById("explore-search-input");
const cards = [...document.querySelectorAll(".explore-card")];
const empty = document.getElementById("explore-no-results");

if (search && cards.length && empty) {
    search.addEventListener("input", () => {
        const term = search.value.trim().toLowerCase();
        let shown = 0;
        cards.forEach((card) => {
            const match = !term || (card.dataset.search || "").includes(term);
            card.hidden = !match;
            if (match) shown += 1;
        });
        empty.hidden = shown > 0;
    });
}
