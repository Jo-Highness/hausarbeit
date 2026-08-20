/**
 * hausarbeit-stats-card
 * ---------------------
 * Lovelace-Custom-Card mit aggregierter Statistik für den Hausarbeit-Tracker.
 *
 * No-Build-LitElement: verwendet HA-eigenes Lit (kein CDN/Import). Reines ES2020.
 *
 * Zeigt umschaltbar (7/30/90 Tage):
 *  - Ranking der Personen (Balken mit share_percent, Anzahl, Punkte)
 *  - Aufschlüsselung pro Aufgabe (Tabelle Aufgabe x Person)
 *  - Personen-Summen (today/7/30/90/Monat/gesamt)
 */

const LitElement =
  customElements.get("ha-panel-lovelace") !== undefined
    ? Object.getPrototypeOf(customElements.get("ha-panel-lovelace"))
    : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const WS_STATS = "hausarbeit/stats";
const WS_SUBSCRIBE = "hausarbeit/subscribe";

const RANGE_OPTIONS = [7, 30, 90];

class HausarbeitStatsCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      _config: { state: true },
      _stats: { state: true },
      _days: { state: true },
      _view: { state: true },
      _error: { state: true },
      _loading: { state: true },
    };
  }

  constructor() {
    super();
    this._stats = null;
    this._days = 90;
    this._view = "ranking";
    this._error = null;
    this._loading = true;
    this._unsub = null;
    this._loaded = false;
    this._reloadTimer = null;
  }

  setConfig(config) {
    this._config = { ...config };
    this._days = Number(config.days) > 0 ? Number(config.days) : 90;
    // Default-Zeitraum auf die nächstliegende erlaubte Stufe bringen.
    if (!RANGE_OPTIONS.includes(this._days)) {
      this._days = RANGE_OPTIONS.reduce((a, b) =>
        Math.abs(b - this._days) < Math.abs(a - this._days) ? b : a
      );
    }
    if (config.default_view === "tasks" || config.default_view === "ranking") {
      this._view = config.default_view;
    }
  }

  static getStubConfig() {
    return { title: "Hausarbeit-Statistik", days: 90, default_view: "ranking" };
  }

  static getConfigElement() {
    return document.createElement("hausarbeit-stats-card-editor");
  }

  getCardSize() {
    return 6;
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
        type: WS_STATS,
        days: this._days,
      });
      this._stats = res || null;
      this._error = null;
      this._loaded = true;
    } catch (err) {
      this._error = "Statistik konnte nicht geladen werden.";
    } finally {
      this._loading = false;
    }
  }

  _setDays(d) {
    if (this._days === d) return;
    this._days = d;
    this._loadData();
  }

  _setView(v) {
    this._view = v;
  }

  render() {
    if (!this._config) return html``;
    const title = this._config.title || "Hausarbeit-Statistik";
    return html`
      <ha-card .header=${title}>
        <div class="content">
          <div class="controls">
            <div class="segmented" role="group" aria-label="Zeitraum wählen">
              ${RANGE_OPTIONS.map(
                (d) => html`
                  <button
                    class=${this._days === d ? "active" : ""}
                    @click=${() => this._setDays(d)}
                    aria-pressed=${this._days === d ? "true" : "false"}
                  >
                    ${d} Tage
                  </button>
                `
              )}
            </div>
            <div class="segmented" role="group" aria-label="Ansicht wählen">
              <button
                class=${this._view === "ranking" ? "active" : ""}
                @click=${() => this._setView("ranking")}
                aria-pressed=${this._view === "ranking" ? "true" : "false"}
              >
                Ranking
              </button>
              <button
                class=${this._view === "tasks" ? "active" : ""}
                @click=${() => this._setView("tasks")}
                aria-pressed=${this._view === "tasks" ? "true" : "false"}
              >
                Aufgaben
              </button>
            </div>
          </div>

          ${this._error
            ? html`<div class="error" role="alert">${this._error}</div>`
            : this._loading && !this._loaded
            ? html`<div class="hint">Lade …</div>`
            : this._renderStats()}
        </div>
      </ha-card>
    `;
  }

  _renderStats() {
    const s = this._stats;
    if (!s) return html`<div class="hint">Keine Daten.</div>`;
    return html`
      ${this._view === "ranking" ? this._renderRanking(s) : this._renderTasks(s)}
      ${this._renderPerPerson(s)}
    `;
  }

  _renderRanking(s) {
    const ranking = (s.ranking || [])
      .slice()
      .sort((a, b) => (b.count || 0) - (a.count || 0));
    if (!ranking.length) {
      return html`<div class="hint">Keine Einträge im Zeitraum.</div>`;
    }
    return html`
      <div class="block-label">Ranking (${s.days ?? this._days} Tage)</div>
      <div class="ranking">
        ${ranking.map((r) => {
          const pct = Math.max(0, Math.min(100, Number(r.share_percent) || 0));
          return html`
            <div class="rank-row">
              <div class="rank-head">
                <span class="rank-name">${r.person_name}</span>
                <span class="rank-vals">
                  ${r.count}×
                  <span class="muted">· ${r.points} P · ${Math.round(pct)}%</span>
                </span>
              </div>
              <div
                class="bar-track"
                role="img"
                aria-label=${r.person_name +
                ": " +
                r.count +
                " Erledigungen, " +
                Math.round(pct) +
                " Prozent Anteil"}
              >
                <div class="bar-fill" style="width:${pct}%"></div>
              </div>
            </div>
          `;
        })}
      </div>
    `;
  }

  _renderTasks(s) {
    const perTask = s.per_task || [];
    if (!perTask.length) {
      return html`<div class="hint">Keine Aufgaben-Daten im Zeitraum.</div>`;
    }
    // Personen-Spalten aus den per_person-Listen zusammenführen (stabile Reihenfolge).
    const personMap = new Map();
    perTask.forEach((t) =>
      (t.per_person || []).forEach((pp) => {
        if (!personMap.has(pp.person_id))
          personMap.set(pp.person_id, pp.person_name);
      })
    );
    const persons = Array.from(personMap.entries()); // [id, name]

    return html`
      <div class="block-label">Pro Aufgabe (${s.days ?? this._days} Tage)</div>
      <div class="table-scroll">
        <table class="grid">
          <thead>
            <tr>
              <th scope="col">Aufgabe</th>
              ${persons.map(([, name]) => html`<th scope="col">${name}</th>`)}
              <th scope="col">Σ</th>
            </tr>
          </thead>
          <tbody>
            ${perTask.map((t) => {
              const byId = new Map(
                (t.per_person || []).map((pp) => [pp.person_id, pp.count])
              );
              return html`
                <tr>
                  <th scope="row">${t.task_name}</th>
                  ${persons.map(
                    ([id]) => html`<td>${byId.get(id) || 0}</td>`
                  )}
                  <td class="sum">${t.count}</td>
                </tr>
              `;
            })}
          </tbody>
        </table>
      </div>
    `;
  }

  _renderPerPerson(s) {
    const pp = s.per_person || [];
    if (!pp.length) return "";
    return html`
      <div class="block-label">Personen-Summen</div>
      <div class="table-scroll">
        <table class="grid compact">
          <thead>
            <tr>
              <th scope="col">Person</th>
              <th scope="col">Heute</th>
              <th scope="col">7T</th>
              <th scope="col">30T</th>
              <th scope="col">90T</th>
              <th scope="col">Monat</th>
              <th scope="col">Gesamt</th>
              <th scope="col">Punkte</th>
            </tr>
          </thead>
          <tbody>
            ${pp.map(
              (p) => html`
                <tr>
                  <th scope="row">${p.person_name}</th>
                  <td>${p.today ?? 0}</td>
                  <td>${p.d7 ?? 0}</td>
                  <td>${p.d30 ?? 0}</td>
                  <td>${p.d90 ?? 0}</td>
                  <td>${p.current_month ?? 0}</td>
                  <td>${p.total ?? 0}</td>
                  <td>${p.points_total ?? 0}</td>
                </tr>
              `
            )}
          </tbody>
        </table>
      </div>
    `;
  }

  static get styles() {
    return css`
      ha-card {
        border-radius: var(--ha-card-border-radius, 12px);
      }
      .content {
        padding: 0 16px 16px 16px;
      }
      .controls {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
      }
      .segmented {
        display: inline-flex;
        border: 1px solid var(--divider-color);
        border-radius: 20px;
        overflow: hidden;
      }
      .segmented button {
        border: none;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        padding: 6px 14px;
        cursor: pointer;
        font-size: 0.9em;
      }
      .segmented button + button {
        border-left: 1px solid var(--divider-color);
      }
      .segmented button.active {
        background: var(--primary-color);
        color: var(--text-primary-color, var(--card-background-color));
      }
      .segmented button:focus-visible {
        outline: 2px solid var(--primary-color);
        outline-offset: -2px;
      }
      .block-label {
        color: var(--secondary-text-color);
        font-size: 0.85em;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 16px 0 8px 0;
      }
      .ranking {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .rank-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 4px;
        font-size: 0.95em;
      }
      .rank-name {
        font-weight: 600;
        color: var(--primary-text-color);
      }
      .rank-vals {
        color: var(--primary-text-color);
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
        background: var(--primary-color);
        border-radius: 6px;
        transition: width 0.3s ease;
      }
      .table-scroll {
        overflow-x: auto;
      }
      table.grid {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9em;
      }
      table.grid th,
      table.grid td {
        padding: 6px 10px;
        text-align: center;
        border-bottom: 1px solid var(--divider-color);
        color: var(--primary-text-color);
        white-space: nowrap;
      }
      table.grid thead th {
        color: var(--secondary-text-color);
        font-weight: 600;
      }
      table.grid th[scope="row"] {
        text-align: left;
        font-weight: 600;
      }
      table.grid td.sum,
      table.grid td.sum {
        font-weight: 700;
      }
      table.compact th,
      table.compact td {
        padding: 5px 8px;
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

customElements.define("hausarbeit-stats-card", HausarbeitStatsCard);

// --------------------------------------------------------------------------- //
// Config-Editor
// --------------------------------------------------------------------------- //
class HausarbeitStatsCardEditor extends LitElement {
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
    let value = target.value;
    if (key === "days") value = value === "" ? undefined : Number(value);
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
          Standard-Zeitraum (Tage)
          <select
            data-key="days"
            .value=${this._config.days != null ? String(this._config.days) : "90"}
            @change=${this._valueChanged}
          >
            <option value="7">7</option>
            <option value="30">30</option>
            <option value="90">90</option>
          </select>
        </label>
        <label>
          Standard-Ansicht
          <select
            data-key="default_view"
            .value=${this._config.default_view || "ranking"}
            @change=${this._valueChanged}
          >
            <option value="ranking">Ranking</option>
            <option value="tasks">Aufgaben</option>
          </select>
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

customElements.define("hausarbeit-stats-card-editor", HausarbeitStatsCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hausarbeit-stats-card",
  name: "Hausarbeit: Statistik",
  description:
    "Ranking, Aufgaben-Aufschlüsselung und Personen-Summen der Hausarbeit.",
  preview: true,
  documentationURL: "https://github.com/Jo-Highness/hausarbeit",
});
