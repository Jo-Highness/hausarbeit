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

// --- WebSocket-Befehle (müssen exakt const.py entsprechen) ---------------- //
const WS_PERSONS = "hausarbeit/persons";
const WS_TASKS = "hausarbeit/tasks";
const WS_LOG_EXECUTION = "hausarbeit/log_execution";
const WS_DELETE_EXECUTION = "hausarbeit/delete_execution";
const WS_SUBSCRIBE = "hausarbeit/subscribe";

// --- Übersetzungen (kein Build/Import → Tabelle inline pro Karte) ---------- //
const STRINGS = {
  de: {
    title_default: "Erledigt melden",
    load_error: "Daten konnten nicht geladen werden.",
    select_person_first: "Bitte zuerst eine Person wählen.",
    logged: (task, pName) =>
      `${task}${pName ? " für " + pName : ""} eingetragen.`,
    undone: "Eintrag rückgängig gemacht.",
    undo_failed: "Rückgängig fehlgeschlagen.",
    log_failed: "Eintragen fehlgeschlagen.",
    loading: "Lade …",
    no_persons:
      "Keine Personen vorhanden. Bitte in den Hausarbeit-Einstellungen anlegen.",
    no_tasks:
      "Keine aktiven Aufgaben vorhanden. Bitte in den Hausarbeit-Einstellungen anlegen.",
    person: "Person",
    select_person: "Person wählen",
    task_heading: (name) => (name ? `Aufgabe für ${name}` : "Aufgabe"),
    log_task_group: "Aufgabe eintragen",
    note_placeholder: "Notiz (optional)",
    note_label: "Notiz",
    backdate_summary: "Nachtragen (Zeitpunkt setzen)",
    exec_time_label: "Zeitpunkt der Ausführung",
    use_now: "Jetzt verwenden",
    reset_time: "Zeitpunkt zurücksetzen",
    person_named: (name) => "Person " + name,
    log_task_named: (name) => "Aufgabe eintragen: " + name,
    select_person_first_short: "Bitte zuerst Person wählen",
    points: (n) => `${n} P`,
    undo_last: "Letzten Eintrag rückgängig machen",
    undo: "Rückgängig",
    ed_title: "Titel",
    ed_columns: "Spalten",
    ed_show_note: "Notizfeld anzeigen",
    ed_filter_hint: () =>
      html`Filter <code>persons</code>/<code>tasks</code> (Listen von IDs) bei
      Bedarf direkt im YAML setzen.`,
  },
  en: {
    title_default: "Log a chore",
    load_error: "Could not load data.",
    select_person_first: "Please select a person first.",
    logged: (task, pName) => `${task}${pName ? " for " + pName : ""} logged.`,
    undone: "Entry undone.",
    undo_failed: "Undo failed.",
    log_failed: "Could not log the entry.",
    loading: "Loading …",
    no_persons: "No people yet. Please add them in the Hausarbeit settings.",
    no_tasks:
      "No active chores yet. Please add them in the Hausarbeit settings.",
    person: "Person",
    select_person: "Select person",
    task_heading: (name) => (name ? `Chore for ${name}` : "Chore"),
    log_task_group: "Log a chore",
    note_placeholder: "Note (optional)",
    note_label: "Note",
    backdate_summary: "Add later (set time)",
    exec_time_label: "Time of completion",
    use_now: "Use now",
    reset_time: "Reset time",
    person_named: (name) => "Person " + name,
    log_task_named: (name) => "Log chore: " + name,
    select_person_first_short: "Please select a person first",
    points: (n) => `${n} pt`,
    undo_last: "Undo last entry",
    undo: "Undo",
    ed_title: "Title",
    ed_columns: "Columns",
    ed_show_note: "Show note field",
    ed_filter_hint: () =>
      html`Set the <code>persons</code>/<code>tasks</code> filters (lists of IDs)
      directly in YAML if needed.`,
  },
  es: {
    title_default: "Registrar tarea",
    load_error: "No se pudieron cargar los datos.",
    select_person_first: "Selecciona primero una persona.",
    logged: (task, pName) =>
      `${task}${pName ? " para " + pName : ""} registrada.`,
    undone: "Entrada deshecha.",
    undo_failed: "No se pudo deshacer.",
    log_failed: "No se pudo registrar la entrada.",
    loading: "Cargando …",
    no_persons: "Aún no hay personas. Añádelas en los ajustes de Hausarbeit.",
    no_tasks:
      "Aún no hay tareas activas. Añádelas en los ajustes de Hausarbeit.",
    person: "Persona",
    select_person: "Elegir persona",
    task_heading: (name) => (name ? `Tarea para ${name}` : "Tarea"),
    log_task_group: "Registrar tarea",
    note_placeholder: "Nota (opcional)",
    note_label: "Nota",
    backdate_summary: "Registrar después (fijar hora)",
    exec_time_label: "Hora de realización",
    use_now: "Usar ahora",
    reset_time: "Restablecer hora",
    person_named: (name) => "Persona " + name,
    log_task_named: (name) => "Registrar tarea: " + name,
    select_person_first_short: "Selecciona primero una persona",
    points: (n) => `${n} pt`,
    undo_last: "Deshacer última entrada",
    undo: "Deshacer",
    ed_title: "Título",
    ed_columns: "Columnas",
    ed_show_note: "Mostrar campo de nota",
    ed_filter_hint: () =>
      html`Configura los filtros <code>persons</code>/<code>tasks</code> (listas
      de IDs) directamente en el YAML si es necesario.`,
  },
};

