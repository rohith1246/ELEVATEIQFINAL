(function() {
  const preloader = document.getElementById("preloader");
  const video = document.getElementById("preloader-video");
  const fallback = document.getElementById("preloader-fallback");

  if (preloader) {
    // Lock scrolling on page load
    document.body.style.overflow = "hidden";

    let fadeTimeout = null;
    let fallbackTimeout = null;

    // Ultimate fallback: If nothing loads or plays after 4.2 seconds, bypass preloader.
    fadeTimeout = setTimeout(fadeOutPreloader, 4200);

    if (video) {
      // Fast check: If video cannot play through within 800ms, skip preloader immediately.
      fallbackTimeout = setTimeout(() => {
        console.log("Video took too long to buffer. Bypassing preloader to avoid user lag.");
        fadeOutPreloader();
      }, 800);

      video.addEventListener("canplaythrough", () => {
        // Video is fully buffered and ready to play smoothly!
        clearTimeout(fallbackTimeout);
        
        // Fade out CSS spinner and fade in video intro
        if (fallback) fallback.style.opacity = "0";
        video.style.opacity = "1";
        
        video.play().catch(err => {
          console.log("Autoplay prevented:", err);
          fadeOutPreloader();
        });
      });

      video.addEventListener("ended", fadeOutPreloader);

      // Bypass immediately if a hard error occurs
      video.addEventListener("error", () => {
        console.log("Video loading error. Bypassing...");
        fadeOutPreloader();
      });
    } else {
      // No video element, exit preloader after brief logo pulse
      setTimeout(fadeOutPreloader, 1500);
    }

    // Skip preloader on click
    preloader.addEventListener("click", fadeOutPreloader);
    
    function fadeOutPreloader() {
      clearTimeout(fadeTimeout);
      clearTimeout(fallbackTimeout);
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
