import { renderWatchlist } from "./watchlist.js";
import { initNavigation } from "./navigation.js";

document.addEventListener("DOMContentLoaded", async () => {
  const ready = await initNavigation();
  if (!ready) return;
  renderWatchlist();
});
