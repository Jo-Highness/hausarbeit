/**
 * hausarbeit-targets-card
 * -----------------------
 * Lovelace-Custom-Card "Soll/Ist" für den Hausarbeit-Tracker.
 *
 * No-Build-LitElement: verwendet HA-eigenes Lit (kein CDN/Import). Reines ES2020.
 *
 * Zeigt pro Target einen Fortschrittsbalken "<Task> <ist>/<count> <Periode>".
 * Balken visuell bei 100% gedeckelt, Text darf >100% zeigen. Farbe grün wenn
 * on_track, sonst warnend. Gruppierung nach Person, optionale Filter.
 */

// Home Assistant no longer exposes html/css on hui-view.prototype, and this
// module can load before the core Lit elements are defined. Defer the whole card
// definition until an element that DOES expose Lit (ha-panel-lovelace /
// hui-masonry-view / ha-card) is available, then read html/css from it.
async function _haInit() {
  let LitElement;
  for (let _i = 0; _i < 600 && !LitElement; _i++) {
    for (const n of ["ha-panel-lovelace", "hui-masonry-view", "ha-card"]) {
      const el = customElements.get(n);
      const proto = el && Object.getPrototypeOf(el);
      if (proto && proto.prototype && typeof proto.prototype.html === "function") { LitElement = proto; break; }
    }
    if (!LitElement) await new Promise((r) => setTimeout(r, 50));
  }
  const html = LitElement.prototype.html;
  const css = LitElement.prototype.css;

const WS_TARGETS = "hausarbeit/targets";
const WS_SUBSCRIBE = "hausarbeit/subscribe";

// --- Übersetzungen (kein Build/Import → Tabelle inline pro Karte) ---------- //
const STRINGS = {
  de: {
    title_default: "Soll / Ist",
    load_error: "Ziele konnten nicht geladen werden.",
    loading: "Lade …",
    no_targets: (hasFilter) =>
      `Keine Ziele definiert${hasFilter ? " (für diesen Filter)" : ""}.`,
    period_day: "täglich",
    period_week: "diese Woche",
    period_month: "diesen Monat",
    remaining: (n, period) => `noch ${n}× ${period}`,
    target_done: "Ziel erreicht",
    until: (date) => `bis ${date}`,
    target_aria: (name, ist, count, period, pct, onTrack) =>
      `${name}: ${ist} von ${count} ${period}, ${pct} Prozent${
        onTrack ? ", im Plan" : ", im Rückstand"
      }`,
    ed_title: "Titel",
    ed_period_filter: "Periode-Filter",
    ed_opt_all: "Alle",
    ed_opt_daily: "Täglich",
    ed_opt_weekly: "Wöchentlich",
    ed_opt_monthly: "Monatlich",
    ed_person_filter: "Personen-Filter (person_id)",
    ed_person_placeholder: "z. B. per_1a2b3c4d",
  },
  en: {
    title_default: "Target / Actual",
    load_error: "Could not load targets.",
    loading: "Loading …",
    no_targets: (hasFilter) =>
      `No targets defined${hasFilter ? " (for this filter)" : ""}.`,
    period_day: "per day",
    period_week: "this week",
    period_month: "this month",
    remaining: (n, period) => `${n}× more ${period}`,
    target_done: "Target reached",
    until: (date) => `by ${date}`,
    target_aria: (name, ist, count, period, pct, onTrack) =>
      `${name}: ${ist} of ${count} ${period}, ${pct} percent${
        onTrack ? ", on track" : ", behind"
      }`,
    ed_title: "Title",
    ed_period_filter: "Period filter",
    ed_opt_all: "All",
    ed_opt_daily: "Daily",
    ed_opt_weekly: "Weekly",
    ed_opt_monthly: "Monthly",
    ed_person_filter: "Person filter (person_id)",
    ed_person_placeholder: "e.g. per_1a2b3c4d",
  },
  es: {
    title_default: "Objetivo / Real",
    load_error: "No se pudieron cargar los objetivos.",
    loading: "Cargando …",
    no_targets: (hasFilter) =>
      `No hay objetivos definidos${hasFilter ? " (para este filtro)" : ""}.`,
    period_day: "al día",
    period_week: "esta semana",
    period_month: "este mes",
    remaining: (n, period) => `${n}× más ${period}`,
    target_done: "Objetivo alcanzado",
    until: (date) => `hasta ${date}`,
    target_aria: (name, ist, count, period, pct, onTrack) =>
      `${name}: ${ist} de ${count} ${period}, ${pct} por ciento${
        onTrack ? ", al día" : ", atrasado"
      }`,
    ed_title: "Título",
    ed_period_filter: "Filtro de periodo",
    ed_opt_all: "Todos",
    ed_opt_daily: "Diario",
    ed_opt_weekly: "Semanal",
    ed_opt_monthly: "Mensual",
    ed_person_filter: "Filtro de persona (person_id)",
    ed_person_placeholder: "p. ej. per_1a2b3c4d",
  },
};

// Für die Datumsformatierung passende Locale je Sprache.
const DATE_LOCALE = { de: "de-DE", en: "en-GB", es: "es-ES" };

// Sprache aus HA ableiten (Fallback en → de) und Key nachschlagen.
function langOf(hass) {
  return (
    (hass && ((hass.locale && hass.locale.language) || hass.language)) ||
    "de"
  ).split("-")[0];
}

function translate(hass, key, args) {
  const lang = langOf(hass);
  const table = STRINGS[lang] || STRINGS.en || STRINGS.de;
  let v = table[key];
  if (v === undefined)
    v = STRINGS.en[key] !== undefined ? STRINGS.en[key] : STRINGS.de[key];
  return typeof v === "function" ? v(...args) : v;
}

class HausarbeitTargetsCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      _config: { state: true },
      _targets: { state: true },
      _error: { state: true },
      _loading: { state: true },
    };
  }

  constructor() {
    super();
    this._targets = [];
    this._error = null;
    this._loading = true;
    this._unsub = null;
    this._loaded = false;
    this._reloadTimer = null;
  }

  setConfig(config) {
    this._config = { ...config };
  }

  static getStubConfig() {
    return {};
  }

  static getConfigElement() {
    return document.createElement("hausarbeit-targets-card-editor");
  }

  getCardSize() {
    return 4;
  }

  set hass(hass) {
    const first = this._hass === undefined;
    this._hass = hass;
    if (first && hass) {
      this._subscribe();
      this._loadData();
    }
  }

  get hass() {
    return this._hass;
  }

  _t(key, ...args) {
    return translate(this._hass, key, args);
  }

  _period(p) {
    const key = { day: "period_day", week: "period_week", month: "period_month" }[
      p
    ];
    return key ? this._t(key) : p || "";
  }

  connectedCallback() {
    super.connectedCallback();
    if (this._hass && !this._unsub) {
      this._subscribe();
      if (!this._loaded) this._loadData();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._cleanupSub();
    if (this._reloadTimer) {
      clearTimeout(this._reloadTimer);
      this._reloadTimer = null;
    }
  }

  async _subscribe() {
    if (!this._hass || this._unsub) return;
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        () => this._scheduleReload(),
        { type: WS_SUBSCRIBE }
      );
    } catch (err) {
      this._unsub = null;
    }
  }

  _cleanupSub() {
    if (this._unsub) {
      try {
        this._unsub();
      } catch (e) {
        /* ignore */
      }
      this._unsub = null;
    }
  }

  _scheduleReload() {
    if (this._reloadTimer) return;
    this._reloadTimer = setTimeout(() => {
      this._reloadTimer = null;
      this._loadData();
    }, 400);
  }

  async _loadData() {
    if (!this._hass) return;
    this._loading = true;
    try {
      const res = await this._hass.connection.sendMessagePromise({
        type: WS_TARGETS,
      });
      let targets = (res && res.targets) || [];
      if (this._config.person) {
        targets = targets.filter((t) => t.person_id === this._config.person);
      }
      if (this._config.period) {
        targets = targets.filter((t) => t.period === this._config.period);
      }
      this._targets = targets;
      this._error = null;
      this._loaded = true;
    } catch (err) {
      this._error = this._t("load_error");
    } finally {
      this._loading = false;
    }
  }

  // Gruppiert Targets nach Person (stabile Reihenfolge nach erstem Auftreten).
  _groupByPerson() {
    const groups = new Map();
    for (const t of this._targets) {
      if (!groups.has(t.person_id)) {
        groups.set(t.person_id, { name: t.person_name, items: [] });
      }
      groups.get(t.person_id).items.push(t);
    }
    return Array.from(groups.values());
  }

  render() {
    if (!this._config) return html``;
    const title = this._config.title || this._t("title_default");
    return html`
      <ha-card .header=${title}>
        <div class="content">
          ${this._error
            ? html`<div class="error" role="alert">${this._error}</div>`
            : this._loading && !this._loaded
            ? html`<div class="hint">${this._t("loading")}</div>`
            : this._renderBody()}
        </div>
      </ha-card>
    `;
  }

  _renderBody() {
    if (!this._targets.length) {
      return html`<div class="hint">
        ${this._t("no_targets", !!(this._config.person || this._config.period))}
      </div>`;
    }
    const groups = this._groupByPerson();
    return html`
      ${groups.map(
        (g) => html`
          <div class="person-group">
            <div class="person-name">${g.name}</div>
            ${g.items.map((t) => this._renderTarget(t))}
          </div>
        `
      )}
    `;
  }

  _renderTarget(t) {
    const pct = Number(t.percent) || 0;
    const capped = Math.max(0, Math.min(100, pct));
    // Farbe: grün wenn on_track, sonst je nach Fortschritt warnend/rot.
    let color = "var(--success-color)";
    if (!t.on_track) {
      color = pct >= 50 ? "var(--warning-color)" : "var(--error-color)";
    }
    const periodLabel = this._period(t.period);
    const rest = Number(t.rest) || 0;
    return html`
      <div class="target">
        <div class="target-head">
          <span class="task">${t.task_name}</span>
          <span class="count">
            ${t.ist}/${t.count}
            <span class="muted">· ${periodLabel} · ${Math.round(pct)}%</span>
          </span>
        </div>
        <div
          class="bar-track"
          role="img"
          aria-label=${this._t(
            "target_aria",
            t.task_name,
            t.ist,
            t.count,
            periodLabel,
            Math.round(pct),
            !!t.on_track
          )}
        >
          <div class="bar-fill" style="width:${capped}%; background:${color};"></div>
        </div>
        <div class="target-foot">
          ${rest > 0
            ? html`<span class="rest" style="color:${color};"
                >${this._t("remaining", rest, periodLabel)}</span
              >`
            : html`<span class="rest done">${this._t("target_done")}</span>`}
          ${t.period_end
            ? html`<span class="end muted"
                >${this._t("until", this._fmtDate(t.period_end))}</span
              >`
            : ""}
        </div>
      </div>
    `;
  }

  _fmtDate(iso) {
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      const locale = DATE_LOCALE[langOf(this._hass)] || "de-DE";
      return d.toLocaleDateString(locale, {
        day: "2-digit",
        month: "2-digit",
      });
    } catch (e) {
      return iso;
    }
  }

  static get styles() {
    return css`
      ha-card {
        border-radius: var(--ha-card-border-radius, 12px);
      }
      .content {
        padding: 0 16px 16px 16px;
      }
      .person-group {
        margin-top: 12px;
      }
      .person-name {
        font-weight: 700;
        color: var(--primary-text-color);
        margin-bottom: 8px;
        padding-bottom: 4px;
        border-bottom: 1px solid var(--divider-color);
      }
      .target {
        margin-bottom: 14px;
      }
      .target-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 8px;
        margin-bottom: 4px;
        font-size: 0.95em;
      }
      .task {
        font-weight: 600;
        color: var(--primary-text-color);
      }
      .count {
        color: var(--primary-text-color);
        white-space: nowrap;
      }
      .muted {
        color: var(--secondary-text-color);
        font-size: 0.9em;
      }
      .bar-track {
        width: 100%;
        height: 12px;
        border-radius: 6px;
        background: var(--divider-color);
        overflow: hidden;
      }
      .bar-fill {
        height: 100%;
        border-radius: 6px;
        transition: width 0.3s ease;
      }
      .target-foot {
        display: flex;
        justify-content: space-between;
        margin-top: 4px;
        font-size: 0.85em;
      }
      .rest.done {
        color: var(--success-color);
      }
      .hint {
        padding: 12px 0;
        color: var(--secondary-text-color);
      }
      .error {
        padding: 8px 10px;
        border-radius: 8px;
        color: var(--error-color);
        border: 1px solid var(--error-color);
      }
    `;
  }
}

