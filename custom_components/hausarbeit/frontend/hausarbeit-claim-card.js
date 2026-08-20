/**
 * hausarbeit-claim-card
 * ---------------------
 * Lovelace-Custom-Card "Erledigt melden" für den Hausarbeit-Tracker.
 *
 * No-Build-LitElement: verwendet das von Home Assistant selbst geladene Lit
 * (kein CDN, kein Import, keine Build-Pipeline). Reines ES2020.
 *
 * UX: Person wählen (Chip mit Icon/Farbe), dann Aufgabe antippen -> loggt eine
 * Ausführung via WebSocket. Ist nur eine Person konfiguriert/gewählt, genügt der
 * Aufgaben-Klick. Sofortiges Feedback + Undo (löscht zuletzt geloggte execution_id).
 */

// --- HA-eigenes Lit wiederverwenden (Pflicht-Pattern) --------------------- //
const LitElement =
  customElements.get("ha-panel-lovelace") !== undefined
    ? Object.getPrototypeOf(customElements.get("ha-panel-lovelace"))
    : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// --- WebSocket-Befehle (müssen exakt const.py entsprechen) ---------------- //
const WS_PERSONS = "hausarbeit/persons";
const WS_TASKS = "hausarbeit/tasks";
const WS_LOG_EXECUTION = "hausarbeit/log_execution";
const WS_DELETE_EXECUTION = "hausarbeit/delete_execution";
const WS_SUBSCRIBE = "hausarbeit/subscribe";

class HausarbeitClaimCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      _config: { state: true },
      _persons: { state: true },
      _tasks: { state: true },
      _selectedPerson: { state: true },
      _note: { state: true },
      _customTs: { state: true },
      _feedback: { state: true }, // {text, executionId} | null
      _error: { state: true },
      _loading: { state: true },
    };
  }

  constructor() {
    super();
    this._persons = [];
    this._tasks = [];
    this._selectedPerson = null;
    this._note = "";
    this._customTs = "";
    this._feedback = null;
    this._error = null;
    this._loading = true;
    this._unsub = null;
    this._loaded = false;
    this._reloadTimer = null;
  }

  // --- Lovelace-Pflichtmethoden ------------------------------------------- //
  setConfig(config) {
    this._config = { ...config };
  }

  static getStubConfig() {
    return { title: "Erledigt melden", show_note: false, columns: 3 };
  }

  static getConfigElement() {
    return document.createElement("hausarbeit-claim-card-editor");
  }

  getCardSize() {
    return 4;
  }

  set hass(hass) {
    const first = this._hass === undefined;
    this._hass = hass;
    // WS-Daten nur einmal initial laden; danach nur bei subscribe-Event.
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
    // Nach erneutem Einhängen ggf. Abo wiederherstellen.
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

  // --- Push-Abo bei Datenänderung ----------------------------------------- //
  async _subscribe() {
    if (!this._hass || this._unsub) return;
    try {
      this._unsub = await this._hass.connection.subscribeMessage(
        () => this._scheduleReload(),
        { type: WS_SUBSCRIBE }
      );
    } catch (err) {
      // Abo optional — Karte funktioniert auch ohne Push.
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

  // Throttle: bei mehreren Events kurz sammeln, dann einmal neu laden.
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
      const [pRes, tRes] = await Promise.all([
        this._hass.connection.sendMessagePromise({ type: WS_PERSONS }),
        this._hass.connection.sendMessagePromise({ type: WS_TASKS }),
      ]);
      let persons = (pRes && pRes.persons) || [];
      let tasks = (tRes && tRes.tasks) || [];

      // Config-Filter anwenden.
      if (Array.isArray(this._config.persons) && this._config.persons.length) {
        const allow = new Set(this._config.persons);
        persons = persons.filter((p) => allow.has(p.id));
      }
      if (Array.isArray(this._config.tasks) && this._config.tasks.length) {
        const allow = new Set(this._config.tasks);
        tasks = tasks.filter((t) => allow.has(t.id));
      }
      // Nur aktive Aufgaben.
      tasks = tasks.filter((t) => t.active !== false);

      this._persons = persons;
      this._tasks = tasks;
      this._error = null;
      this._loaded = true;

      // Auto-Select, wenn nur eine Person zur Verfügung steht.
      if (persons.length === 1) {
        this._selectedPerson = persons[0].id;
      } else if (
        this._selectedPerson &&
        !persons.some((p) => p.id === this._selectedPerson)
      ) {
        this._selectedPerson = null;
      }
    } catch (err) {
      this._error = "Daten konnten nicht geladen werden.";
    } finally {
      this._loading = false;
    }
  }

  // --- Aktionen ----------------------------------------------------------- //
  _selectPerson(id) {
    this._selectedPerson = this._selectedPerson === id ? null : id;
  }

  async _claim(task) {
    if (!this._hass) return;
    const personId = this._selectedPerson;
    if (!personId) {
      this._error = "Bitte zuerst eine Person wählen.";
      return;
    }
    this._error = null;
    const params = {
      type: WS_LOG_EXECUTION,
      person_id: personId,
      task_id: task.id,
    };
    if (this._config.show_note && this._note.trim()) {
      params.note = this._note.trim();
    }
    if (this._customTs) {
      // datetime-local liefert lokale Zeit ohne Zonensuffix; als ISO senden.
      const d = new Date(this._customTs);
      if (!isNaN(d.getTime())) params.ts = d.toISOString();
    }
    try {
      const res = await this._hass.connection.sendMessagePromise(params);
      const person = this._persons.find((p) => p.id === personId);
      const pName = person ? person.name : "";
      this._feedback = {
        text: `${task.name}${pName ? " für " + pName : ""} eingetragen.`,
        executionId: res && res.execution_id,
      };
      this._note = "";
      this._customTs = "";  // Nachtrage-Zeitpunkt nach dem Loggen zurücksetzen
      // Feedback nach einiger Zeit ausblenden.
      if (this._fbTimer) clearTimeout(this._fbTimer);
      this._fbTimer = setTimeout(() => {
        this._feedback = null;
      }, 8000);
    } catch (err) {
      this._error = "Eintragen fehlgeschlagen.";
    }
  }

  async _undo() {
    if (!this._hass || !this._feedback || !this._feedback.executionId) return;
    const id = this._feedback.executionId;
    try {
      await this._hass.connection.sendMessagePromise({
        type: WS_DELETE_EXECUTION,
        execution_id: id,
      });
      this._feedback = { text: "Eintrag rückgängig gemacht.", executionId: null };
      if (this._fbTimer) clearTimeout(this._fbTimer);
      this._fbTimer = setTimeout(() => {
        this._feedback = null;
      }, 4000);
    } catch (err) {
      this._error = "Rückgängig fehlgeschlagen.";
    }
  }

  // --- Render ------------------------------------------------------------- //
  render() {
    if (!this._config) return html``;
    const title = this._config.title || "Erledigt melden";
    const columns = Number(this._config.columns) > 0 ? Number(this._config.columns) : 3;

    return html`
      <ha-card .header=${title}>
        <div class="content">
          ${this._loading && !this._loaded
            ? html`<div class="hint">Lade …</div>`
            : this._renderBody(columns)}
          ${this._error
            ? html`<div class="error" role="alert" aria-live="assertive">
                ${this._error}
              </div>`
            : ""}
          <div class="feedback" aria-live="polite">
            ${this._feedback
              ? html`
                  <span>${this._feedback.text}</span>
                  ${this._feedback.executionId
                    ? html`<button
                        class="undo"
                        @click=${this._undo}
                        aria-label="Letzten Eintrag rückgängig machen"
                      >
                        Rückgängig
                      </button>`
                    : ""}
                `
              : ""}
          </div>
        </div>
      </ha-card>
    `;
  }

  _renderBody(columns) {
    if (!this._persons.length) {
      return html`<div class="hint">
        Keine Personen vorhanden. Bitte in den Hausarbeit-Einstellungen anlegen.
      </div>`;
    }
    if (!this._tasks.length) {
      return html`<div class="hint">
        Keine aktiven Aufgaben vorhanden. Bitte in den Hausarbeit-Einstellungen anlegen.
      </div>`;
    }

    const multiPerson = this._persons.length > 1;
    return html`
      ${multiPerson
        ? html`
            <div class="section-label">Person</div>
            <div class="persons" role="group" aria-label="Person wählen">
              ${this._persons.map((p) => this._renderPersonChip(p))}
            </div>
          `
        : ""}
      <div class="section-label">
        Aufgabe${!multiPerson && this._persons.length === 1
          ? html` für ${this._persons[0].name}`
          : ""}
      </div>
      <div
        class="tasks"
        style="grid-template-columns: repeat(${columns}, 1fr);"
        role="group"
        aria-label="Aufgabe eintragen"
      >
        ${this._tasks.map((t) => this._renderTaskButton(t))}
      </div>
      ${this._config.show_note
        ? html`
            <input
              class="note"
              type="text"
              .value=${this._note}
              @input=${(e) => (this._note = e.target.value)}
              placeholder="Notiz (optional)"
              aria-label="Notiz"
            />
          `
        : ""}
      <details class="nachtrag">
        <summary>Nachtragen (Zeitpunkt setzen)</summary>
        <input
          type="datetime-local"
          .value=${this._customTs}
          @input=${(e) => (this._customTs = e.target.value)}
          aria-label="Zeitpunkt der Ausführung"
        />
        ${this._customTs
          ? html`<button
              class="clear-ts"
              @click=${() => (this._customTs = "")}
              aria-label="Zeitpunkt zurücksetzen"
            >
              Jetzt verwenden
            </button>`
          : ""}
      </details>
    `;
  }

  _renderPersonChip(p) {
    const selected = this._selectedPerson === p.id;
    const color = p.color ? p.color : "var(--primary-color)";
    return html`
      <button
        class="person-chip ${selected ? "selected" : ""}"
        style=${selected ? `--chip-accent:${color};` : `--chip-accent:${color};`}
        @click=${() => this._selectPerson(p.id)}
        role="checkbox"
        aria-checked=${selected ? "true" : "false"}
        aria-label=${"Person " + p.name}
      >
        ${p.icon
          ? html`<ha-icon icon=${p.icon}></ha-icon>`
          : ""}
        <span>${p.name}</span>
      </button>
    `;
  }

  _renderTaskButton(t) {
    const disabled = !this._selectedPerson && this._persons.length > 1;
    return html`
      <button
        class="task-btn"
        ?disabled=${disabled}
        @click=${() => this._claim(t)}
        aria-label=${"Aufgabe eintragen: " + t.name}
        title=${disabled ? "Bitte zuerst Person wählen" : t.name}
      >
        ${t.icon ? html`<ha-icon icon=${t.icon}></ha-icon>` : ""}
        <span class="task-name">${t.name}</span>
        ${t.points && t.points !== 1
          ? html`<span class="pts">${t.points} P</span>`
          : ""}
      </button>
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
      .section-label {
        color: var(--secondary-text-color);
        font-size: 0.85em;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 12px 0 6px 0;
      }
      .persons {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .person-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border-radius: 20px;
        border: 2px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
        cursor: pointer;
        font-size: 0.95em;
        transition: border-color 0.15s, background 0.15s;
      }
      .person-chip ha-icon {
        color: var(--chip-accent, var(--primary-color));
      }
      .person-chip.selected {
        border-color: var(--chip-accent, var(--primary-color));
        background: color-mix(
          in srgb,
          var(--chip-accent, var(--primary-color)) 15%,
          var(--card-background-color)
        );
      }
      .person-chip:focus-visible {
        outline: 2px solid var(--primary-color);
        outline-offset: 2px;
      }
      .tasks {
        display: grid;
        gap: 8px;
      }
      .task-btn {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 4px;
        padding: 14px 8px;
        border-radius: var(--ha-card-border-radius, 12px);
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
        cursor: pointer;
        min-height: 64px;
        transition: background 0.15s, border-color 0.15s;
      }
      .task-btn ha-icon {
        color: var(--primary-color);
        --mdc-icon-size: 28px;
      }
      .task-btn:hover:not([disabled]) {
        border-color: var(--primary-color);
        background: color-mix(
          in srgb,
          var(--primary-color) 8%,
          var(--card-background-color)
        );
      }
      .task-btn:focus-visible {
        outline: 2px solid var(--primary-color);
        outline-offset: 2px;
      }
      .task-btn[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .task-name {
        text-align: center;
        font-size: 0.9em;
        line-height: 1.15;
      }
      .pts {
        font-size: 0.75em;
        color: var(--secondary-text-color);
      }
      .note {
        margin-top: 12px;
        width: 100%;
        box-sizing: border-box;
        padding: 8px 10px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
      }
      .nachtrag {
        margin-top: 12px;
        color: var(--secondary-text-color);
        font-size: 0.9em;
      }
      .nachtrag summary {
        cursor: pointer;
      }
      .nachtrag input {
        margin-top: 8px;
        padding: 6px 8px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
      }
      .clear-ts,
      .undo {
        margin-left: 8px;
        padding: 4px 10px;
        border-radius: 8px;
        border: 1px solid var(--primary-color);
        background: transparent;
        color: var(--primary-color);
        cursor: pointer;
      }
      .clear-ts:focus-visible,
      .undo:focus-visible {
        outline: 2px solid var(--primary-color);
        outline-offset: 2px;
      }
      .feedback {
        margin-top: 12px;
        min-height: 1.4em;
        color: var(--success-color, var(--primary-color));
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 4px;
      }
      .hint {
        padding: 12px 0;
        color: var(--secondary-text-color);
      }
      .error {
        margin-top: 12px;
        padding: 8px 10px;
        border-radius: 8px;
        color: var(--error-color);
        border: 1px solid var(--error-color);
      }
    `;
  }
}