// Sprache aus HA ableiten (Fallback en → de) und Key nachschlagen.
function translate(hass, key, args) {
  const lang = (
    (hass && ((hass.locale && hass.locale.language) || hass.language)) ||
    "de"
  ).split("-")[0];
  const table = STRINGS[lang] || STRINGS.en || STRINGS.de;
  let v = table[key];
  if (v === undefined)
    v = STRINGS.en[key] !== undefined ? STRINGS.en[key] : STRINGS.de[key];
  return typeof v === "function" ? v(...args) : v;
}

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
    return { show_note: false, columns: 3 };
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

  _t(key, ...args) {
    return translate(this._hass, key, args);
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
      this._error = this._t("load_error");
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
      this._error = this._t("select_person_first");
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
        text: this._t("logged", task.name, pName),
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
      this._error = this._t("log_failed");
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
      this._feedback = { text: this._t("undone"), executionId: null };
      if (this._fbTimer) clearTimeout(this._fbTimer);
      this._fbTimer = setTimeout(() => {
        this._feedback = null;
      }, 4000);
    } catch (err) {
      this._error = this._t("undo_failed");
    }
  }

  // --- Render ------------------------------------------------------------- //
  render() {
    if (!this._config) return html``;
    const title = this._config.title || this._t("title_default");
    const columns = Number(this._config.columns) > 0 ? Number(this._config.columns) : 3;

    return html`
      <ha-card .header=${title}>
        <div class="content">
          ${this._loading && !this._loaded
            ? html`<div class="hint">${this._t("loading")}</div>`
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
                        aria-label=${this._t("undo_last")}
                      >
                        ${this._t("undo")}
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
      return html`<div class="hint">${this._t("no_persons")}</div>`;
    }
    if (!this._tasks.length) {
      return html`<div class="hint">${this._t("no_tasks")}</div>`;
    }

    const multiPerson = this._persons.length > 1;
    return html`
      ${multiPerson
        ? html`
            <div class="section-label">${this._t("person")}</div>
            <div
              class="persons"
              role="group"
              aria-label=${this._t("select_person")}
            >
              ${this._persons.map((p) => this._renderPersonChip(p))}
            </div>
          `
        : ""}
      <div class="section-label">
        ${this._t(
          "task_heading",
          !multiPerson && this._persons.length === 1
            ? this._persons[0].name
            : ""
        )}
      </div>
      <div
        class="tasks"
        style="grid-template-columns: repeat(${columns}, 1fr);"
        role="group"
        aria-label=${this._t("log_task_group")}
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
              placeholder=${this._t("note_placeholder")}
              aria-label=${this._t("note_label")}
            />
          `
        : ""}
      <details class="nachtrag">
        <summary>${this._t("backdate_summary")}</summary>
        <input
          type="datetime-local"
          .value=${this._customTs}
          @input=${(e) => (this._customTs = e.target.value)}
          aria-label=${this._t("exec_time_label")}
        />
        ${this._customTs
          ? html`<button
              class="clear-ts"
              @click=${() => (this._customTs = "")}
              aria-label=${this._t("reset_time")}
            >
              ${this._t("use_now")}
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
        aria-label=${this._t("person_named", p.name)}
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
        aria-label=${this._t("log_task_named", t.name)}
        title=${disabled ? this._t("select_person_first_short") : t.name}
      >
        ${t.icon ? html`<ha-icon icon=${t.icon}></ha-icon>` : ""}
        <span class="task-name">${t.name}</span>
        ${t.points && t.points !== 1
          ? html`<span class="pts">${this._t("points", t.points)}</span>`
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

  _t(key, ...args) {
    return translate(this.hass, key, args);
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
          ${this._t("ed_title")}
          <input
            type="text"
            data-key="title"
            .value=${this._config.title || ""}
            @input=${this._valueChanged}
          />
        </label>
        <label>
          ${this._t("ed_columns")}
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
          ${this._t("ed_show_note")}
        </label>
        <p class="note">${this._t("ed_filter_hint")}</p>
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
(() => {
  // Picker-Text folgt der Browser-/HA-Sprache (statisch beim Laden; Fallback en -> de).
  const P = {
    de: { name: "Hausarbeit: Erledigt melden", description: "Schnelles Eintragen erledigter Hausarbeit (Person + Aufgabe)." },
    en: { name: "Hausarbeit: Log a chore", description: "Quickly log a completed chore (person + task)." },
    es: { name: "Hausarbeit: Registrar tarea", description: "Registra rápidamente una tarea del hogar (persona + tarea)." },
  };
  const lang = ((typeof navigator !== "undefined" && navigator.language) || "en").split("-")[0];
  const t = P[lang] || P.en;
  window.customCards.push({
    type: "hausarbeit-claim-card",
    name: t.name,
    description: t.description,
    preview: true,
    documentationURL: "https://github.com/Jo-Highness/hausarbeit",
  });
})();

}
_haInit();
