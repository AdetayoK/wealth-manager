"use strict";
const form = document.querySelector("#login");
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = document.querySelector("#message");
  message.textContent = "";
  const btn = form.querySelector("button");
  btn.disabled = true;
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST", headers: {"Content-Type": "application/json"},
      credentials: "same-origin",
      body: JSON.stringify({ username: form.username.value, password: form.password.value }),
    });
    if (!response.ok) throw new Error("Invalid username or password");
    window.location.replace("/");
  } catch (error) {
    message.textContent = error.message;
  } finally {
    btn.disabled = false;
  }
});
