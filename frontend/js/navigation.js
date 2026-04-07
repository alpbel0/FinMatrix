import { getCurrentUser, getToken, logout } from "./auth.js";

const PROTECTED_PAGES = ["dashboard.html", "chat.html", "watchlist.html"];

export function isProtectedPage() {
  const page = window.location.pathname.split("/").pop();
  return PROTECTED_PAGES.includes(page);
}

export function checkAuthAndRedirect() {
  const token = getToken();
  if (isProtectedPage() && !token) {
    window.location.href = "/login.html";
    return false;
  }
  return true;
}

export async function updateAuthStateDisplay() {
  const target = document.querySelector("[data-auth-state]");
  if (!target) return;

  if (!getToken()) {
    target.textContent = "Guest";
    return;
  }

  try {
    const user = await getCurrentUser();
    if (user) {
      target.textContent = `Logged in as ${user.username}`;
    } else {
      target.textContent = "Guest";
      if (isProtectedPage()) {
        window.location.href = "/login.html";
      }
    }
  } catch {
    target.textContent = "Guest";
  }
}

export function setupLogoutButton() {
  const logoutBtn = document.querySelector("[data-logout]");
  if (!logoutBtn) return;

  logoutBtn.addEventListener("click", (e) => {
    e.preventDefault();
    logout();
  });
}

export async function initNavigation() {
  if (!checkAuthAndRedirect()) return false;
  await updateAuthStateDisplay();
  setupLogoutButton();
  return true;
}
