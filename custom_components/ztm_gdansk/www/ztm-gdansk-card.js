import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit@2.8.0/index.js?module";

class ZtmGdanskCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      _config: { type: Object },
    };
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("'entity' is required in card config");
    }
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
  }

  get hass() {
    return this._hass;
  }

  static getConfigElement() {
    return document.createElement("ztm-gdansk-card-editor");
  }

  static getStubConfig() {
    return { entity: "" };
  }

  _formatTime(isoString) {
    if (!isoString) return "—";
    const dt = new Date(isoString);
    return dt.toLocaleTimeString("pl-PL", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  _formatLastUpdated(isoString) {
    if (!isoString) return "—";
    const dt = new Date(isoString);
    return dt.toLocaleTimeString("pl-PL", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  _delayCell(departure) {
    const { delay_minutes, status } = departure;
    if (status === "SCHEDULED" || delay_minutes === null || delay_minutes === undefined) {
      return html`<td class="delay gray">—</td>`;
    }
    if (delay_minutes > 0) {
      return html`<td class="delay red">+${delay_minutes} min</td>`;
    }
    return html`<td class="delay green">${delay_minutes} min</td>`;
  }

  render() {
    if (!this._config || !this._hass) return html``;

    const entityId = this._config.entity;
    const stateObj = this._hass.states[entityId];

    if (!stateObj) {
      return html`
        <ha-card>
          <div class="error">Encja ${entityId} nie istnieje.</div>
        </ha-card>
      `;
    }

    if (stateObj.state === "unavailable") {
      return html`
        <ha-card>
          <div class="header">
            ${this._config.title || stateObj.attributes.stop_name || entityId}
          </div>
          <div class="error">Brak danych — integracja niedostępna.</div>
        </ha-card>
      `;
    }

    const attrs = stateObj.attributes;
    const title = this._config.title || attrs.stop_name || entityId;
    const departures = attrs.departures || [];
    const lastUpdated = this._formatLastUpdated(stateObj.last_updated);

    return html`
      <ha-card>
        <div class="header">${title}</div>
        ${departures.length === 0
          ? html`<div class="empty">Brak odjazdów</div>`
          : html`
              <table>
                <thead>
                  <tr>
                    <th>Linia</th>
                    <th>Kierunek</th>
                    <th>Odjazd</th>
                    <th>Opóźnienie</th>
                  </tr>
                </thead>
                <tbody>
                  ${departures.map(
                    (d) => html`
                      <tr>
                        <td class="line">${d.line}</td>
                        <td class="headsign">${d.headsign}</td>
                        <td class="time">${this._formatTime(d.estimated_time)}</td>
                        ${this._delayCell(d)}
                      </tr>
                    `
                  )}
                </tbody>
              </table>
            `}
        <div class="footer">Ostatnia aktualizacja: ${lastUpdated}</div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      ha-card {
        overflow: hidden;
      }
      .header {
        padding: 12px 16px 8px;
        font-size: 1.1em;
        font-weight: 500;
        color: var(--primary-text-color);
      }
      table {
        width: 100%;
        border-collapse: collapse;
        overflow-x: auto;
        display: block;
      }
      thead tr {
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }
      th {
        padding: 6px 12px;
        text-align: left;
        font-size: 0.8em;
        color: var(--secondary-text-color);
        white-space: nowrap;
      }
      td {
        padding: 8px 12px;
        color: var(--primary-text-color);
        white-space: nowrap;
      }
      tbody tr:nth-child(even) {
        background: var(--table-row-alternative-background-color, rgba(0,0,0,0.04));
      }
      .line {
        font-weight: 700;
        min-width: 40px;
      }
      .headsign {
        max-width: 180px;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .time {
        font-family: monospace;
      }
      .delay {
        font-weight: 500;
        min-width: 70px;
      }
      .delay.green {
        color: #4caf50;
      }
      .delay.red {
        color: #f44336;
      }
      .delay.gray {
        color: var(--secondary-text-color, #9e9e9e);
      }
      .footer {
        padding: 6px 16px 10px;
        font-size: 0.75em;
        color: var(--secondary-text-color);
      }
      .empty {
        padding: 16px;
        text-align: center;
        color: var(--secondary-text-color);
      }
      .error {
        padding: 12px 16px;
        color: var(--error-color, #f44336);
      }
    `;
  }
}

class ZtmGdanskCardEditor extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      _config: { type: Object },
    };
  }

  setConfig(config) {
    this._config = config;
  }

  _valueChanged(ev) {
    const config = { ...this._config, [ev.target.configValue]: ev.target.value };
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config } }));
  }

  render() {
    if (!this._config) return html``;
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${this._config}
        .schema=${[
          {
            name: "entity",
            selector: {
              entity: { domain: "sensor", integration: "ztm_gdansk" },
            },
          },
          {
            name: "title",
            selector: { text: {} },
          },
        ]}
        .computeLabel=${(s) =>
          s.name === "entity" ? "Encja sensora" : "Tytuł (opcjonalny)"}
        @value-changed=${(ev) => {
          this.dispatchEvent(
            new CustomEvent("config-changed", {
              detail: { config: ev.detail.value },
            })
          );
        }}
      ></ha-form>
    `;
  }
}

customElements.define("ztm-gdansk-card", ZtmGdanskCard);
customElements.define("ztm-gdansk-card-editor", ZtmGdanskCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "ztm-gdansk-card",
  name: "ZTM Gdańsk",
  description: "Wyświetla odjazdy w czasie rzeczywistym z przystanku ZTM Gdańsk.",
  preview: false,
  documentationURL:
    "https://github.com/harrrson/ZTM-Gdansk-Home-Assistant-integration",
});
