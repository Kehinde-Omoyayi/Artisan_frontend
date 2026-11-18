/* Keyboard behaviour shared by every dropdown in the product.
   ---------------------------------------------------------------------------
   The panels already open on click, close on Escape and expose ARIA state, but
   the options inside them could only be reached with Tab. This adds the keys a
   person expects from a list: arrows, Home, End, and Enter/Space to choose
   (native on buttons). It works from the open panel itself, so each page keeps
   its own open/close logic and its own markup.
*/
(() => {
  const PANELS = [
    ".request-pick-body",
    ".artisan-pick-body",
    ".match-pick-panel",
    ".profile-pick-panel",
  ].join(",");
  const TOGGLES =
    ".request-pick-head,.artisan-pick-head,.match-pick-toggle,.profile-pick-toggle";
  const ROWS = ".request-pick,.artisan-pick,.match-pick,.profile-pick";
  const OPTION = "[role='option'], .match-pick-options > button";

  const visibleOptions = (panel) =>
    Array.from(panel.querySelectorAll(OPTION)).filter(
      (node) =>
        !node.hidden &&
        node.getAttribute("aria-hidden") !== "true" &&
        node.getClientRects().length > 0 &&
        !node.disabled
    );

  const openPanelFor = (toggle) => {
    const row = toggle.closest(".request-pick,.artisan-pick,.match-pick");
    if (!row) return null;
    const body = row.querySelector(PANELS);
    if (!body || body.hidden) return null;
    return body;
  };

  /* A picker near the bottom of a page opens a panel that lands below the fold.
     Once the page has painted the panel, pull it fully into view — only when it
     is actually out of reach, so nothing moves for a panel that already fits. */
  const bringIntoView = (panel) => {
    if (!panel) return;
    const box = panel.getBoundingClientRect();
    const room = window.innerHeight;
    if (box.bottom <= room && box.top >= 0) return;
    const wanted = box.height + 24;
    window.scrollBy({
      top: box.bottom > room ? Math.min(box.bottom - room + 16, wanted) : box.top - 16,
      behavior: "smooth",
    });
  };

  document.addEventListener(
    "click",
    (event) => {
      const toggle = event.target.closest(TOGGLES);
      if (!toggle) return;
      const settle = () => {
        const row = toggle.closest(ROWS);
        const panel = row && row.querySelector(PANELS);
        if (panel && !panel.hidden) bringIntoView(panel);
      };
      // Once as the panel opens, once after its options have arrived: a list
      // that fills from the server grows the panel, which can push it back
      // below the fold a moment after the first nudge.
      window.setTimeout(settle, 260);
      window.setTimeout(settle, 1200);
    },
    true
  );

  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
    const active = document.activeElement;
    if (!active) return;

    /* Inside an open panel: move between the options. */
    const panel = active.closest(PANELS);
    if (panel && !panel.hidden) {
      const options = visibleOptions(panel);
      if (!options.length) return;
      const index = options.indexOf(active);
      let next = null;
      if (event.key === "ArrowDown") next = options[index < 0 ? 0 : Math.min(options.length - 1, index + 1)];
      else if (event.key === "ArrowUp") next = options[index < 0 ? 0 : Math.max(0, index - 1)];
      else if (event.key === "Home") next = options[0];
      else if (event.key === "End") next = options[options.length - 1];
      if (next) {
        event.preventDefault();
        next.focus();
      }
      return;
    }

    /* On the closed (or open) trigger: ArrowDown steps into the list. */
    const toggle = active.closest(TOGGLES);
    if (!toggle) return;
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const body = openPanelFor(toggle);
    if (!body) return;
    const options = visibleOptions(body);
    if (!options.length) return;
    event.preventDefault();
    const target = event.key === "ArrowDown" ? options[0] : options[options.length - 1];
    target.focus();
  });
})();

