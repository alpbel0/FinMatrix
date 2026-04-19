/** Chat UI module.
 *
 * Handles chat session management and message rendering with RAG responses.
 */

import { Chart, registerables } from "chart.js";
import "chartjs-adapter-luxon";
import {
  createChatSession,
  getChatSessions,
  getSessionMessages,
  sendChatMessage,
} from "./api.js";

Chart.register(...registerables);

// ============================================================================
// State
// ============================================================================

let currentSessionId = null;
let chatCharts = []; // Track charts for cleanup
const CHAT_SESSION_STORAGE_KEY = "finmatrix_chat_session_id";
const LEGACY_MOCK_PATTERNS = [
  /week 1 mock response/i,
  /mock source/i,
  /thyao ve asels icin temel karsilastirma/i,
];

// ============================================================================
// DOM Helpers
// ============================================================================

function getElements() {
  return {
    output: document.querySelector("#chat-output"),
    form: document.querySelector("#chat-form"),
    input: document.querySelector("#chat-input"),
    sourcePanel: document.querySelector("#source-panel"),
    sourceCards: document.querySelector("#source-cards"),
    loading: document.querySelector("#chat-loading"),
    suggestedQuestions: document.querySelector("#suggested-questions"),
  };
}

function isLegacyMockMessage(message) {
  const content = message?.content ?? "";
  const sources = Array.isArray(message?.sources) ? message.sources : [];
  return (
    LEGACY_MOCK_PATTERNS.some((pattern) => pattern.test(content)) ||
    sources.some((source) => typeof source === "string" && LEGACY_MOCK_PATTERNS.some((pattern) => pattern.test(source)))
  );
}

function setStoredSessionId(sessionId) {
  if (sessionId) {
    sessionStorage.setItem(CHAT_SESSION_STORAGE_KEY, String(sessionId));
  } else {
    sessionStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
  }
}

function getStoredSessionId() {
  const value = sessionStorage.getItem(CHAT_SESSION_STORAGE_KEY);
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

// ============================================================================
// Rendering
// ============================================================================

function formatDateTime(dt) {
  if (!dt) return "";
  return new Date(dt).toLocaleDateString("tr-TR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderMessage(message) {
  const card = document.createElement("div");
  card.className = `card message-${message.role}`;
  card.innerHTML = `
    <div class="message-header">
      <strong>${message.role === "user" ? "Siz" : "Asistan"}</strong>
      <span class="muted">${formatDateTime(message.created_at)}</span>
    </div>
    <div class="message-content">${escapeHtml(message.content)}</div>
  `;

  // Render comparison table if present (assistant messages only)
  if (message.role === "assistant" && message.comparison_table) {
    const tableContainer = document.createElement("div");
    tableContainer.className = "comparison-table-container";
    tableContainer.innerHTML = renderComparisonTable(message.comparison_table);
    card.appendChild(tableContainer);
  }

  // Render chart if present (assistant messages only)
  if (message.role === "assistant" && message.chart) {
    renderChart(message.chart, card);
  }

  return card;
}

function renderSourceCard(source) {
  return `
    <div class="source-card">
      <div class="source-header">
        <span class="badge">${source.stock_symbol}</span>
        <span class="badge badge-secondary">${source.filing_type}</span>
      </div>
      <h4 class="source-title">${escapeHtml(source.report_title)}</h4>
      <p class="muted">${formatDateTime(source.published_at)}</p>
      <p class="source-preview">${escapeHtml(source.chunk_preview)}...</p>
      <a href="${source.source_url}" target="_blank" rel="noopener" class="source-link">
        KAP Kaynak →
      </a>
    </div>
  `;
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Render a chart from ChartPayload into a dynamically created canvas.
 * @param {Object} chartPayload - ChartPayload from backend: {type, title, series: [{name, data: [{date, value}]}]}
 * @param {HTMLElement} container - DOM element to inject canvas into
 */
function renderChart(chartPayload, container) {
  if (!chartPayload || !chartPayload.series || chartPayload.series.length === 0) return;

  const canvasId = `chat-chart-${Date.now()}`;
  const canvas = document.createElement("canvas");
  canvas.id = canvasId;
  canvas.style.maxHeight = "300px";
  canvas.style.margin = "12px 0";
  container.appendChild(canvas);

  const ctx = canvas.getContext("2d");

  const datasets = chartPayload.series.map((series, index) => {
    const colors = ["#1a7f64", "#4a90d9", "#d97b4a", "#9b59b6", "#27ae60"];
    const color = colors[index % colors.length];
    return {
      label: series.name,
      data: series.data.map((d) => ({ x: d.date, y: d.value })),
      borderColor: color,
      backgroundColor: `${color}1a`, // 10% opacity
      fill: true,
      tension: 0.1,
      pointRadius: 2,
    };
  });

  const chart = new Chart(ctx, {
    type: chartPayload.type || "line",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: "top" },
        title: { display: true, text: chartPayload.title, font: { size: 14 } },
      },
      scales: {
        x: { type: "time", time: { unit: "month" }, ticks: { maxTicksLimit: 8 } },
        y: { beginAtZero: false, ticks: { callback: (v) => v.toLocaleString() } },
      },
    },
  });

  chatCharts.push(chart);
}

