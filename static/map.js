(() => {
  // ── Map init ────────────────────────────────────────────────────────────────
  const map = L.map("map", {
    zoomControl: true,
    touchZoom: true,
    scrollWheelZoom: true,
  }).setView([20, 0], 3);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(map);

  // ── State ───────────────────────────────────────────────────────────────────
  let markers = [];
  let refreshCooldown = false;
  let countdownValue = 60;
  let countdownTimer = null;
  let autoRefreshTimer = null;
  let autoRefreshPaused = false;
  let lastErrorKind = null;

  // ── DOM refs ─────────────────────────────────────────────────────────────────
  const statusText = document.getElementById("status-text");
  const refreshBtn = document.getElementById("refresh-btn");
  const locateBtn = document.getElementById("locate-btn");
  const searchBtn = document.getElementById("search-btn");
  const searchInput = document.getElementById("search-input");
  const suggestionsList = document.getElementById("suggestions-list");
  const loadingOverlay = document.getElementById("loading-overlay");
  const toastContainer = document.getElementById("toast-container");

  // ── HTML escape ──────────────────────────────────────────────────────────────
  // Third-party strings (OpenSky callsign/country, Nominatim display_name) are
  // not trusted: ADS-B callsigns are broadcast by the aircraft itself, and
  // Nominatim names come from OSM tags. Always run them through this before
  // interpolating into innerHTML.
  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ── Toast ────────────────────────────────────────────────────────────────────
  function showToast(message, type = "") {
    const el = document.createElement("div");
    el.className = "toast" + (type ? " " + type : "");
    el.textContent = message;
    toastContainer.appendChild(el);
    setTimeout(() => el.remove(), 4200);
  }

  // ── Loading overlay ──────────────────────────────────────────────────────────
  function setLoading(on) {
    loadingOverlay.classList.toggle("visible", on);
  }

  // ── Refresh cooldown ─────────────────────────────────────────────────────────
  function startCooldown() {
    refreshCooldown = true;
    refreshBtn.disabled = true;
    setTimeout(() => {
      refreshCooldown = false;
      refreshBtn.disabled = false;
    }, 10000);
  }

  // ── Countdown timer ──────────────────────────────────────────────────────────
  function resetCountdown() {
    countdownValue = 60;
    if (countdownTimer) clearInterval(countdownTimer);
    countdownTimer = setInterval(() => {
      countdownValue -= 1;
      if (countdownValue > 0) {
        statusText.textContent = `Refreshing in ${countdownValue}s...`;
      }
    }, 1000);
  }

  // ── Clear all markers ────────────────────────────────────────────────────────
  function clearMarkers() {
    markers.forEach(m => m.remove());
    markers = [];
  }

  // ── Build DivIcon for a flight ────────────────────────────────────────────────
  function buildIcon(heading, onGround) {
    const color = onGround ? "#a0a0b0" : "#4a90d9";
    const rotate = (heading || 0);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-14 -14 28 28" width="28" height="28" style="transform:rotate(${rotate}deg);color:${color}">
      <ellipse cx="0" cy="0" rx="3" ry="10" fill="${color}"/>
      <path d="M-12,4 L0,-1 L12,4 L10,6 L0,3 L-10,6 Z" fill="${color}"/>
      <path d="M-5,8 L0,6 L5,8 L4,10 L0,8.5 L-4,10 Z" fill="${color}"/>
    </svg>`;
    return L.divIcon({
      html: `<div class="plane-icon">${svg}</div>`,
      className: "",
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });
  }

  // ── Build popup HTML ──────────────────────────────────────────────────────────
  function buildPopup(f) {
    const alt = f.altitude != null ? Math.round(f.altitude).toLocaleString() + " m" : "N/A";
    const spd = f.speed != null ? Math.round(f.speed) + " m/s" : "N/A";
    const hdg = f.heading != null ? Math.round(f.heading) + "°" : "N/A";
    const statusClass = f.on_ground ? "popup-status-ground" : "popup-status-airborne";
    const statusLabel = f.on_ground ? "On Ground" : "Airborne";
    // callsign and country come from third-party ADS-B broadcasts; escape them.
    // alt/spd/hdg are numeric-derived; statusClass/statusLabel are internal.
    return `
      <div class="popup-callsign">&#9992; ${escapeHtml(f.callsign)}</div>
      <div class="popup-row"><span class="popup-label">Country</span><span class="popup-value">${escapeHtml(f.country) || "N/A"}</span></div>
      <div class="popup-row"><span class="popup-label">Altitude</span><span class="popup-value">${alt}</span></div>
      <div class="popup-row"><span class="popup-label">Speed</span><span class="popup-value">${spd}</span></div>
      <div class="popup-row"><span class="popup-label">Heading</span><span class="popup-value">${hdg}</span></div>
      <div class="popup-row"><span class="popup-label">Status</span><span class="${statusClass}">${statusLabel}</span></div>
    `;
  }

  // ── Fetch and render flights ──────────────────────────────────────────────────
  async function fetchAndRenderFlights() {
    const b = map.getBounds();
    const params = new URLSearchParams({
      lat1: b.getSouth().toFixed(4),
      lon1: b.getWest().toFixed(4),
      lat2: b.getNorth().toFixed(4),
      lon2: b.getEast().toFixed(4),
    });

    setLoading(true);
    resetCountdown();

    try {
      const res = await fetch(`/api/flights?${params}`);
      const data = await res.json();

      if (data.error === "zoom_required") {
        // Server short-circuited before any OpenSky call; don't lock the
        // manual button or moveend refetch — the user may zoom in immediately.
        clearMarkers();
        if (lastErrorKind !== "zoom_required") {
          showToast("Zoom in to see flights", "warn");
        }
        lastErrorKind = "zoom_required";
        stopAutoRefresh("Zoom in to see flights");
        return;
      }

      // Past this point a real OpenSky call was attempted; apply the 10 s
      // client cooldown to avoid hammering even on error paths.
      startCooldown();

      if (data.error === "rate_limited") {
        clearMarkers();
        if (lastErrorKind !== "rate_limited") {
          showToast(data.message || "Rate limited — tap ↺ to retry", "warn");
        }
        lastErrorKind = "rate_limited";
        stopAutoRefresh("Rate limited — tap ↺ to retry");
        return;
      }

      if (data.error === "upstream_error") {
        showToast("Flight data unavailable — showing last known positions", "error");
        statusText.textContent = "API error — last known data";
        return;
      }

      clearMarkers();
      lastErrorKind = null;
      autoRefreshPaused = false;
      scheduleAutoRefresh();

      if (!data.flights || data.flights.length === 0) {
        statusText.textContent = "No flights in this area";
        showToast("No flights in this area");
        return;
      }

      data.flights.forEach(f => {
        const marker = L.marker([f.lat, f.lon], { icon: buildIcon(f.heading, f.on_ground) })
          .bindPopup(buildPopup(f), { maxWidth: 240 })
          .addTo(map);
        markers.push(marker);
      });

      statusText.textContent = `${data.count} flight${data.count !== 1 ? "s" : ""} in view`;
    } catch {
      showToast("Could not reach server", "error");
      statusText.textContent = "Connection error";
    } finally {
      setLoading(false);
    }
  }

  // ── Auto-refresh every 60s ────────────────────────────────────────────────────
  function scheduleAutoRefresh() {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    autoRefreshTimer = setInterval(fetchAndRenderFlights, 60000);
  }

  function stopAutoRefresh(statusLabel) {
    autoRefreshPaused = true;
    if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null; }
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    if (statusLabel) statusText.textContent = statusLabel;
  }

  // ── Manual refresh ────────────────────────────────────────────────────────────
  refreshBtn.addEventListener("click", () => {
    if (!refreshCooldown) fetchAndRenderFlights();
  });

  // ── My location ──────────────────────────────────────────────────────────────
  locateBtn.addEventListener("click", () => {
    if (!navigator.geolocation) {
      showToast("Geolocation not supported", "warn");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      pos => map.setView([pos.coords.latitude, pos.coords.longitude], 10),
      err => {
        const msg = err && err.code === 1 ? "Location permission denied" : "Couldn't get location";
        showToast(msg, "warn");
      },
      { timeout: 15000, maximumAge: 60000, enableHighAccuracy: false }
    );
  });

  // ── Autocomplete ─────────────────────────────────────────────────────────────
  function hideSuggestions() {
    suggestionsList.classList.remove("visible");
    suggestionsList.innerHTML = "";
  }

  function renderSuggestions(items) {
    suggestionsList.innerHTML = "";
    if (!items.length) { hideSuggestions(); return; }

    items.forEach(item => {
      const parts = item.display_name.split(", ");
      const primary = parts[0];
      const secondary = parts.slice(1).join(", ");

      // Build with DOM methods to avoid HTML-injection via Nominatim display_name
      // (OSM tags are user-contributed).
      const li = document.createElement("li");
      li.className = "suggestion-item";
      const primaryDiv = document.createElement("div");
      primaryDiv.className = "suggestion-primary";
      primaryDiv.textContent = primary;
      const secondaryDiv = document.createElement("div");
      secondaryDiv.className = "suggestion-secondary";
      secondaryDiv.textContent = secondary;
      li.appendChild(primaryDiv);
      li.appendChild(secondaryDiv);
      li.addEventListener("mousedown", e => {
        e.preventDefault();
        searchInput.value = item.display_name;
        hideSuggestions();
        selectLocation(item.lat, item.lon);
      });
      suggestionsList.appendChild(li);
    });

    suggestionsList.classList.add("visible");
  }

  let suggestDebounce = null;
  searchInput.addEventListener("input", () => {
    clearTimeout(suggestDebounce);
    const q = searchInput.value.trim();
    if (q.length < 2) { hideSuggestions(); return; }
    suggestDebounce = setTimeout(async () => {
      try {
        const res = await fetch(`/api/suggestions?q=${encodeURIComponent(q)}`);
        renderSuggestions(await res.json());
      } catch {
        hideSuggestions();
      }
    }, 300);
  });

  searchInput.addEventListener("keydown", e => {
    if (e.key === "Escape") hideSuggestions();
  });

  document.addEventListener("click", e => {
    if (!e.target.closest("#search-group")) hideSuggestions();
  });

  function selectLocation(lat, lon) {
    map.setView([lat, lon], 8);
    fetchAndRenderFlights();
  }

  // ── Location search ───────────────────────────────────────────────────────────
  async function doSearch() {
    const q = searchInput.value.trim();
    if (!q) return;
    hideSuggestions();

    try {
      const res = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`);
      const data = await res.json();

      if (data.error === "not_found") {
        showToast("Location not found", "warn");
        return;
      }
      if (data.error) {
        showToast("Geocoding unavailable", "error");
        return;
      }

      selectLocation(data.lat, data.lon);
    } catch {
      showToast("Could not reach server", "error");
    }
  }

  searchBtn.addEventListener("click", doSearch);
  searchInput.addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });

  // ── Re-fetch when map view changes (debounced) ────────────────────────────────
  let moveDebounce = null;
  map.on("moveend", () => {
    clearTimeout(moveDebounce);
    moveDebounce = setTimeout(() => {
      if (!refreshCooldown) fetchAndRenderFlights();
    }, 600);
  });

  // ── Boot ──────────────────────────────────────────────────────────────────────
  scheduleAutoRefresh();

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      pos => {
        map.setView([pos.coords.latitude, pos.coords.longitude], 10);
        // moveend debounce triggers the initial fetch at the new location
      },
      () => fetchAndRenderFlights(),
      { timeout: 15000, maximumAge: 60000, enableHighAccuracy: false }
    );
  } else {
    fetchAndRenderFlights();
  }
})();