customElements.define("hausarbeit-targets-card", HausarbeitTargetsCard);

// --------------------------------------------------------------------------- //
// Config-Editor
// --------------------------------------------------------------------------- //
class HausarbeitTargetsCardEditor extends LitElement {
  static get properties() {
    return { hass: { attribute: false }, _config: { state: true } };
  }

  setConfig(config) {
    this._config = { ...config };
  }

  _t(key, ...args) {
    return translate(this.hass, key, args);
  }

  _emit(cfg) {
    this._config = cfg;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: cfg },
        bubbles: true,
        composed: true,
      })
    );
  }

  _valueChanged(ev) {
    if (!this._config) return;
    const target = ev.target;
    const key = target.getAttribute("data-key");
    const value = target.value;
    const cfg = { ...this._config };
    if (value === "" || value === undefined) delete cfg[key];
    else cfg[key] = value;
    this._emit(cfg);
  }

  render() {
    if (!this._config) return html``;
    return html`
      <div class="form">
        <label>
          ${this._t("ed_title")}
          <input
            type="text"
            data-key="title"
            .value=${this._config.title || ""}
            @input=${this._valueChanged}
          />
        </label>
        <label>
          ${this._t("ed_period_filter")}
          <select
            data-key="period"
            .value=${this._config.period || ""}
            @change=${this._valueChanged}
          >
            <option value="">${this._t("ed_opt_all")}</option>
            <option value="day">${this._t("ed_opt_daily")}</option>
            <option value="week">${this._t("ed_opt_weekly")}</option>
            <option value="month">${this._t("ed_opt_monthly")}</option>
          </select>
        </label>
        <label>
          ${this._t("ed_person_filter")}
          <input
            type="text"
            data-key="person"
            .value=${this._config.person || ""}
            @input=${this._valueChanged}
            placeholder=${this._t("ed_person_placeholder")}
          />
        </label>
      </div>
    `;
  }

  static get styles() {
    return css`
      .form {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 8px 0;
      }
      label {
        display: flex;
        flex-direction: column;
        gap: 4px;
        color: var(--primary-text-color);
      }
      input,
      select {
        padding: 8px 10px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
      }
    `;
  }
}

customElements.define(
  "hausarbeit-targets-card-editor",
  HausarbeitTargetsCardEditor
);

window.customCards = window.customCards || [];
(() => {
  // Picker-Text folgt der Browser-/HA-Sprache (statisch beim Laden; Fallback en -> de).
  const P = {
    de: { name: "Hausarbeit: Soll/Ist", description: "Fortschritt der Hausarbeit-Ziele je Person mit Balken." },
    en: { name: "Hausarbeit: Targets", description: "Target vs. actual progress per person, with bars." },
    es: { name: "Hausarbeit: Objetivos", description: "Progreso objetivo/real por persona, con barras." },
  };
  const lang = ((typeof navigator !== "undefined" && navigator.language) || "en").split("-")[0];
  const t = P[lang] || P.en;
  window.customCards.push({
    type: "hausarbeit-targets-card",
    name: t.name,
    description: t.description,
    preview: true,
    documentationURL: "https://github.com/Jo-Highness/hausarbeit",
  });
})();

}
_haInit();
