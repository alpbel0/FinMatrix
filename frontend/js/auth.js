function setToken(token) {
  localStorage.setItem("finmatrix_token", token);
}

function clearToken() {
  localStorage.removeItem("finmatrix_token");
}

function getToken() {
  return localStorage.getItem("finmatrix_token");
}

function isAuthenticated() {
  return Boolean(getToken());
}

function requireAuth() {
  const protectedPages = ["dashboard.html", "chat.html", "watchlist.html"];
  const page = window.location.pathname.split("/").pop();
  if (protectedPages.includes(page) && !isAuthenticated()) {
    window.location.href = "login.html";
  }
}

function getApiBaseUrl() {
  return window.FinMatrixAPI?.API_BASE_URL || "http://localhost:8000";
}

async function registerUser(username, email, password) {
  const response = await fetch(`${getApiBaseUrl()}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, email, password })
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Registration failed");
  }
  const data = await response.json();
  setToken(data.access_token);
  return data;
}

async function loginUser(email, password) {
  const response = await fetch(`${getApiBaseUrl()}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Login failed");
  }
  const data = await response.json();
  setToken(data.access_token);
  return data;
}

async function getCurrentUser() {
  const token = getToken();
  if (!token) return null;
  const response = await fetch(`${getApiBaseUrl()}/api/auth/me`, {
    headers: { "Authorization": `Bearer ${token}` }
  });
  if (!response.ok) {
    clearToken();
    return null;
  }
  return await response.json();
}

function logout() {
  clearToken();
  window.location.href = "login.html";
}

window.FinMatrixAuth = {
  setToken,
  clearToken,
  getToken,
  isAuthenticated,
  requireAuth,
  registerUser,
  loginUser,
  getCurrentUser,
  logout
};
