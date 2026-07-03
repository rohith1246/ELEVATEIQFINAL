(function() {
  const preloader = document.getElementById("preloader");
  const video = document.getElementById("preloader-video");

  if (preloader) {
    // Lock scrolling on page load
    document.body.style.overflow = "hidden";

    // Fade out after 4.2 seconds (logo resolves at ~3.5s)
    const fadeTimeout = setTimeout(fadeOutPreloader, 4200);

    if (video) {
      // Autoplay video
      video.play().catch(err => {
        console.log("Autoplay prevented:", err);
        fadeOutPreloader();
      });
      
      video.addEventListener("ended", fadeOutPreloader);

      // Bypass preloader immediately if a hard loading error occurs
      video.addEventListener("error", () => {
        console.log("Video loading error, skipping...");
        fadeOutPreloader();
      });
    }

    // Skip preloader on click
    preloader.addEventListener("click", fadeOutPreloader);
    
    function fadeOutPreloader() {
      clearTimeout(fadeTimeout);
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
