(function () {
  const q = document.getElementById("tm-skill-query");
  const hidden = document.getElementById("tm-skill-name");
  const list = document.getElementById("tm-skill-suggestions");
  const status = document.getElementById("tm-reco-status");
  const submit = document.getElementById("tm-skill-submit");
  const form = document.getElementById("tm-skill-form");

  if (!q || !hidden || !list || !status || !submit || !form) return;

  let timer = null;
  let lastQuery = "";
  let selected = null;

  function clearSelection() {
    selected = null;
    hidden.value = "";
    submit.disabled = true;
  }

  function setStatus(text) {
    status.textContent = text;
  }

  function renderSuggestions(items) {
    list.innerHTML = "";
    if (!items || items.length === 0) {
      setStatus("No recommendations");
      return;
    }
    setStatus("Select one to add");
    items.forEach((skill) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tm-reco-item";
      btn.setAttribute("role", "option");
      btn.textContent = skill;

      btn.addEventListener("click", () => {
        // selection is explicit; never auto-map
        selected = skill;
        hidden.value = skill;
        // keep query visible but show chosen canonical in the input as well
        q.value = skill;
        submit.disabled = false;

        // visually mark selected
        [...list.querySelectorAll(".tm-reco-item")].forEach((el) => el.classList.remove("is-selected"));
        btn.classList.add("is-selected");
        setStatus("Selected: " + skill);
      });

      list.appendChild(btn);
    });
  }

  async function fetchSuggestions(query) {
    const res = await fetch(`/api/skills/suggest?q=${encodeURIComponent(query)}`, { headers: { "Accept": "application/json" } });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.suggestions) ? data.suggestions : [];
  }

  q.addEventListener("input", () => {
    const query = (q.value || "").trim();
    // typing clears previous explicit selection
    clearSelection();
    list.innerHTML = "";
    if (query.length < 1) {
      setStatus("Type to see suggestions");
      return;
    }

    // live updates while typing, small debounce to avoid spamming
    if (timer) clearTimeout(timer);
    timer = setTimeout(async () => {
      lastQuery = query;
      setStatus("Loading…");
      try {
        const items = await fetchSuggestions(query);
        // if user typed more, ignore stale results
        if (((q.value || "").trim()) !== lastQuery) return;
        renderSuggestions(items);
      } catch (e) {
        setStatus("Could not load recommendations");
      }
    }, 120);
  });

  form.addEventListener("submit", (e) => {
    // enforce selection: no canonical selected => nothing saved
    if (!hidden.value) {
      e.preventDefault();
      setStatus("Please select a recommended skill before submitting.");
      submit.disabled = true;
    }
  });
})();