/* ===========================================================================
   One searchable, animated dropdown for every native <select>, plus a search
   box inside every button-list picker panel that does not already have one.
   ---------------------------------------------------------------------------
   The native <select> stays in the form exactly where it was (so submits,
   validation and every page script keep working); it is only taken off screen.
   The panel, colours, chevron and open animation are the reference picker
   design, and a country select that has no value yet opens on Nigeria.
   =========================================================================== */
(() => {
  const CHEVRON_SVG =
    '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg>';

  /* --- search boxes for the button-list picker families ------------------ */
  const SEARCH_FAMILIES = [
    {
      panel: ".artisan-pick-body",
      cls: "artisan-pick-search",
      skipRow: '[data-picker-key="institution"]',
    },
    {
      panel: ".request-pick-body",
      cls: "request-pick-search",
      skipRow: '[data-pick-key="institution"]',
    },
    {
      panel: ".artisan-filter-row-body",
      cls: "artisan-filter-search",
      skipRow: '[data-filter-key="institution_id"]',
    },
  ];

  const injectSearch = () => {
    SEARCH_FAMILIES.forEach(({ panel, cls, skipRow }) => {
      document.querySelectorAll(panel).forEach((body) => {
        if (body.querySelector('input[type="search"]')) return;
        if (skipRow && body.closest(skipRow)) return;
        const list = body.querySelector(
          "[data-picker-options], [data-pick-options], [data-filter-options]"
        );
        if (!list) return;
        const input = document.createElement("input");
        input.type = "search";
        input.className = cls;
        input.placeholder = "Search…";
        input.setAttribute("aria-label", "Search options");
        input.autocomplete = "off";
        input.addEventListener("input", () => {
          const query = input.value.trim().toLocaleLowerCase();
          list.querySelectorAll("button").forEach((button) => {
            button.hidden = query
              ? !button.textContent.toLocaleLowerCase().includes(query)
              : false;
          });
        });
        input.addEventListener("keydown", (event) => {
          if (event.key !== "Enter") return;
          event.preventDefault();
          const visible = [...list.querySelectorAll("button")].filter(
            (button) => !button.hidden
          );
          if (visible.length === 1) visible[0].click();
          else visible[0]?.focus();
        });
        body.insertBefore(input, body.firstChild);
      });
    });
  };

  /* --- native selects ---------------------------------------------------- */
  const freshOptions = (select) =>
    [...select.options].filter((option) => !option.disabled);

  const closePanel = (panel) => {
    panel.hidden = true;
    const toggle = panel.previousElementSibling;
    if (toggle && toggle.classList.contains("ds-select-toggle")) {
      toggle.setAttribute("aria-expanded", "false");
    }
  };

  const defaultNigeria = (select, options) => {
    if (select.value) return;
    const nigeria = options.find(
      (option) =>
        option.value === "Nigeria" ||
        option.textContent.trim().toLocaleLowerCase() === "nigeria"
    );
    if (!nigeria) return;
    select.value = nigeria.value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  };

  const enhanceSelect = (select) => {
    if (select.dataset.dsReady) return;
    if (select.multiple || select.hasAttribute("data-ds-native")) return;
    if (select.hasAttribute("data-payout-bank-select")) return;
    /* The profile picker system converts these into its own reference rows. */
    if (select.closest("[data-profile-pickers]")) return;
    if (!freshOptions(select).length) return;
    select.dataset.dsReady = "1";

    const wrap = document.createElement("div");
    wrap.className = "ds-select";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "ds-select-toggle";
    toggle.setAttribute("aria-haspopup", "listbox");
    toggle.setAttribute("aria-expanded", "false");
    const label = document.createElement("span");
    label.className = "ds-select-label";
    toggle.appendChild(label);
    toggle.insertAdjacentHTML("beforeend", CHEVRON_SVG);

    const panel = document.createElement("div");
    panel.className = "ds-select-panel";
    panel.hidden = true;
    const search = document.createElement("input");
    search.type = "search";
    search.className = "ds-select-search";
    search.placeholder = "Search…";
    search.setAttribute("aria-label", "Search options");
    search.autocomplete = "off";
    const list = document.createElement("div");
    list.className = "ds-select-options";
    list.setAttribute("role", "listbox");
    const status = document.createElement("p");
    status.className = "ds-select-status";
    status.setAttribute("role", "status");
    panel.append(search, list, status);
    wrap.append(toggle, panel);
    select.insertAdjacentElement("afterend", wrap);
    select.classList.add("ds-native");
    select.setAttribute("tabindex", "-1");
    select.setAttribute("aria-hidden", "true");

    const syncLabel = () => {
      const options = freshOptions(select);
      const current =
        options.find((option) => option.value === select.value) || options[0];
      label.textContent = current ? current.textContent.trim() : "";
    };

    const renderList = () => {
      const options = freshOptions(select);
      const query = search.value.trim().toLocaleLowerCase();
      const matches = options.filter(
        (option) =>
          !query || option.textContent.toLocaleLowerCase().includes(query)
      );
      list.replaceChildren();
      matches.forEach((option) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "ds-select-option";
        button.setAttribute("role", "option");
        const on = option.value === select.value;
        button.setAttribute("aria-selected", String(on));
        if (on) button.classList.add("is-selected");
        button.textContent = option.textContent.trim();
        button.addEventListener("click", () => {
          if (select.value !== option.value) {
            select.value = option.value;
            select.dispatchEvent(new Event("change", { bubbles: true }));
          }
          syncLabel();
          closePanel(panel);
          toggle.focus();
        });
        list.appendChild(button);
      });
      status.textContent = matches.length
        ? `${matches.length} option${matches.length === 1 ? "" : "s"}`
        : "No matching option. Try a different search.";
    };

    const open = () => {
      document
        .querySelectorAll(".ds-select-panel:not([hidden])")
        .forEach((other) => {
          if (other !== panel) closePanel(other);
        });
      search.value = "";
      renderList();
      panel.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
      search.focus();
    };

    toggle.addEventListener("click", () => {
      if (panel.hidden) open();
      else closePanel(panel);
    });
    toggle.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        open();
        const buttons = [...list.querySelectorAll("button")];
        (event.key === "ArrowDown"
          ? buttons[0]
          : buttons[buttons.length - 1]
        )?.focus();
      }
    });
    search.addEventListener("input", renderList);
    search.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        const buttons = [...list.querySelectorAll("button")];
        if (buttons.length === 1) buttons[0].click();
        else buttons[0]?.focus();
      } else if (event.key === "Escape") {
        closePanel(panel);
        toggle.focus();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        const buttons = [...list.querySelectorAll("button")];
        if (!buttons.length) return;
        event.preventDefault();
        (event.key === "ArrowDown"
          ? buttons[0]
          : buttons[buttons.length - 1]
        )?.focus();
      }
    });
    list.addEventListener("keydown", (event) => {
      const buttons = [...list.querySelectorAll("button")];
      const index = buttons.indexOf(document.activeElement);
      if (event.key === "ArrowDown") {
        event.preventDefault();
        buttons[Math.min(buttons.length - 1, index + 1)]?.focus();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (index <= 0) search.focus();
        else buttons[index - 1]?.focus();
      } else if (event.key === "Escape") {
        closePanel(panel);
        toggle.focus();
      }
    });
    select.addEventListener("change", syncLabel);
    if (select.disabled) toggle.disabled = true;

    syncLabel();
    defaultNigeria(select, freshOptions(select));
    syncLabel();
  };

  document.addEventListener("click", (event) => {
    if (event.target.closest && event.target.closest(".ds-select")) return;
    document
      .querySelectorAll(".ds-select-panel:not([hidden])")
      .forEach(closePanel);
  });

  const enhanceAll = () => {
    document.querySelectorAll("select").forEach(enhanceSelect);
    injectSearch();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhanceAll);
  } else {
    enhanceAll();
  }
  /* Pages that add a select after load can call this again. */
  window.dsEnhance = enhanceAll;
})();
