import { initNews, fetchNews } from "./news.js";
import { initNavigation } from "./navigation.js";

document.addEventListener("DOMContentLoaded", async () => {
  const ready = await initNavigation();
  if (!ready) return;
  await initNews();

  // Bind category tab handlers
  document.querySelectorAll(".tabs .tab").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const category = e.target.dataset.category;
      document.querySelectorAll(".tabs .tab").forEach((b) => b.classList.remove("active"));
      e.target.classList.add("active");

      try {
        const data = await fetchNews(category);
        const root = document.querySelector("#news-root");
        if (root) {
          const { renderNewsFeed } = await import("./news.js");
          renderNewsFeed(data, category);
        }
      } catch (err) {
        console.error("Error loading news:", err);
      }
    });
  });
});