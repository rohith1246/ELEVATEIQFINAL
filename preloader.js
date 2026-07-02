(function() {
  const visited = sessionStorage.getItem("elevateiq_visited");
  const preloader = document.getElementById("preloader");
  const video = document.getElementById("preloader-video");

  if (visited) {
    if (preloader) {
      preloader.style.display = "none";
    }
  } else {
    // Lock scrolling on page load
    document.body.style.overflow = "hidden";
    
    sessionStorage.setItem("elevateiq_visited", "true");

    // Fade out after 4.2 seconds (logo resolves at ~3.5s)
    const fadeTimeout = setTimeout(fadeOutPreloader, 4200);

    if (video) {
      // Autoplay video
      video.play().catch(err => {
        console.log("Autoplay prevented:", err);
      });
      
      video.addEventListener("ended", fadeOutPreloader);
    }

    // Skip preloader on click
    if (preloader) {
      preloader.addEventListener("click", fadeOutPreloader);
    }
    
    function fadeOutPreloader() {
      clearTimeout(fadeTimeout);
      if (preloader && !preloader.classList.contains("fade-out")) {
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
