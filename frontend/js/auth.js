import { API_BASE_URL } from "./api.js";

export function setToken(token) {
  localStorage.setItem("finmatrix_token", token);
}

export function clearToken() {
  localStorage.removeItem("finmatrix_token");
}

export function getToken() {
  return localStorage.getItem("finmatrix_token");
}

export function isAuthenticated() {
  return Boolean(getToken());
}

export async function registerUser(username, email, password) {
  const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, email, password })
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Registration failed");
  }
  setToken(data.access_token);
  return data;
}

export async function loginUser(email, password) {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Login failed");
  }
  setToken(data.access_token);
  return data;
}

export async function getCurrentUser() {
  const token = getToken();
  if (!token) return null;
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: { "Authorization": `Bearer ${token}` }
  });
  if (!response.ok) {
    clearToken();
    return null;
  }
  return await response.json();
}

export function logout() {
  clearToken();
  window.location.href = "/login.html";
}
