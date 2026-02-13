
const input = document.getElementById("skill-input");
const box = document.getElementById("skill-suggestions");
let selectedSkill = null;

if (input && box) {
  input.addEventListener("input", async () => {
    selectedSkill = null;
    box.innerHTML = "";
    if (input.value.length < 2) return;
    const r = await fetch(`/api/skills/suggest?q=${encodeURIComponent(input.value)}`);
    const d = await r.json();
    d.suggestions.forEach(s => {
      const div = document.createElement("div");
      div.className = "skill-suggestion";
      div.textContent = s;
      div.onclick = () => {
        selectedSkill = s;
        input.value = s;
        box.innerHTML = "";
      };
      box.appendChild(div);
    });
  });
}

async function submitSkill() {
  if (!selectedSkill) {
    alert("Please select a suggested skill.");
    return;
  }
  const r = await fetch("/api/skills/add", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({skill: selectedSkill})
  });
  if (!r.ok) {
    alert("Invalid skill selection.");
  } else {
    location.reload();
  }
}
