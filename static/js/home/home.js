const problem = document.getElementById("id_problem_statement");
const counter = document.getElementById("problem-count");
const updateCount = () => { counter.textContent = `${problem.value.length} characters in your problem statement`; };
counter.hidden = false;
problem.parentElement.insertAdjacentElement("afterend", counter);
problem.setAttribute("aria-describedby", counter.id);
problem.addEventListener("input", updateCount);
updateCount();
