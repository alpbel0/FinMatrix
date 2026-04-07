import { registerUser } from "./auth.js";

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("register-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const username = document.getElementById("username")?.value || "";
    const email = document.getElementById("email")?.value || "";
    const password = document.getElementById("password")?.value || "";
    const errorMsg = document.getElementById("error-message");

    try {
      await registerUser(username, email, password);
      window.location.href = "/dashboard.html";
    } catch (error) {
      if (errorMsg) {
        errorMsg.textContent = error.message;
        errorMsg.style.display = "block";
      }
    }
  });
});
