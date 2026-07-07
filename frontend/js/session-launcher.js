/**
 * @file session-launcher.js
 * @description Provides a premium staggered sliding panel transition (slide-in / slide-out) for ElevateIQ.
 */

(function() {
  // Determine path of the logo (relative to the current page location)
  const isSubdir = window.location.pathname.includes('/edutech/');
  const logoSrc = isSubdir ? '../images/logo.png' : 'images/logo.png';

  // Helper to inject the transition overlay markup
  function createOverlayMarkup(initialActiveState = false, customText = 'Secure Session') {
    if (document.getElementById('page-transition-overlay')) return;

    const activeClass = initialActiveState ? 'active' : '';
    const overlayHtml = `
      <div id="page-transition-overlay" class="${activeClass}">
        <div class="transition-panel panel-1"></div>
        <div class="transition-panel panel-2"></div>
        <div class="transition-panel panel-3">
          <div class="transition-logo-wrap">
            <img src="${logoSrc}" alt="ElevateIQ Logo" class="transition-logo">
            <div class="transition-text" id="transition-status-text">${customText}</div>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('afterbegin', overlayHtml);
  }

  // Trigger page reveal (slide-out to left)
  function triggerSlideOut() {
    const overlay = document.getElementById('page-transition-overlay');
    if (!overlay) return;

    // Lock scrolling initially during transition slide out
    document.body.style.overflow = 'hidden';

    setTimeout(() => {
      overlay.classList.add('slide-out');
      
      // Unlock page scrolling
      document.body.style.overflow = '';
      
      // Remove completely from DOM after animation resolves (approx 900ms)
      setTimeout(() => {
        overlay.remove();
      }, 1000);
    }, 100);
  }

  // Initialize: Check if page load is an internal transition slide-out
  const initLauncher = () => {
    if (sessionStorage.getItem('page_transitioning') === 'true') {
      sessionStorage.removeItem('page_transitioning');
      
      // Get destination-specific tag to show during slide-out
      const savedText = sessionStorage.getItem('page_transition_text') || 'Secure Session';
      sessionStorage.removeItem('page_transition_text');

      createOverlayMarkup(true, savedText); // create active (fully covered) overlay
      triggerSlideOut();
    }

    // Intercept click events dynamically
    document.addEventListener('click', function(e) {
      const link = e.target.closest('a');
      if (!link) return;

      const href = link.getAttribute('href');
      
      // Do not intercept if:
      // - No href exists
      // - It is an internal section link (starts with #)
      // - It is a javascript action, tel link, or mailto link
      // - It opens in a new tab (_blank)
      // - It has custom click handlers like logout
      if (!href || 
          href.startsWith('#') || 
          href.startsWith('javascript:') || 
          href.startsWith('tel:') || 
          href.startsWith('mailto:') || 
          link.getAttribute('target') === '_blank' ||
          link.getAttribute('onclick')) {
        return;
      }

      // Customize text according to target
      let customText = 'Connecting Session';
      const lowerHref = href.toLowerCase();
      
      if (lowerHref.includes('login.html')) {
        customText = 'Authenticating Gate';
      } else if (lowerHref.includes('register.html')) {
        customText = 'Accessing Registry';
      } else if (lowerHref.includes('dashboard.html')) {
        customText = 'Launching Dashboard';
      } else if (lowerHref.includes('edutech/')) {
        customText = 'Launching EduTech Portal';
      } else if (lowerHref.includes('about.html')) {
        customText = 'Loading Corporate Profile';
      } else if (lowerHref.includes('contact.html')) {
        customText = 'Opening Communications';
      } else if (lowerHref.includes('openings.html')) {
        customText = 'Opening Careers Desk';
      } else {
        customText = 'Transitioning Page';
      }

      // Start transition slide-in
      e.preventDefault();
      
      // Inject overlay inactive (offscreen)
      createOverlayMarkup(false, customText);
      const overlay = document.getElementById('page-transition-overlay');
      
      // Trigger slide-in
      setTimeout(() => {
        document.body.style.overflow = 'hidden';
        overlay.classList.add('active');
        
        // Cache transition states to slide out seamlessly on load
        sessionStorage.setItem('page_transitioning', 'true');
        sessionStorage.setItem('page_transition_text', customText);
        
        // Navigate away after panels cover screen (800ms)
        setTimeout(() => {
          window.location.href = href;
        }, 800);
      }, 20);
    });
  };

  // Safe window entry points
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLauncher);
  } else {
    initLauncher();
  }
})();
