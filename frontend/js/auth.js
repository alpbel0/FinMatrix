function setToken(token) {
  localStorage.setItem("finmatrix_token", token);
}

function clearToken() {
  localStorage.removeItem("finmatrix_token");
}

function isAuthenticated() {
  return Boolean(localStorage.getItem("finmatrix_token"));
}

function requireAuth() {
  const protectedPages = ["dashboard.html", "chat.html", "watchlist.html"];
  const page = window.location.pathname.split("/").pop();
  if (protectedPages.includes(page) && !isAuthenticated()) {
    window.location.href = "login.html";
  }
}

window.FinMatrixAuth = { setToken, clearToken, isAuthenticated, requireAuth };
