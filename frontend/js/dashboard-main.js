import { initDashboard } from "./dashboard.js";
import { initNavigation } from "./navigation.js";

document.addEventListener("DOMContentLoaded", async () => {
  const ready = await initNavigation();
  if (!ready) return;
  await initDashboard();
});