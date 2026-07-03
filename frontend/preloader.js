(function() {
  const preloader = document.getElementById("preloader");
  const video = document.getElementById("preloader-video");

  if (preloader) {
    // Lock scrolling on page load
    document.body.style.overflow = "hidden";

    // Fade out after 4.2 seconds (logo resolves at ~3.5s)
    const fadeTimeout = setTimeout(fadeOutPreloader, 4200);
    let loadWatchdog = null;

    if (video) {
      // Autoplay video
      video.play().catch(err => {
        console.log("Autoplay prevented:", err);
        fadeOutPreloader();
      });

      // Watchdog timer: If video fails to start playing within 1.8 seconds, bypass preloader.
      loadWatchdog = setTimeout(() => {
        if (video.currentTime === 0) {
          console.log("Video loading too slow or stalled. Bypassing...");
          fadeOutPreloader();
        }
      }, 1800);
      
      video.addEventListener("ended", fadeOutPreloader);

      // Bypass preloader immediately if connection stalls, buffers or errors
      video.addEventListener("waiting", () => {
        console.log("Video buffering, skipping to site...");
        fadeOutPreloader();
      });
      video.addEventListener("stalled", () => {
        console.log("Video stalled, skipping to site...");
        fadeOutPreloader();
      });
      video.addEventListener("error", () => {
        console.log("Video error, skipping to site...");
        fadeOutPreloader();
      });
    }

    // Skip preloader on click
    preloader.addEventListener("click", fadeOutPreloader);
    
    function fadeOutPreloader() {
      clearTimeout(fadeTimeout);
      if (loadWatchdog) clearTimeout(loadWatchdog);
      if (!preloader.classList.contains("fade-out")) {
        preloader.classList.add("fade-out");
        
        // Restore page scrolling
        document.body.style.overflow = "";
        
        // Clean up from DOM after fade animation ends
        setTimeout(() => {
          preloader.remove();
        }, 800);
      }
    }
  }
})();