/**
 * Show suggested questions as clickable buttons (sticky: only on latest message).
 * @param {HTMLElement} container - DOM element to inject buttons into
 */
function renderSuggestedQuestions(container) {
  const { suggestedQuestions } = getElements();
  if (!suggestedQuestions) return;

  // Clear previous suggestions
  suggestedQuestions.innerHTML = "";

  const questions = [
    "Bu hisse hakkında daha detaylı bilgi ister misin?",
    "Karşılaştırmalı analiz yapabilir misin?",
    "Farklı bir hisse hakkında ne düşünüyorsun?",
  ];

  questions.forEach((q) => {
    const btn = document.createElement("button");
    btn.className = "suggested-btn";
    btn.textContent = q;
    btn.addEventListener("click", () => {
      const { input } = getElements();
      if (input) {
        input.value = q;
        input.focus();
      }
    });
    suggestedQuestions.appendChild(btn);
  });

  suggestedQuestions.classList.remove("hidden");
}

/**
 * Render a comparison table from comparison_table data.
 * @param {Array} comparisonTable - list of {metric, values: {symbol: value}}
 * @returns {string} HTML string
 */
function renderComparisonTable(comparisonTable) {
  if (!comparisonTable || comparisonTable.length === 0) return "";

  const symbols = Object.keys(comparisonTable[0]?.values || {});

  let html = `<table class="comparison-table" style="width:100%; border-collapse: collapse; margin: 12px 0; font-size: 0.9rem;">`;
  html += `<thead><tr><th style="text-align:left; padding: 6px 8px; border-bottom: 2px solid var(--color-border);">Metrik</th>`;
  symbols.forEach((s) => {
    html += `<th style="text-align:right; padding: 6px 8px; border-bottom: 2px solid var(--color-border);">${escapeHtml(s)}</th>`;
  });
  html += `</tr></thead><tbody>`;

  comparisonTable.forEach((row) => {
    html += `<tr>`;
    html += `<td style="padding: 6px 8px; border-bottom: 1px solid var(--color-border); font-weight: 500;">${escapeHtml(row.metric)}</td>`;
    symbols.forEach((s) => {
      const val = row.values[s];
      const formatted = val !== null && val !== undefined ? val.toLocaleString("tr-TR", { maximumFractionDigits: 2 }) : "N/A";
      html += `<td style="text-align:right; padding: 6px 8px; border-bottom: 1px solid var(--color-border);">${formatted}</td>`;
    });
    html += `</tr>`;
  });

  html += `</tbody></table>`;
  return html;
}

/**
 * Hide suggested questions (called when new user message is sent).
 */
function hideSuggestedQuestions() {
  const { suggestedQuestions } = getElements();
  if (suggestedQuestions) {
    suggestedQuestions.innerHTML = "";
    suggestedQuestions.classList.add("hidden");
  }
}

function showLoading(show) {
  const { loading, form } = getElements();
  if (loading) {
    loading.classList.toggle("hidden", !show);
  }
  const button = form?.querySelector("button");
  if (button) {
    button.disabled = show;
    button.textContent = show ? "Gönderiliyor..." : "Gönder";
  }
}

