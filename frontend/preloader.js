/**
 * @file preloader.js
 * @description Controls the intro animated preloader video overlay.
 * Handles video playback, autoplay failure fallbacks, user skips, and cleans up the DOM/scroll locking.
 */

(function() {
  const preloader = document.getElementById("preloader");
  const video = document.getElementById("preloader-video");

  if (preloader) {
    // Lock scrolling on page load to prevent user navigation during the intro
    document.body.style.overflow = "hidden";

    // Set a safety timeout to fade out after 4.2 seconds if events don't trigger (logo resolves at ~3.5s)
    const fadeTimeout = setTimeout(fadeOutPreloader, 4200);

    if (video) {
      // Autoplay the preloader MP4 animation
      video.play().catch(err => {
        console.log("Autoplay prevented:", err);
        fadeOutPreloader();
      });
      
      // Hook transition fade-out upon video end
      video.addEventListener("ended", fadeOutPreloader);

      // Bypass preloader immediately if a hard loading error occurs on the media element
      video.addEventListener("error", () => {
        console.log("Video loading error, skipping...");
        fadeOutPreloader();
      });
    }

    // Skip preloader on user click interaction
    preloader.addEventListener("click", fadeOutPreloader);
    
    /**
     * Fades out and terminates the preloader overlay, restoring main viewport scrolling.
     */
    function fadeOutPreloader() {
      clearTimeout(fadeTimeout);
      if (!preloader.classList.contains("fade-out")) {
        preloader.classList.add("fade-out");
        
        // Restore page scrolling
        document.body.style.overflow = "";
        
        // Clean up and completely purge the preloader element from the DOM after fade animation ends
        setTimeout(() => {
          preloader.remove();
        }, 800);
      }
    }
  }
})();

