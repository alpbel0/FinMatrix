import { loginUser } from "./auth.js";

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("login-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const email = document.getElementById("email")?.value || "";
    const password = document.getElementById("password")?.value || "";
    const errorMsg = document.getElementById("error-message");

    try {
      await loginUser(email, password);
      window.location.href = "/dashboard.html";
    } catch (error) {
      if (errorMsg) {
        errorMsg.textContent = error.message;
        errorMsg.style.display = "block";
      }
    }
  });
});
