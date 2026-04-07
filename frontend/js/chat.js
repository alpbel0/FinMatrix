import { mockData } from "./api.js";

export function renderChat() {
  const output = document.querySelector("#chat-output");
  const form = document.querySelector("#chat-form");
  const input = document.querySelector("#chat-input");
  if (!output || !form || !input) return;

  const renderMessage = (message) => {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `<strong>${message.role}</strong><p>${message.content}</p><p class="muted">${(message.sources || []).join(", ")}</p>`;
    output.appendChild(card);
  };

  output.innerHTML = "";
  mockData.chat.forEach(renderMessage);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    renderMessage({ role: "user", content: input.value, sources: [] });
    renderMessage({ role: "assistant", content: "Week 1 mock response.", sources: ["Mock source"] });
    form.reset();
  });
}
