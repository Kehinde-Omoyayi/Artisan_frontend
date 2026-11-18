/* The one bank-transfer card, shared by the chat and the payment page.
 *
 * Two shapes can be on screen:
 *
 *   [data-transfer-card]    the account is ready: copy controls, the countdown
 *                           ring, the "I have made this bank transfer" action
 *                           (chat) or a link back to the chat (payment page).
 *   [data-transfer-pending] the account is being set up (CREATING) or the
 *                           provider never confirmed it (OUTCOME_UNKNOWN).
 *                           Nothing to pay yet; the page refreshes itself the
 *                           moment the provider answers.
 *
 * The countdown is a local clock fed by the server's seconds; the status poll
 * is deliberately lazy (a hidden tab never fetches, and the poll stops once
 * the account has closed or the money has landed).
 */
(() => {
  const pad = (value) => String(value).padStart(2, "0");

  /* ------------------------------------------------------------ copying ---- */
  const bindCopyButtons = (root) => {
    root.querySelectorAll("[data-copy]").forEach((button) => {
      const label = button.querySelector("[data-copy-label]") || button;
      const reset = () => {
        button.removeAttribute("data-copied");
        label.textContent = "Copy";
      };
      button.addEventListener("click", async () => {
        const value = button.getAttribute("data-copy") || "";
        try {
          await navigator.clipboard.writeText(value);
        } catch (error) {
          /* Clipboard blocked (http, or a permission prompt): fall back. */
          const field = button
            .closest(".chat-transfer-hero")
            ?.querySelector("[data-copy-value]");
          if (field) {
            const range = document.createRange();
            range.selectNodeContents(field);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            document.execCommand("copy");
            selection.removeAllRanges();
          }
        }
        button.setAttribute("data-copied", "true");
        label.textContent = "Copied";
        window.setTimeout(reset, 1800);
      });
    });
  };

  /* --------------------------------------------- the live account (READY) ---- */
  const initCard = (card) => {
    const chip = card.querySelector("[data-transfer-chip]");
    const ring = card.querySelector("[data-transfer-ring]");
    const ringFill = card.querySelector("[data-transfer-ring-fill]");
    const clock = card.querySelector("[data-transfer-clock]");
    const count = card.querySelector("[data-transfer-count]");
    const confirmForm = card.querySelector("[data-transfer-confirm]");
    const expiredNote = card.querySelector("[data-transfer-expired-note]");

    const seconds = Number(card.getAttribute("data-transfer-seconds") || 0);
    const expiresAt = String(card.getAttribute("data-transfer-expires") || "").trim();
    let deadline = 0;
    if (seconds > 0) {
      deadline = Date.now() + seconds * 1000;
    } else if (expiresAt) {
      const parsed = new Date(expiresAt.replace(" ", "T"));
      if (!Number.isNaN(parsed.getTime())) deadline = parsed.getTime();
    }
    const span = Math.max(1, seconds > 0 ? seconds : Math.round((deadline - Date.now()) / 1000));
    const timed = deadline > 0;

    const timeLabel = (date) =>
      date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    const RING = 207.35; // 2 * pi * 33, matching the SVG in the card.
    const LOW_MARK = 5 * 60000;

    const scope = card.closest(".addon-payment-panel") || document;
    const unlockPayGate = () => {
      const gate = scope.querySelector("[data-pay-gate]");
      if (!gate) return;
      const start = gate.querySelector("[data-pay-start]");
      const button = gate.querySelector("[data-pay-start-button]");
      if (start) start.hidden = false;
      if (button) {
        button.disabled = false;
        button.removeAttribute("aria-disabled");
        button.textContent = "Request for payment link";
      }
      gate.setAttribute("data-pay-live", "false");
    };

    const paint = () => {
      const left = timed ? Math.max(0, deadline - Date.now()) : 0;
      const minutes = Math.floor(left / 60000);
      const secs = Math.floor((left % 60000) / 1000);
      if (!timed) {
        if (count) count.textContent = "—";
        return true;
      }
      const low = left > 0 && left < LOW_MARK;
      if (count) {
        count.textContent = left > 0 ? `${pad(minutes)}:${pad(secs)}` : "00:00";
        count.setAttribute("data-low", low ? "true" : "false");
      }
      if (ringFill) {
        const fraction = span > 0 ? Math.max(0, Math.min(1, left / (span * 1000))) : 0;
        ringFill.style.strokeDashoffset = String(RING * (1 - fraction));
        ringFill.setAttribute("data-low", low ? "true" : "false");
      }
      if (left <= 0) {
        if (clock) {
          clock.textContent =
            "This account has closed. Nothing has been charged — request a fresh link above.";
        }
        if (chip) {
          chip.textContent = "Expired";
          chip.setAttribute("data-state", "expired");
        }
        if (ring) ring.setAttribute("data-state", "expired");
        if (confirmForm) confirmForm.hidden = true;
        if (expiredNote) expiredNote.hidden = false;
        unlockPayGate();
        return false;
      }
      if (clock) {
        clock.textContent = `Closes at ${timeLabel(new Date(deadline))} — ${minutes} minute${minutes === 1 ? "" : "s"} left.`;
      }
      return true;
    };
    paint();
    const clockTimer = window.setInterval(() => {
      if (!paint()) window.clearInterval(clockTimer);
    }, 1000);

    /* While the account on screen is still open, the way to start another one
       stays inert: the strip hides its button, this disables any that is
       forced visible, and the API answers 409 besides. */
    const gate = scope.querySelector("[data-pay-gate]");
    const gateIsLive = () =>
      (gate ? gate.getAttribute("data-pay-live") === "true" : false) ||
      (timed && deadline - Date.now() > 0);
    const lockStartControls = () => {
      if (!gate) return;
      const start = gate.querySelector("[data-pay-start]");
      const button = gate.querySelector("[data-pay-start-button]");
      if (start) start.hidden = true;
      if (button) {
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
        button.title = "This transfer account is still open. Wait for the timer to finish.";
      }
    };
    const blockIfLive = (event) => {
      if (!gateIsLive()) return false;
      event.preventDefault();
      event.stopImmediatePropagation();
      return true;
    };
    if (gateIsLive()) {
      lockStartControls();
      gate.querySelectorAll("form[data-pay-start-form]").forEach((form) => {
        form.addEventListener("submit", blockIfLive, true);
        form.addEventListener("click", blockIfLive, true);
      });
    }
    return { expired: () => timed && deadline - Date.now() <= 0 };
  };

  /* -------------------------------------------- lazy payment status poll ---- */
  const watchPayment = (endpoint, isExpired, root) => {
    if (!endpoint) return () => {};
    let stopped = false;
    let inFlight = false;
    let timer = 0;
    let polls = 0;
    let delay = 8000;

    const settle = (status) => {
      if (stopped) return;
      stopped = true;
      window.clearTimeout(timer);
      window.setTimeout(() => window.location.reload(), 700);
    };

    const tick = async () => {
      if (stopped || inFlight || document.hidden) return;
      if (isExpired && isExpired()) { stopped = true; return; }
      if (polls > 150) { stopped = true; return; } // ~20 minutes, then the page is just a page.
      inFlight = true;
      polls += 1;
      try {
        const response = await fetch(endpoint, {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
          cache: "no-store",
        });
        if (response.status === 401 || response.status === 403) { stopped = true; return; }
        if (response.ok) {
          const data = await response.json().catch(() => null);
          if (data) {
            const paymentStatus = String(data.status || "").toUpperCase();
            const transferStatus = String(data.bank_transfer_status || "").toUpperCase();
            // The money landed (or the payment failed/was cancelled): reload so
            // the page shows the truth, not a stale card.
            if (paymentStatus && paymentStatus !== "PAYMENT_PENDING") { settle(paymentStatus); return; }
            // A CREATING/OUTCOME_UNKNOWN panel is showing and the account just
            // arrived: reload into the READY card.
            const pendingShown = root ? root.hasAttribute("data-transfer-pending") : document.querySelector("[data-transfer-pending]");
            if (transferStatus === "READY" && pendingShown) { settle("READY"); return; }
            delay = pendingShown ? 5000 : 8000;
          }
        }
      } catch (_) { /* offline: try again next tick */ }
      finally {
        inFlight = false;
        if (!stopped) timer = window.setTimeout(tick, delay);
      }
    };

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) return;
      delay = 3000;
      window.clearTimeout(timer);
      tick();
    });

    timer = window.setTimeout(tick, 3000);
    return (force) => {
      if (!force) return;
      window.clearTimeout(timer);
      tick();
    };
  };

  /* ------------------------------------------------------------- boot up ---- */
  const roots = Array.from(document.querySelectorAll("[data-transfer-card], [data-transfer-pending]"));
  if (!roots.length) return;
  roots.forEach(bindCopyButtons);

  /* Came back via ?transfer=<payment_id> (e.g. from the payment page):
     land on the card instead of at the top of the chat. */
  try {
    const wanted = new URLSearchParams(window.location.search).get("transfer");
    if (wanted) {
      const match = roots.find((root) => root.getAttribute("data-payment-id") === wanted);
      if (match) {
        window.setTimeout(() => {
          match.scrollIntoView({ block: "center", behavior: "smooth" });
          match.classList.add("is-refreshed");
          window.setTimeout(() => match.classList.remove("is-refreshed"), 2400);
        }, 80);
      }
    }
  } catch (_) { /* malformed query: ignore */ }

  /* One page can carry several cards (the booking payment and each approved
     add-on): every one gets its own countdown and its own lazy status poll.
     One-account-per-payment means they never share state. */
  const rechecks = roots.map((root) => {
    const live = root.hasAttribute("data-transfer-card") ? initCard(root) : null;
    const endpoint = String(root.getAttribute("data-payment-status") || "");
    return watchPayment(endpoint, live ? live.expired : () => false, root);
  });

  /* "Check again now": ask that card's own poll immediately. */
  roots.forEach((root, index) => {
    root.querySelectorAll("[data-transfer-recheck]").forEach((button) => {
      button.addEventListener("click", () => rechecks[index](true));
    });
  });
})();