customElements.define("hausarbeit-claim-card", HausarbeitClaimCard);

// --------------------------------------------------------------------------- //
// Einfacher Config-Editor
// --------------------------------------------------------------------------- //
class HausarbeitClaimCardEditor extends LitElement {
  static get properties() {
    return { hass: { attribute: false }, _config: { state: true } };
  }

  setConfig(config) {
    this._config = { ...config };
  }

  _emit(config) {
    this._config = config;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config },
        bubbles: true,
        composed: true,
      })
    );
  }

  _valueChanged(ev) {
    if (!this._config) return;
    const target = ev.target;
    const key = target.getAttribute("data-key");
    let value = target.type === "checkbox" ? target.checked : target.value;
    if (key === "columns") value = value === "" ? undefined : Number(value);
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
          Spalten
          <input
            type="number"
            min="1"
            max="6"
            data-key="columns"
            .value=${this._config.columns != null ? String(this._config.columns) : ""}
            @input=${this._valueChanged}
          />
        </label>
        <label class="row">
          <input
            type="checkbox"
            data-key="show_note"
            .checked=${!!this._config.show_note}
            @change=${this._valueChanged}
          />
          Notizfeld anzeigen
        </label>
        <p class="note">
          Filter <code>persons</code>/<code>tasks</code> (Listen von IDs) bei Bedarf
          direkt im YAML setzen.
        </p>
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
      label.row {
        flex-direction: row;
        align-items: center;
        gap: 8px;
      }
      input[type="text"],
      input[type="number"] {
        padding: 8px 10px;
        border-radius: 8px;
        border: 1px solid var(--divider-color);
        background: var(--card-background-color);
        color: var(--primary-text-color);
      }
      .note {
        color: var(--secondary-text-color);
        font-size: 0.85em;
      }
    `;
  }
}

customElements.define("hausarbeit-claim-card-editor", HausarbeitClaimCardEditor);

// --- Registrierung in der Karten-Auswahl ---------------------------------- //
window.customCards = window.customCards || [];
window.customCards.push({
  type: "hausarbeit-claim-card",
  name: "Hausarbeit: Erledigt melden",
  description: "Schnelles Eintragen erledigter Hausarbeit (Person + Aufgabe).",
  preview: true,
  documentationURL: "https://github.com/Jo-Highness/hausarbeit",
});
