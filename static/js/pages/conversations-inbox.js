(() => {
  const formatTimestamp = (rawValue) => {
    const date = new Date(rawValue || "");
    if (Number.isNaN(date.getTime())) return "";
    const options = {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    };
    if (date.getFullYear() !== new Date().getFullYear()) options.year = "numeric";
    return new Intl.DateTimeFormat(undefined, options).format(date);
  };

  document.querySelectorAll(".inbox-card").forEach((card) => {
    const timestamp = card.querySelector("time[data-utc-time]");
    if (timestamp) {
      const formatted = formatTimestamp(timestamp.dataset.utcTime);
      if (formatted) timestamp.textContent = formatted;
    }

    card.addEventListener("click", () => {
      card.setAttribute("aria-busy", "true");
    });
  });
})();
