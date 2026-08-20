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

const LitElement =
  customElements.get("ha-panel-lovelace") !== undefined
    ? Object.getPrototypeOf(customElements.get("ha-panel-lovelace"))
    : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const WS_TARGETS = "hausarbeit/targets";
const WS_SUBSCRIBE = "hausarbeit/subscribe";

const PERIOD_LABEL = {
  day: "täglich",
  week: "diese Woche",
  month: "diesen Monat",
};

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
    return { title: "Soll / Ist" };
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
      this._error = "Ziele konnten nicht geladen werden.";
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
    const title = this._config.title || "Soll / Ist";
    return html`
      <ha-card .header=${title}>
        <div class="content">
          ${this._error
            ? html`<div class="error" role="alert">${this._error}</div>`
            : this._loading && !this._loaded
            ? html`<div class="hint">Lade …</div>`
            : this._renderBody()}
        </div>
      </ha-card>
    `;
  }

  _renderBody() {
    if (!this._targets.length) {
      return html`<div class="hint">
        Keine Ziele definiert${this._config.person || this._config.period
          ? " (für diesen Filter)"
          : ""}.
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
    const periodLabel = PERIOD_LABEL[t.period] || t.period || "";
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
          aria-label=${t.task_name +
          ": " +
          t.ist +
          " von " +
          t.count +
          " " +
          periodLabel +
          ", " +
          Math.round(pct) +
          " Prozent" +
          (t.on_track ? ", im Plan" : ", im Rückstand")}
        >
          <div class="bar-fill" style="width:${capped}%; background:${color};"></div>
        </div>
        <div class="target-foot">
          ${rest > 0
            ? html`<span class="rest" style="color:${color};"
                >noch ${rest}× ${periodLabel}</span
              >`
            : html`<span class="rest done">Ziel erreicht</span>`}
          ${t.period_end
            ? html`<span class="end muted">bis ${this._fmtDate(t.period_end)}</span>`
            : ""}
        </div>
      </div>
    `;
  }

  _fmtDate(iso) {
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toLocaleDateString("de-DE", {
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
          Titel
          <input
            type="text"
            data-key="title"
            .value=${this._config.title || ""}
            @input=${this._valueChanged}
          />
        </label>
        <label>
          Periode-Filter
          <select
            data-key="period"
            .value=${this._config.period || ""}
            @change=${this._valueChanged}
          >
            <option value="">Alle</option>
            <option value="day">Täglich</option>
            <option value="week">Wöchentlich</option>
            <option value="month">Monatlich</option>
          </select>
        </label>
        <label>
          Personen-Filter (person_id)
          <input
            type="text"
            data-key="person"
            .value=${this._config.person || ""}
            @input=${this._valueChanged}
            placeholder="z. B. per_1a2b3c4d"
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
window.customCards.push({
  type: "hausarbeit-targets-card",
  name: "Hausarbeit: Soll/Ist",
  description: "Fortschritt der Hausarbeit-Ziele je Person mit Balken.",
  preview: true,
  documentationURL: "https://github.com/Jo-Highness/hausarbeit",
});
