const bio = document.getElementById("id_bio");
const counter = document.getElementById("bio-count");
const updateCount = () => { counter.textContent = `${bio.value.length} / ${bio.maxLength} characters`; };
counter.hidden = false;
bio.setAttribute("aria-describedby", `${bio.getAttribute("aria-describedby") || ""} ${counter.id}`.trim());
bio.addEventListener("input", updateCount);
updateCount();
