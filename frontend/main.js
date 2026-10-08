import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap/dist/js/bootstrap.bundle.js";

const SEARCH_DELAY = 250;

function setupPageSearch() {
  const form = document.getElementById("pageSearchForm");
  const input = document.getElementById("pageSearchInput");
  const results = document.getElementById("pageSearchResults");
  if (!form || !input || !results) return;

  let debounceTimer;
  let controller;
  let requestSequence = 0;
  let activeIndex = -1;

  const cancelPending = () => {
    requestSequence += 1;
    window.clearTimeout(debounceTimer);
    if (controller) controller.abort();
    controller = null;
  };

  const closeResults = () => {
    cancelPending();
    results.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    activeIndex = -1;
  };

  const openResults = () => {
    results.hidden = false;
    input.setAttribute("aria-expanded", "true");
  };

  const showMessage = (message) => {
    results.replaceChildren();
    const item = document.createElement("div");
    item.className = "list-group-item text-muted";
    item.textContent = message;
    results.append(item);
    openResults();
  };

  const safeUrl = (value) => {
    try {
      const url = new URL(value, window.location.origin);
      return url.origin === window.location.origin ? url.href : null;
    } catch {
      return null;
    }
  };

  const renderResults = (items) => {
    results.replaceChildren();
    activeIndex = -1;
    if (!items.length) {
      showMessage("Ничего не найдено");
      return;
    }

    items.forEach((item, index) => {
      const url = safeUrl(item.url);
      if (!url || typeof item.title !== "string") return;
      const link = document.createElement("a");
      link.id = `page-search-result-${index}`;
      link.className = "list-group-item list-group-item-action";
      link.setAttribute("role", "option");
      link.textContent = item.title;
      link.href = url;
      results.append(link);
    });

    if (results.children.length) openResults();
    else showMessage("Ничего не найдено");
  };

  const setActive = (index) => {
    const links = [...results.querySelectorAll("a")];
    if (!links.length) return;
    activeIndex = (index + links.length) % links.length;
    links.forEach((link, linkIndex) => {
      const isActive = linkIndex === activeIndex;
      link.classList.toggle("active", isActive);
      link.setAttribute("aria-selected", String(isActive));
    });
    input.setAttribute("aria-activedescendant", links[activeIndex].id);
  };

  const search = async (value) => {
    const query = value.trim();
    requestSequence += 1;
    const sequence = requestSequence;
    if (controller) controller.abort();
    if (!query) {
      closeResults();
      return;
    }

    controller = new AbortController();
    const url = new URL(form.action, window.location.origin);
    url.searchParams.set("q", query);
    showMessage("Поиск…");

    try {
      const response = await fetch(url, {
        method: "GET",
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("search failed");
      const data = await response.json();
      if (sequence !== requestSequence) return;
      renderResults(Array.isArray(data.results) ? data.results : []);
    } catch (error) {
      if (error.name === "AbortError" || sequence !== requestSequence) return;
      showMessage("Не удалось выполнить поиск");
    }
  };

  input.addEventListener("input", () => {
    cancelPending();
    if (!input.value.trim()) {
      closeResults();
      return;
    }
    debounceTimer = window.setTimeout(() => search(input.value), SEARCH_DELAY);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    cancelPending();
    search(input.value);
  });

  form.addEventListener("keydown", (event) => {
    const links = results.querySelectorAll("a");
    if (event.key === "Escape") {
      closeResults();
      return;
    }
    if (event.key === "ArrowDown" && links.length) {
      event.preventDefault();
      setActive(activeIndex + 1);
    } else if (event.key === "ArrowUp" && links.length) {
      event.preventDefault();
      setActive(activeIndex - 1);
    } else if (event.key === "Enter" && activeIndex >= 0 && links[activeIndex]) {
      event.preventDefault();
      links[activeIndex].click();
    }
  });

  document.addEventListener("click", (event) => {
    if (!form.contains(event.target)) closeResults();
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", setupPageSearch, { once: true });
} else {
  setupPageSearch();
}
