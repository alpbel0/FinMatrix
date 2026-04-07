const PROTECTED_PAGES = ["dashboard.html", "chat.html", "watchlist.html"];

function isProtectedPage() {
  const page = window.location.pathname.split("/").pop();
  return PROTECTED_PAGES.includes(page);
}

function checkAuthAndRedirect() {
  const token = window.FinMatrixAuth?.getToken();
  if (isProtectedPage() && !token) {
    window.location.href = "login.html";
    return false;
  }
  return true;
}

async function updateAuthStateDisplay() {
  const target = document.querySelector("[data-auth-state]");
  if (!target) return;

  if (window.FinMatrixAuth?.isAuthenticated()) {
    try {
      const user = await window.FinMatrixAuth.getCurrentUser();
      if (user) {
        target.textContent = `Logged in as ${user.username}`;
      } else {
        target.textContent = "Guest";
      }
    } catch {
      target.textContent = "Guest";
    }
  } else {
    target.textContent = "Guest";
  }
}

function setupLogoutButton() {
  const logoutBtn = document.querySelector("[data-logout]");
  if (logoutBtn && window.FinMatrixAuth) {
    logoutBtn.addEventListener("click", (e) => {
      e.preventDefault();
      window.FinMatrixAuth.logout();
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Check auth before anything else
  if (!checkAuthAndRedirect()) return;

  // Update auth state display
  updateAuthStateDisplay();

  // Setup logout button if present
  setupLogoutButton();
});

window.FinMatrixNavigation = { checkAuthAndRedirect, updateAuthStateDisplay, isProtectedPage };
