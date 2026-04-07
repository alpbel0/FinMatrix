document.addEventListener("DOMContentLoaded", () => {
  const target = document.querySelector("[data-auth-state]");
  if (!target || !window.FinMatrixAuth) return;
  target.textContent = window.FinMatrixAuth.isAuthenticated() ? "Logged in" : "Guest";
});