function showSourcePanel(sources) {
  const { sourcePanel, sourceCards } = getElements();
  if (!sourcePanel || !sourceCards) return;

  if (sources && sources.length > 0) {
    sourceCards.innerHTML = sources.map(renderSourceCard).join("");
    sourcePanel.classList.remove("hidden");
  } else {
    sourcePanel.classList.add("hidden");
  }
}

// ============================================================================
// Session Management
// ============================================================================

async function initializeSession() {
  try {
    const sessions = await getChatSessions();
    const storedSessionId = getStoredSessionId();
    const existingSession = storedSessionId
      ? sessions.find((session) => session.id === storedSessionId)
      : null;

    if (existingSession) {
      currentSessionId = existingSession.id;
      await loadSessionHistory(currentSessionId);
      return;
    }

    const newSession = await createChatSession("Yeni Sohbet");
    currentSessionId = newSession.id;
    setStoredSessionId(currentSessionId);
    await loadSessionHistory(currentSessionId);
  } catch (error) {
    console.error("Session initialization error:", error);
  }
}

async function loadSessionHistory(sessionId) {
  const { output } = getElements();
  if (!output) return;

  try {
    const data = await getSessionMessages(sessionId);
    output.innerHTML = "";

    const safeMessages = (data.messages || []).filter((msg) => !isLegacyMockMessage(msg));

    if (safeMessages.length > 0) {
      safeMessages.forEach((msg) => {
        const card = renderMessage(msg);
        output.appendChild(card);
      });

      // Scroll to bottom
      output.scrollTop = output.scrollHeight;
    } else {
      output.innerHTML = '<p class="muted">Belge odaklı sohbet hazır.</p>';
    }
  } catch (error) {
    console.error("Load session history error:", error);
  }
}

// ============================================================================
// Message Handling
// ============================================================================

async function handleSubmit(event) {
  event.preventDefault();

  const { output, input } = getElements();
  if (!output || !input || !currentSessionId) return;

  const message = input.value.trim();
  if (!message) return;

  // Hide previous suggested questions (sticky behavior)
  hideSuggestedQuestions();

  // Destroy previous charts
  chatCharts.forEach((c) => c.destroy());
  chatCharts = [];

  // Render user message immediately
  const userCard = renderMessage({
    role: "user",
    content: message,
    created_at: new Date().toISOString(),
  });
  output.appendChild(userCard);
  input.value = "";

  // Show loading
  showLoading(true);
  showSourcePanel([]);

  try {
    const response = await sendChatMessage(currentSessionId, message);
    setStoredSessionId(currentSessionId);

    // Render assistant message with chart and comparison_table
    const assistantCard = renderMessage({
      role: "assistant",
      content: response.answer_text,
      created_at: new Date().toISOString(),
      chart: response.chart || null,
      comparison_table: response.comparison_table || null,
    });
    output.appendChild(assistantCard);

    // Show sources if available
    if (response.sources && response.sources.length > 0) {
      showSourcePanel(response.sources);
    }

    // Show suggested questions (sticky: only on latest message)
    renderSuggestedQuestions();

    // Scroll to bottom
    output.scrollTop = output.scrollHeight;
  } catch (error) {
    console.error("Send message error:", error);
    const errorCard = renderMessage({
      role: "assistant",
      content: "Mesaj gönderilirken bir hata oluştu. Lütfen tekrar deneyin.",
      created_at: new Date().toISOString(),
    });
    output.appendChild(errorCard);
  } finally {
    showLoading(false);
  }
}

// ============================================================================
// Initialization
// ============================================================================

export function renderChat() {
  const { form, output, sourcePanel, suggestedQuestions } = getElements();
  if (!form || !output) return;

  // Clear previous charts
  chatCharts.forEach((c) => c.destroy());
  chatCharts = [];

  // Clear previous content
  output.innerHTML = '<p class="muted">Sohbet yükleniyor...</p>';
  if (sourcePanel) {
    sourcePanel.classList.add("hidden");
  }
  if (suggestedQuestions) {
    suggestedQuestions.classList.add("hidden");
    suggestedQuestions.innerHTML = "";
  }

  // Set up form handler
  form.addEventListener("submit", handleSubmit);

  // Initialize session
  initializeSession();
}
