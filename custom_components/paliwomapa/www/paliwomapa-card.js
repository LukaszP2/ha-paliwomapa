/**
 * PaliwoMapa Lovelace Card
 * Native Home Assistant custom card; no external frontend dependencies.
 * Version: 0.2.8
 */
(() => {
  const CARD_TAG = "paliwomapa-card";
  const FUEL_TYPES = [
    { key: "pb95", label: "PB95", icon: "mdi:gas-station", price: "sensor.najtansze_pb95", station: "sensor.paliwomapa_podsumowanie_stacja_z_najtanszym_pb95" },
    { key: "pb98", label: "PB98", icon: "mdi:gas-station", price: "sensor.najtansze_pb98", station: "sensor.paliwomapa_podsumowanie_stacja_z_najtanszym_pb98" },
    { key: "on", label: "ON", icon: "mdi:gas-station", price: "sensor.najtansze_on", station: "sensor.stacja_z_najtanszym_on" },
    { key: "on_premium", label: "ON premium", icon: "mdi:gas-station", price: "sensor.najtansze_on_premium", station: "sensor.stacja_z_najtanszym_on_premium" },
    { key: "lpg", label: "LPG", icon: "mdi:gas-cylinder", price: "sensor.najtansze_lpg", station: "sensor.paliwomapa_podsumowanie_stacja_z_najtanszym_lpg" },
  ];

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));

  class PaliwoMapaCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = {};
      this._hass = null;
      this._lastSignature = "";
      this._stationSearch = "";
      this._stationFuelFilters = [];
      this._stationSort = "name";
      this._showAllStations = false;
      this._stationsExpanded = true;
    }

    setConfig(config) {
      if (!config || typeof config !== "object") throw new Error("Wymagana jest konfiguracja karty.");
      this._config = config;
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    get hass() { return this._hass; }

    getCardSize() { return 5; }

    static getConfigElement() { return document.createElement("paliwomapa-card-editor"); }

    static getStubConfig() {
      return { title: "PaliwoMapa", show_refresh: true, show_stations: true };
    }

    _entityId(fuel, kind) {
      const custom = this._config.fuels?.[fuel.key]?.[kind];
      if (custom) return custom;
      const defaults = FUEL_TYPES.find((f) => f.key === fuel.key);
      return defaults?.[kind] || "";
    }

    _state(entityId) {
      return entityId && this._hass?.states?.[entityId] ? this._hass.states[entityId] : null;
    }

    _displayState(entityId) {
      const obj = this._state(entityId);
      if (!obj || ["unknown", "unavailable", "none"].includes(String(obj.state).toLowerCase())) return null;
      return obj.state;
    }

    _brandDomain(brand = "") {
      const value = String(brand).toLocaleLowerCase("pl-PL");
      const domains = [
        [/orlen/, "orlen.pl"], [/bp|british petroleum/, "bp.com"], [/shell/, "shell.pl"],
        [/circle\s*k|circlek/, "circlek.pl"], [/moya/, "moyastacja.pl"], [/avia/, "avia.pl"],
        [/amic/, "amicenergy.pl"], [/mol/, "molpl.com"], [/lot(os)?/, "lotospaliwa.pl"],
        [/carrefour/, "carrefour.pl"], [/auchan/, "auchan.pl"], [/dyskont paliwowy/, ""]
      ];
      return domains.find(([pattern]) => pattern.test(value))?.[1] || "";
    }

    _brandLogoHtml(brand = "", explicitLogo = "", compact = false) {
      const safeBrand = String(brand || "").trim();
      const supplied = typeof explicitLogo === "string" && /^https?:\/\//i.test(explicitLogo) ? explicitLogo : "";
      const domain = this._brandDomain(safeBrand);
      // Prefer a logo URL provided by the integration; otherwise use the brand's favicon as a lightweight logo.
      const src = supplied || (domain ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=128` : "");
      if (src) return `<span class="operator-logo${compact ? " operator-logo-compact" : ""}" title="${esc(safeBrand)}"><img class="brand-image" src="${esc(src)}" alt="${esc(safeBrand)}" loading="lazy"></span>`;
      return `<span class="operator-logo operator-logo-fallback${compact ? " operator-logo-compact" : ""}" title="${esc(safeBrand || "Stacja paliw")}"><ha-icon icon="mdi:gas-station"></ha-icon></span>`;
    }

    _fuelKey(value = "") {
      const text = String(value).toLocaleLowerCase("pl-PL").replace(/[._-]+/g, " ");
      if (/on premium|premium on|diesel premium/.test(text)) return "on_premium";
      if (/pb ?98|benzyna 98|eurosuper 98/.test(text)) return "pb98";
      if (/pb ?95|benzyna 95|eurosuper 95/.test(text)) return "pb95";
      if (/\blpg\b|autogas|gaz/.test(text)) return "lpg";
      if (/\bon\b|diesel|olej napędowy/.test(text)) return "on";
      return "";
    }

    _fuelBadgeHtml(key, label, compact = false) {
      const safeKey = ["pb95", "pb98", "on", "on_premium", "lpg"].includes(key) ? key : "unknown";
      if (safeKey === "on_premium") return `<span class="fuel-badge fuel-on-premium${compact ? " fuel-badge-compact" : ""}"><span>ON</span><small>premium</small></span>`;
      return `<span class="fuel-badge fuel-${safeKey}${compact ? " fuel-badge-compact" : ""}">${esc(label || key.toUpperCase())}</span>`;
    }

    _navigationUrl(attrs = {}, label = "", address = "") {
      const explicit = attrs.navigation_url || attrs.map_url || attrs.google_maps_url;
      if (typeof explicit === "string" && /^https?:\/\//i.test(explicit)) return explicit;
      const lat = attrs.latitude ?? attrs.lat ?? attrs.gps_latitude;
      const lon = attrs.longitude ?? attrs.lon ?? attrs.lng ?? attrs.gps_longitude;
      const latitude = Number(lat);
      const longitude = Number(lon);
      if (lat !== undefined && lon !== undefined && Number.isFinite(latitude) && Number.isFinite(longitude) &&
          latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180) {
        return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${latitude},${longitude}`)}`;
      }
      const query = [address, label].filter(Boolean).join(", ").trim();
      return query ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(query)}` : "";
    }

    _findRefreshButton() {
      const configured = this._config.refresh_entity;
      if (configured && this._state(configured)) return configured;
      return Object.keys(this._hass?.states || {}).find((id) =>
        id.startsWith("button.") && /paliwomapa.*odswiez|odswiez.*ceny/i.test(id)
      ) || null;
    }

    _findLastRefresh() {
      const configured = this._config.last_refresh_entity;
      if (configured && this._state(configured)) return configured;
      return Object.keys(this._hass?.states || {}).find((id) =>
        id.startsWith("sensor.") && /paliwomapa.*ostatnie_odswiezenie/i.test(id)
      ) || null;
    }

    _stationEntities() {
      const explicit = this._config.station_entities;
      if (Array.isArray(explicit) && explicit.length) return explicit.filter((id) => this._state(id));
      return Object.keys(this._hass?.states || {}).filter((id) => {
        if (!id.startsWith("sensor.")) return false;
        const obj = this._state(id);
        const a = obj?.attributes || {};
        const name = `${id} ${obj?.attributes?.friendly_name || ""}`.toLowerCase();
        return (a.station_id !== undefined || a.station_name !== undefined || a.fuel_type !== undefined) &&
          (/paliwomapa/.test(name) || a.station_id !== undefined);
      }).sort((a, b) => a.localeCompare(b));
    }

    _formatPrice(value, entityId) {
      const obj = this._state(entityId);
      if (value === null || value === undefined) return "—";
      const unit = obj?.attributes?.unit_of_measurement || "zł/l";
      const num = Number(value);
      return `${Number.isFinite(num) ? num.toLocaleString("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 3 }) : esc(value)} ${esc(unit)}`;
    }

    _render() {
      if (!this.shadowRoot) return;
      if (!this._hass) {
        this.shadowRoot.innerHTML = `<ha-card><div class="loading">Ładowanie PaliwoMapa…</div></ha-card>${this._styles()}`;
        return;
      }

      const title = this._config.title || "PaliwoMapa";
      const refreshId = this._findRefreshButton();
      const lastId = this._findLastRefresh();
      const last = lastId ? this._displayState(lastId) : null;
      const fuels = FUEL_TYPES.map((fuel) => {
        const priceId = this._entityId(fuel, "price");
        const stationId = this._entityId(fuel, "station");
        const price = this._displayState(priceId);
        const stationObj = this._state(stationId);
        const stationState = this._displayState(stationId);
        const attrs = stationObj?.attributes || {};
        const stationName = attrs.station_name ||
          (stationState && !/^\d+$/.test(stationState) ? stationState : null) || "Brak danych stacji";
        const address = attrs.station_address || attrs.address || attrs.address_line || attrs.location_name || "";
        const brand = attrs.brand || attrs.operator || attrs.network || "";
        const stationNumber = attrs.station_number ?? attrs.station_no ?? attrs.station_code ?? attrs.station_id ?? attrs.stationId ?? "";
        const url = this._navigationUrl(attrs, stationName, address);
        const distance = attrs.distance_km;
        // Keep the main comparison visually consistent with monitored-station rows:
        // operator + fuel badge, location/number beneath, price and navigation at right.
        const operator = brand || stationName;
        const location = address || (brand && stationName !== brand ? stationName : "");
        const logo = attrs.logo_url || attrs.brand_logo_url || attrs.logo || attrs.image_url || "";
        return { ...fuel, priceId, stationId, price, stationName, operator, location, stationNumber, url, distance, logo };
      });

      // If a fuel was removed from the integration configuration, its entities
      // disappear from HA; do not keep rendering a placeholder row for it.
      const activeFuels = fuels.filter((fuel) => this._state(fuel.priceId) || this._state(fuel.stationId) ||
        this._config.fuels?.[fuel.key]?.price || this._config.fuels?.[fuel.key]?.station);
      const hasAny = activeFuels.some((f) => f.price !== null || f.stationName);
      const fuelRows = activeFuels.map((fuel) => {
        const stationText = fuel.stationName || "Brak danych stacji";
        const stationHtml = fuel.url
          ? `<a class="icon-link fuel-navigation" href="${esc(fuel.url)}" target="_blank" rel="noopener noreferrer" aria-label="Nawiguj do ${esc(stationText)}" title="Nawiguj do stacji"><ha-icon icon="mdi:directions"></ha-icon></a>`
          : "";
        const secondary = [fuel.location, fuel.stationNumber, fuel.distance !== undefined && fuel.distance !== null ? `${fuel.distance} km` : ""]
          .filter((v) => v !== undefined && v !== null && String(v).trim() !== "")
          .map((v) => String(v));
        return `
          <div class="fuel-row">
            <div class="fuel-brand" title="${esc(fuel.operator)}">${this._brandLogoHtml(fuel.operator, fuel.logo)}${this._fuelBadgeHtml(fuel.key, fuel.label)}</div>
            <div class="fuel-copy">
              <div class="fuel-location">${esc(fuel.location || fuel.stationName || "Brak danych stacji")}</div>
              ${secondary.length ? `<div class="muted">${secondary.map(esc).join(" · ")}</div>` : ""}
            </div>
            <div class="price">${fuel.price !== null ? esc(this._formatPrice(fuel.price, fuel.priceId)) : "—"}</div>
            ${stationHtml}
          </div>`;
      }).join("");

      const allStations = this._stationEntities().map((id) => {
        const obj = this._state(id);
        const a = obj?.attributes || {};
        const label = a.friendly_name || id;
        const addr = a.station_address || a.address || a.address_line || "";
        const url = this._navigationUrl(a, a.station_name || a.brand || a.friendly_name || id, addr);
        const unit = a.unit_of_measurement || "";
        const distanceRaw = a.distance_km ?? a.distance ?? a.distance_m;
        const distance = distanceRaw === undefined || distanceRaw === null || distanceRaw === "" ? null : Number(distanceRaw) / (a.distance_m !== undefined ? 1000 : 1);
        const rawState = obj?.state ?? "—";
        const unavailable = ["unknown", "unavailable", "none", ""].includes(String(rawState).toLowerCase());
        const stationNumber = a.station_number ?? a.station_no ?? a.station_code ?? a.station_id ?? a.stationId ?? "";
        const operator = a.brand || a.operator || a.network || label.match(/^(Orlen|BP|Shell|Circle ?K|Moya|Avia|Amic|MOL|Lotos|Dyskont Paliwowy|Carrefour|Auchan)/i)?.[0] || "";
        const logo = a.logo_url || a.brand_logo_url || a.logo || a.image_url || "";
        // Station price sensors commonly encode the fuel in their entity_id
        // (for example sensor.orlen_pb95), not in a fuel_type attribute.
        const idFuel = id.toLowerCase().match(/(?:^|_)(on_premium|pb95|pb98|lpg|on)(?:_|$)/)?.[1] || "";
        const fuelKey = String(a.fuel_key || a.fuel_type || a.fuel || idFuel).toLowerCase();
        const normalizedFuelKey = this._fuelKey(fuelKey) || this._fuelKey(id);
        const fuelNames = { pb95: "PB95", pb98: "PB98", on: "ON", diesel: "ON", on_premium: "ON premium", lpg: "LPG", autogas: "LPG" };
        const fuel = a.fuel_label || fuelNames[normalizedFuelKey] || fuelNames[fuelKey] || a.fuel_type || a.fuel || "";
        const numeric = Number(rawState);
        const searchText = [label, fuel, addr, stationNumber, rawState].join(" ").toLocaleLowerCase("pl-PL");
        return { id, label, url, unit, rawState, unavailable, fuel: String(fuel), fuelKey: normalizedFuelKey, operator: String(operator), logo: String(logo), addr: String(addr),
          stationNumber: String(stationNumber), distance: Number.isFinite(distance) ? distance : null,
          numeric: Number.isFinite(numeric) && String(rawState).trim() !== "" ? numeric : null, searchText };
      });
      // Keep all supported fuels available as filters, even if current entity names
      // do not expose a fuel_type attribute (notably plain ON and LPG sensors).
      const knownFuelLabels = { pb95: "PB95", pb98: "PB98", on: "ON", on_premium: "ON premium", lpg: "LPG" };
      const detectedFuelLabels = Object.fromEntries(allStations
        .filter((station) => station.fuel && station.fuelKey)
        .map((station) => [station.fuelKey, station.fuel]));
      const fuelOptions = Object.keys(knownFuelLabels).map((key) => ({
        key, label: detectedFuelLabels[key] || knownFuelLabels[key],
      }));
      // Drop selections that disappeared because the available entities changed.
      this._stationFuelFilters = this._stationFuelFilters.filter((key) => fuelOptions.some((fuel) => fuel.key === key));
      const needle = this._stationSearch.trim().toLocaleLowerCase("pl-PL");
      const filteredStations = allStations.filter((station) =>
        (!needle || station.searchText.includes(needle)) &&
        (!this._stationFuelFilters.length || this._stationFuelFilters.includes(station.fuelKey))
      );
      filteredStations.sort((a, b) => {
        if (this._stationSort === "price") {
          if (a.numeric === null && b.numeric !== null) return 1;
          if (a.numeric !== null && b.numeric === null) return -1;
          if (a.numeric !== null && b.numeric !== null && a.numeric !== b.numeric) return a.numeric - b.numeric;
        }
        if (this._stationSort === "distance") {
          if (a.distance === null && b.distance !== null) return 1;
          if (a.distance !== null && b.distance === null) return -1;
          if (a.distance !== null && b.distance !== null && a.distance !== b.distance) return a.distance - b.distance;
        }
        return a.label.localeCompare(b.label, "pl-PL", { sensitivity: "base" });
      });
      const visibleStations = this._showAllStations ? filteredStations : filteredStations.slice(0, 8);
      const showStations = this._config.show_stations !== false;
      const stationMarkup = showStations ? `
        <section class="stations">
          <div class="stations-heading">
            <div class="section-title"><ha-icon icon="mdi:map-marker-multiple"></ha-icon> Monitorowane stacje <span class="count">${filteredStations.length === allStations.length ? allStations.length : `${filteredStations.length} z ${allStations.length}`}</span></div>
            <button class="collapse-stations" type="button" aria-expanded="${this._stationsExpanded}"><ha-icon icon="mdi:chevron-${this._stationsExpanded ? "up" : "down"}"></ha-icon><span>${this._stationsExpanded ? "Zwiń" : "Rozwiń"}</span></button>
          </div>
          ${this._stationsExpanded ? `
            <div class="station-tools">
              <label class="station-search"><ha-icon icon="mdi:magnify"></ha-icon><input class="station-search-input" type="search" placeholder="Szukaj stacji, adresu lub paliwa…" value="${esc(this._stationSearch)}" aria-label="Szukaj monitorowanych stacji"></label>
              <div class="station-selects">
                <div class="fuel-filter-group" role="group" aria-label="Filtruj według paliwa">
                  <span class="filter-label">Paliwo</span>
                  <button class="fuel-filter-chip ${this._stationFuelFilters.length === 0 ? "active" : ""}" type="button" data-fuel-filter="all" aria-pressed="${this._stationFuelFilters.length === 0}">Wszystkie</button>
                  ${fuelOptions.map((fuel) => `<button class="fuel-filter-chip ${this._stationFuelFilters.includes(fuel.key) ? "active" : ""}" type="button" data-fuel-filter="${esc(fuel.key)}" aria-pressed="${this._stationFuelFilters.includes(fuel.key)}">${this._fuelBadgeHtml(fuel.key, fuel.label, true)}</button>`).join("")}
                </div>
                <label><span>Sortuj</span><select class="station-sort" aria-label="Sortuj stacje"><option value="name" ${this._stationSort === "name" ? "selected" : ""}>Nazwa</option><option value="price" ${this._stationSort === "price" ? "selected" : ""}>Cena rosnąco</option><option value="distance" ${this._stationSort === "distance" ? "selected" : ""}>Odległość</option></select></label>
              </div>
            </div>
            ${visibleStations.length ? `<div class="station-list">${visibleStations.map((station) => {
              const value = station.unavailable ? "Brak danych" : `${station.rawState}${station.unit ? ` ${station.unit}` : ""}`;
              const stateClass = station.unavailable ? " station-unavailable" : "";
              const detail = [station.addr, station.stationNumber].filter(Boolean).join(" · ");
              const displayName = station.label
                .replace(station.operator ? new RegExp(`^${station.operator.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*[-|:]?\\s*`, "i") : /$^/, "")
                .replace(/\s*\[\d+\]\s*/g, " ")
                .replace(/\s+(PB95|PB98|ON\s+premium|ON|LPG)\s*$/i, "")
                .trim();
              const fuelKey = station.fuelKey || "";
              const brandMarkup = this._brandLogoHtml(station.operator, station.logo, true);
              const badgeMarkup = fuelKey ? this._fuelBadgeHtml(fuelKey, station.fuel, true) : `<span class="fuel-badge fuel-unknown fuel-badge-compact"><ha-icon icon="mdi:gas-station"></ha-icon></span>`;
              return `<div class="station-item${stateClass}" data-search="${esc(station.searchText)}" data-fuel="${esc(station.fuel)}"><div class="station-brand">${brandMarkup}${badgeMarkup}</div><div class="station-copy"><strong title="${esc(station.label)}">${esc(displayName || station.label)}</strong>${detail ? `<span>${esc(detail)}</span>` : ""}</div><div class="station-value">${esc(value)}</div>${station.url ? `<a class="icon-link" href="${esc(station.url)}" target="_blank" rel="noopener noreferrer" aria-label="Nawiguj do ${esc(station.label)}"><ha-icon icon="mdi:directions"></ha-icon></a>` : ""}</div>`;
            }).join("")}</div>${filteredStations.length > 8 ? `<button class="show-more-stations" type="button">${this._showAllStations ? "Pokaż mniej" : `Pokaż wszystkie (${filteredStations.length})`} <ha-icon icon="mdi:chevron-${this._showAllStations ? "up" : "down"}"></ha-icon></button>` : ""}` : `<div class="empty">Brak stacji pasujących do wyszukiwania i filtrów.</div>`}
          ` : ""}
        </section>` : "";

      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="header">
            <div class="brand"><ha-icon icon="mdi:gas-station"></ha-icon><div><div class="title">${esc(title)}</div></div></div>
            <div class="header-actions">
              ${last ? `<div class="updated"><ha-icon icon="mdi:clock-outline"></ha-icon><span>${esc(last)}</span></div>` : ""}
              ${this._config.show_refresh !== false && refreshId ? `<button class="refresh" data-refresh="${esc(refreshId)}"><ha-icon icon="mdi:refresh"></ha-icon><span>Odśwież</span></button>` : ""}
            </div>
          </div>
          <div class="body">
            <div class="section-title"><ha-icon icon="mdi:cash-check"></ha-icon> Najtańsze paliwa</div>
            ${hasAny ? `<div class="fuel-list">${fuelRows}</div>` : `<div class="empty">Nie znaleziono danych cenowych. Sprawdź identyfikatory encji w konfiguracji karty.</div>`}
            ${stationMarkup}
          </div>
        </ha-card>
        ${this._styles()}`;

      const searchInput = this.shadowRoot.querySelector(".station-search-input");
      if (searchInput) {
        searchInput.addEventListener("input", (event) => {
          const cursor = event.target.selectionStart;
          this._stationSearch = event.target.value;
          this._showAllStations = Boolean(this._stationSearch.trim()) || this._stationFuelFilters.length > 0;
          this._render();
          const nextInput = this.shadowRoot.querySelector(".station-search-input");
          if (nextInput) {
            nextInput.focus();
            try { nextInput.setSelectionRange(cursor, cursor); } catch (_) { /* Search input may not support selection. */ }
          }
        });
      }
      this.shadowRoot.querySelectorAll("[data-fuel-filter]").forEach((button) => {
        button.addEventListener("click", () => {
          const key = button.dataset.fuelFilter;
          if (key === "all") {
            this._stationFuelFilters = [];
          } else if (this._stationFuelFilters.includes(key)) {
            this._stationFuelFilters = this._stationFuelFilters.filter((item) => item !== key);
          } else {
            this._stationFuelFilters = [...this._stationFuelFilters, key];
          }
          this._showAllStations = false;
          this._render();
        });
      });
      this.shadowRoot.querySelector(".station-sort")?.addEventListener("change", (event) => {
        this._stationSort = event.target.value;
        this._showAllStations = false;
        this._render();
      });
      this.shadowRoot.querySelector(".show-more-stations")?.addEventListener("click", () => {
        this._showAllStations = !this._showAllStations;
        this._render();
      });
      this.shadowRoot.querySelector(".collapse-stations")?.addEventListener("click", () => {
        this._stationsExpanded = !this._stationsExpanded;
        this._render();
      });

      this.shadowRoot.querySelectorAll("img.brand-image").forEach((img) => {
        img.addEventListener("error", () => {
          const wrapper = img.closest(".operator-logo");
          if (wrapper && !wrapper.classList.contains("operator-logo-fallback")) {
            wrapper.classList.add("operator-logo-fallback");
            wrapper.innerHTML = '<ha-icon icon="mdi:gas-station"></ha-icon>';
          }
        }, { once: true });
      });

      this.shadowRoot.querySelectorAll("[data-refresh]").forEach((button) => {
        button.addEventListener("click", () => {
          const entityId = button.getAttribute("data-refresh");
          this._hass.callService("button", "press", { entity_id: entityId });
        });
      });
    }

    _styles() {
      return `<style>
        :host{display:block;color:var(--primary-text-color)}
        ha-card{overflow:hidden;border-radius:var(--ha-card-border-radius,12px)}
        .header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:18px 20px;background:var(--ha-card-header-background,var(--card-background-color))}
        .brand{display:flex;align-items:center;gap:12px;min-width:0}
        .brand ha-icon{--mdc-icon-size:30px;color:var(--primary-color)}
        .title{font-size:20px;font-weight:600;line-height:1.25}
        .subtitle,.muted,.updated{font-size:12px;color:var(--secondary-text-color)}
        .header-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-end}
        .updated{display:flex;align-items:center;gap:5px}
        .refresh{display:flex;align-items:center;gap:6px;border:0;border-radius:9px;padding:9px 12px;background:var(--primary-color);color:var(--text-primary-color,var(--text-primary-color));font:inherit;cursor:pointer}
        .refresh ha-icon{--mdc-icon-size:18px}
        .body{padding:4px 20px 20px}
        .section-title{display:flex;align-items:center;gap:8px;font-weight:600;font-size:15px;margin:16px 0 10px}
        .section-title ha-icon{color:var(--primary-color);--mdc-icon-size:20px}
        .fuel-list{display:flex;flex-direction:column;gap:0}
        .fuel-row{display:grid;grid-template-columns:minmax(100px,.9fr) minmax(90px,1.2fr) auto 28px;gap:10px;align-items:center;padding:13px 0;border-bottom:1px solid var(--divider-color);min-width:0}
        .fuel-row:last-child{border-bottom:0}
        .fuel-brand{display:flex;align-items:center;gap:7px;min-width:0;flex-wrap:nowrap}
        .fuel-brand .fuel-badge{flex:0 0 52px;width:52px;box-sizing:border-box;min-width:52px;height:27px;min-height:27px;padding:2px 3px}
        .fuel-brand .fuel-on-premium{height:27px;min-height:27px}
        .station-brand{display:flex;align-items:center;gap:4px;flex:0 0 auto;min-width:0}
        .operator-logo{display:inline-flex;align-items:center;justify-content:center;flex:0 0 38px;width:38px;height:28px;padding:2px;border-radius:5px;background:var(--secondary-background-color);font-size:10px;font-weight:800;line-height:1.1;text-align:center;overflow:hidden}
        .operator-logo img{display:block;max-width:100%;max-height:100%;width:100%;height:100%;object-fit:contain}
        .operator-logo ha-icon{--mdc-icon-size:21px;color:var(--primary-color)}
        .operator-logo-fallback{background:transparent}
        .operator-logo-compact{flex-basis:28px;width:28px;height:24px;padding:1px}
        .operator-logo-compact ha-icon{--mdc-icon-size:18px}
        .fuel-badge{display:inline-flex;align-items:center;justify-content:center;min-width:52px;min-height:27px;width:52px;height:27px;box-sizing:border-box;padding:2px 3px;border-radius:3px;background:#0750c7;color:#fff;font-size:11px;font-weight:800;line-height:1.1;white-space:nowrap}
        .fuel-badge small{display:block;font-size:8px;line-height:1}
        .fuel-on{background:#111;color:#fff}
        .fuel-pb95{background:#19833b;color:#fff}
        .fuel-pb98{background:#006b2d;color:#fff}
        .fuel-on-premium{background:#082d68;color:#fff;flex-direction:column;gap:0}
        .fuel-lpg{background:#f2f2f2;color:#171717}
        .fuel-unknown{background:var(--secondary-background-color);color:var(--primary-text-color)}
        .fuel-badge-compact{min-width:25px;min-height:21px;width:auto;height:auto;padding:2px 4px;font-size:10px}
        .fuel-badge-compact small{font-size:7px}
        .fuel-copy{display:flex;flex-direction:column;gap:3px;min-width:0}
        .fuel-location{font-size:13px;font-weight:650;line-height:1.35;overflow-wrap:anywhere}
        .price{font-size:16px;font-weight:750;font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right}
        .muted{margin-top:1px;overflow-wrap:anywhere;font-size:11px;color:var(--secondary-text-color)}
        .fuel-navigation{align-self:center;margin-left:0;text-decoration:none}
        .fuel-navigation ha-icon{--mdc-icon-size:20px}
        .stations{border-top:1px solid var(--divider-color);margin-top:18px;padding-top:10px}
        .stations-heading{display:flex;align-items:center;justify-content:space-between;gap:10px}
        .stations-heading .section-title{margin:8px 0 12px}
        .count{font-size:12px;color:var(--secondary-text-color);font-weight:500;background:var(--secondary-background-color);border-radius:20px;padding:3px 8px}
        .collapse-stations,.show-more-stations{display:inline-flex;align-items:center;justify-content:center;gap:5px;border:1px solid var(--divider-color);border-radius:8px;background:transparent;color:var(--primary-text-color);font:inherit;font-size:12px;padding:7px 10px;cursor:pointer}
        .collapse-stations ha-icon,.show-more-stations ha-icon{--mdc-icon-size:17px}
        .station-tools{display:flex;align-items:center;gap:10px;margin:0 0 10px;flex-wrap:wrap}
        .station-search{display:flex;align-items:center;gap:8px;flex:1;min-width:190px;border:1px solid var(--divider-color);border-radius:9px;padding:0 10px;background:var(--secondary-background-color);color:var(--secondary-text-color)}
        .station-search ha-icon{--mdc-icon-size:19px}
        .station-search input{width:100%;min-width:0;border:0;outline:0;background:transparent;color:var(--primary-text-color);font:inherit;font-size:13px;padding:10px 0}
        .station-selects{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
        .station-selects label{display:flex;align-items:center;gap:5px;color:var(--secondary-text-color);font-size:11px}
        .fuel-filter-group{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
        .filter-label{font-size:11px;color:var(--secondary-text-color);margin-right:2px}
        .fuel-filter-chip{display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--divider-color);border-radius:7px;background:transparent;color:var(--primary-text-color);font:inherit;font-size:12px;padding:4px 6px;cursor:pointer;min-height:33px}
        .fuel-filter-chip .fuel-badge{pointer-events:none}
        .fuel-filter-chip.active{border-color:var(--primary-color);background:color-mix(in srgb,var(--primary-color) 13%,transparent);color:var(--primary-text-color)}
        .station-selects select{max-width:145px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit;font-size:12px;padding:8px 6px}
        .station-list{display:flex;flex-direction:column;border:1px solid var(--divider-color);border-radius:10px;overflow:hidden}
        .station-item{display:flex;align-items:center;gap:8px;padding:10px 10px;border-bottom:1px solid var(--divider-color);min-width:0}
        .station-item:last-child{border-bottom:0}
        .station-item[hidden],.show-more-stations[hidden]{display:none}
        .station-status{display:flex;align-items:center;justify-content:center;flex:0 0 22px;color:var(--success-color,var(--primary-color))}
        .station-status ha-icon{--mdc-icon-size:18px}
        .station-unavailable .station-status{color:var(--warning-color,var(--error-color))}
        .station-copy{display:flex;flex-direction:column;gap:3px;min-width:0;flex:1}
        .station-copy strong{font-size:13px;line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .station-copy span{font-size:11px;line-height:1.35;color:var(--secondary-text-color);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .station-value{font-size:12px;font-weight:650;font-variant-numeric:tabular-nums;text-align:right;max-width:32%;overflow-wrap:anywhere;flex:0 0 auto}
        .icon-link{display:flex;align-items:center;justify-content:center;flex:0 0 28px;color:var(--primary-color);padding:5px;border-radius:7px}
        .icon-link:hover{background:var(--secondary-background-color)}
        .show-more-stations{width:100%;margin-top:9px;color:var(--primary-color);border-color:transparent;background:var(--secondary-background-color)}
        .empty{padding:12px;border-radius:8px;background:var(--secondary-background-color);color:var(--secondary-text-color);font-size:13px;line-height:1.5}
        .loading{padding:20px}
        @media(max-width:560px){.header{align-items:flex-start;flex-direction:column}.header-actions{justify-content:flex-start}.body{padding-left:14px;padding-right:14px}.fuel-row{grid-template-columns:minmax(82px,.85fr) minmax(0,1fr) auto 25px;gap:6px;padding:12px 0}.fuel-brand{gap:4px}.operator-logo{max-width:58px;font-size:9px;padding:3px 4px}.fuel-badge{font-size:10px;min-height:21px;padding:2px 4px}.station-brand{gap:3px}.operator-logo-compact{flex-basis:24px;width:24px;height:22px}.fuel-badge-compact{min-width:22px;font-size:9px}.fuel-location{font-size:12px}.price{font-size:14px}.fuel-navigation ha-icon{--mdc-icon-size:19px}.station-tools{align-items:stretch;flex-direction:column}.station-selects{width:100%;align-items:stretch;flex-direction:column}.fuel-filter-group{width:100%}.station-selects label{justify-content:space-between}.station-selects select{max-width:none;flex:1;min-width:0}.station-value{font-size:11px;max-width:38%}.station-item{gap:7px;padding:10px 8px}.station-copy strong{font-size:12px}.stations-heading .section-title{font-size:14px;gap:5px}}
      </style>`;
    }
  }

  if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, PaliwoMapaCard);

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === CARD_TAG)) {
    window.customCards.push({
      type: CARD_TAG,
      name: "PaliwoMapa",
      description: "Ceny paliw, najtańsze stacje i nawigacja.",
      preview: true,
    });
  }
})();