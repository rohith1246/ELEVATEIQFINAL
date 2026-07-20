/**
 * @file preloader.js
 * @description Controls the intro animated preloader video overlay.
 * Handles video playback, autoplay failure fallbacks, user skips, and cleans up the DOM/scroll locking.
 */

(function() {
  const preloader = document.getElementById("preloader");
  const video = document.getElementById("preloader-video");

  if (preloader) {
    if (sessionStorage.getItem("preloader_played") === "true") {
      preloader.remove();
      document.body.style.overflow = "";
      return;
    }

    const fadeTimeout = setTimeout(fadeOutPreloader, 300);

    if (video) {
      video.play().catch(() => fadeOutPreloader());
      video.addEventListener("ended", fadeOutPreloader);
      video.addEventListener("error", fadeOutPreloader);
    }

    preloader.addEventListener("click", fadeOutPreloader);
    window.addEventListener("touchstart", fadeOutPreloader, { once: true });
    window.addEventListener("keydown", fadeOutPreloader, { once: true });
    
    function fadeOutPreloader() {
      clearTimeout(fadeTimeout);
      if (!preloader.classList.contains("fade-out")) {
        preloader.classList.add("fade-out");
        sessionStorage.setItem("preloader_played", "true");
        document.body.style.overflow = "";
        setTimeout(() => { preloader.remove(); }, 200);
      }
    }
  }
})();

