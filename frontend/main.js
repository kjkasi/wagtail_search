import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap/dist/js/bootstrap.bundle.js";

const SEARCH_DEBOUNCE_MS = 250;

function setResultsVisibility(input, container, visible) {
    container.hidden = !visible;
    input.setAttribute("aria-expanded", String(visible));
}

function renderMessage(container, message) {
    container.replaceChildren();
    const item = document.createElement("div");
    item.className = "list-group-item text-muted";
    item.setAttribute("role", "option");
    item.textContent = message;
    container.append(item);
}

function getResultLinks(container) {
    return Array.from(container.querySelectorAll("a[role=option]"));
}

function moveFocus(links, currentIndex, direction) {
    if (links.length === 0) {
        return;
    }

    const nextIndex = (currentIndex + direction + links.length) % links.length;
    links[nextIndex].focus();
}

function isSafeResultUrl(value) {
    try {
        const url = new URL(String(value), window.location.origin);
        return url.origin === window.location.origin;
    } catch {
        return false;
    }
}

function renderSearchResults(container, results) {
    container.replaceChildren();

    if (results.length === 0) {
        renderMessage(container, "Ничего не найдено");
        return;
    }

    results.forEach((result, index) => {
        if (!result || !isSafeResultUrl(result.url)) {
            return;
        }

        const link = document.createElement("a");
        link.className = "list-group-item list-group-item-action";
        link.setAttribute("role", "option");
        link.id = `pageSearchResult-${index}`;
        link.href = String(result.url);

        const kind = document.createElement("span");
        kind.className = "me-2 text-muted small";
        kind.textContent = result.type === "document" ? "Документ" : "Страница";
        link.append(kind, document.createTextNode(String(result.title ?? "")));
        container.append(link);
    });

    if (container.children.length === 0) {
        renderMessage(container, "Ничего не найдено");
    }
}

function setupPageSearch() {
    const form = document.querySelector("#pageSearchForm");
    const input = document.querySelector("#pageSearchInput");
    const container = document.querySelector("#pageSearchResults");

    if (!(form instanceof HTMLFormElement) || !(input instanceof HTMLInputElement) || !container) {
        return;
    }

    let debounceTimer;
    let controller = null;
    let requestSequence = 0;

    const closeResults = () => {
        setResultsVisibility(input, container, false);
    };

    const runSearch = async () => {
        const query = input.value.trim();
        requestSequence += 1;
        const sequence = requestSequence;

        if (controller) {
            controller.abort();
            controller = null;
        }

        if (!query) {
            container.replaceChildren();
            closeResults();
            return;
        }

        controller = new AbortController();
        renderMessage(container, "Загрузка…");
        setResultsVisibility(input, container, true);

        const url = new URL(form.action, window.location.href);
        url.search = new URLSearchParams({ q: query }).toString();

        try {
            const response = await fetch(url, {
                method: "GET",
                signal: controller.signal,
            });
            if (!response.ok) {
                throw new Error(`Search request failed: ${response.status}`);
            }

            const data = await response.json();
            if (sequence !== requestSequence) {
                return;
            }

            renderSearchResults(container, Array.isArray(data.results) ? data.results : []);
            setResultsVisibility(input, container, true);
        } catch (error) {
            if (error.name === "AbortError" || sequence !== requestSequence) {
                return;
            }

            renderMessage(container, "Не удалось выполнить поиск");
            setResultsVisibility(input, container, true);
        } finally {
            if (sequence === requestSequence) {
                controller = null;
            }
        }
    };

    input.addEventListener("input", () => {
        window.clearTimeout(debounceTimer);
        requestSequence += 1;

        if (controller) {
            controller.abort();
            controller = null;
        }

        container.replaceChildren();
        closeResults();
        if (input.value.trim()) {
            debounceTimer = window.setTimeout(runSearch, SEARCH_DEBOUNCE_MS);
        }
    });

    input.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            event.preventDefault();
            closeResults();
            input.focus();
            return;
        }

        if (!container.hidden && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
            const links = getResultLinks(container);
            event.preventDefault();
            moveFocus(links, event.key === "ArrowDown" ? -1 : 0, event.key === "ArrowDown" ? 1 : -1);
        }
    });

    container.addEventListener("keydown", (event) => {
        const links = getResultLinks(container);
        const currentIndex = links.indexOf(document.activeElement);

        if (event.key === "Escape") {
            event.preventDefault();
            closeResults();
            input.focus();
        } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            moveFocus(links, currentIndex, event.key === "ArrowDown" ? 1 : -1);
        }
    });

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        window.clearTimeout(debounceTimer);
        runSearch();
    });

    document.addEventListener("click", (event) => {
        if (event.target instanceof Node && !form.contains(event.target)) {
            closeResults();
        }
    });
}

setupPageSearch();
