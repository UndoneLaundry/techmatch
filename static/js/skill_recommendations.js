(function () {
  function initPicker(root) {
    const queryInput = root.querySelector(".js-skill-query");
    const hiddenInput = root.querySelector(".js-skill-name");
    const list = root.querySelector(".js-skill-list");
    const status = root.querySelector(".js-skill-status");
    const submit = root.querySelector(".js-skill-submit");
    const form =
      root.tagName.toLowerCase() === "form" ? root : root.querySelector("form");

    if (!queryInput || !hiddenInput || !list || !status || !submit || !form) {
      return;
    }

    let timer = null;
    let lastQuery = "";

    function clearSelection() {
      hiddenInput.value = "";
      submit.disabled = true;
      list
        .querySelectorAll(".tm-reco-item.is-selected")
        .forEach((el) => el.classList.remove("is-selected"));
    }

    function setStatus(text) {
      status.textContent = text;
    }

    function renderSuggestions(items) {
      list.innerHTML = "";

      if (!items || items.length === 0) {
        setStatus("Type to see suggestions");
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
          hiddenInput.value = skill;
          queryInput.value = skill;
          submit.disabled = false;

          list
            .querySelectorAll(".tm-reco-item")
            .forEach((el) => el.classList.remove("is-selected"));
          btn.classList.add("is-selected");

          setStatus(`Selected: ${skill}`);
        });

        list.appendChild(btn);
      });
    }

    async function fetchSuggestions(query) {
      const res = await fetch(
        `/api/skills/suggest?q=${encodeURIComponent(query)}`,
        {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        }
      );

      if (!res.ok) {
        throw new Error("Failed to fetch suggestions");
      }

      const data = await res.json();
      return Array.isArray(data.suggestions) ? data.suggestions : [];
    }

    queryInput.addEventListener("input", () => {
      const query = (queryInput.value || "").trim();
      clearSelection();
      list.innerHTML = "";

      if (query.length === 0) {
        setStatus("Type to see suggestions");
        return;
      }

      if (timer) clearTimeout(timer);

      timer = setTimeout(async () => {
        lastQuery = query;
        setStatus("Loading…");

        try {
          const items = await fetchSuggestions(query);

          // Ignore stale responses
          if ((queryInput.value || "").trim() !== lastQuery) return;

          renderSuggestions(items);
        } catch (err) {
          console.error(err);
          setStatus("Could not load recommendations");
        }
      }, 120);
    });

    form.addEventListener("submit", (e) => {
      if (!hiddenInput.value) {
        e.preventDefault();
        submit.disabled = true;
        setStatus("Please select a recommended skill before submitting.");
      }
    });

    // Initial state
    setStatus("Type to see suggestions");
    submit.disabled = true;
  }

  document
    .querySelectorAll("[data-skill-picker]")
    .forEach(initPicker);
})();
