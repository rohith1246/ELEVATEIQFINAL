/**
 * @file preloader.js
 * @description Controls the intro animated preloader video overlay.
 * Handles video playback, autoplay failure fallbacks, user skips, and cleans up the DOM/scroll locking.
 */

(function() {
  const preloader = document.getElementById("preloader");
  const video = document.getElementById("preloader-video");

  if (!preloader) return;

  if (sessionStorage.getItem("preloader_played") === "true") {
    preloader.remove();
    document.body.style.overflow = "";
    return;
  }

  function dismissPreloader() {
    if (preloader && preloader.parentNode) {
      preloader.style.transition = "opacity 0.4s ease, visibility 0.4s ease";
      preloader.style.opacity = "0";
      preloader.style.visibility = "hidden";
      preloader.style.pointerEvents = "none";
      document.body.style.overflow = "";
      sessionStorage.setItem("preloader_played", "true");
      setTimeout(() => {
        if (preloader.parentNode) preloader.remove();
      }, 400);
    }
  }

  // Safety fallback timer: auto-dismiss after 2 seconds max
  const maxTimer = setTimeout(dismissPreloader, 2000);

  if (video) {
    video.addEventListener("ended", () => {
      clearTimeout(maxTimer);
      dismissPreloader();
    });
    video.addEventListener("error", dismissPreloader);
    video.play().catch(dismissPreloader);
  }

  preloader.addEventListener("click", dismissPreloader);
  window.addEventListener("touchstart", dismissPreloader, { once: true });
  window.addEventListener("keydown", dismissPreloader, { once: true });
})();

