/** Chat UI module.
 *
 * Handles chat session management and message rendering with RAG responses.
 */

import {
  createChatSession,
  getChatSessions,
  getSessionMessages,
  sendChatMessage,
} from "./api.js";

// ============================================================================
// State
// ============================================================================

let currentSessionId = null;
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

    // Render assistant message
    const assistantCard = renderMessage({
      role: "assistant",
      content: response.answer_text,
      created_at: new Date().toISOString(),
    });
    output.appendChild(assistantCard);

    // Show sources if available
    if (response.sources && response.sources.length > 0) {
      showSourcePanel(response.sources);
    }

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
  const { form, output, sourcePanel } = getElements();
  if (!form || !output) return;

  // Clear previous content
  output.innerHTML = '<p class="muted">Sohbet yükleniyor...</p>';
  if (sourcePanel) {
    sourcePanel.classList.add("hidden");
  }

  // Set up form handler
  form.addEventListener("submit", handleSubmit);

  // Initialize session
  initializeSession();
}
