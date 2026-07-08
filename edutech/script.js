/**
 * @file script.js
 * @description Interactive behaviors for the EduTech Sub-Portal.
 * Implements smooth scroll wrappers, GSAP reveal animations, particle canvas renderers,
 * dynamic search course grids, testimonial carousels, and a rule-based AI guide widget.
 */

(function(){
  "use strict";

  function escapeHTML(str) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  const hasGSAP = typeof gsap !== "undefined";
  if (hasGSAP && typeof ScrollTrigger !== "undefined") gsap.registerPlugin(ScrollTrigger);
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ============================================================
     1. PRELOADER TRANSITIONS
     ============================================================ */
  let preloaderRemoved = false;
  function hidePreloader() {
    if (preloaderRemoved) return;
    preloaderRemoved = true;
    
    const bar = document.getElementById("preload-bar");
    const pre = document.getElementById("preloader");
    if (bar) bar.style.transition = "width .6s ease";
    requestAnimationFrame(() => { if (bar) bar.style.width = "100%"; });
    
    setTimeout(() => {
      if (pre){
        pre.style.transition = "opacity .5s ease, visibility .5s";
        pre.style.opacity = "0";
        setTimeout(() => pre.remove(), 550);
      }
      document.body.classList.add("loaded");
      playEntranceAnimations();
    }, 650);
  }

  window.addEventListener("load", () => {
    setTimeout(hidePreloader, 100);
  });

  /* ============================================================
     2. LENIS SMOOTH SCROLL INTEGRATION
     ============================================================ */
  let lenis;
  try{
    if (typeof Lenis !== "undefined" && !reduceMotion){
      lenis = new Lenis({ duration: 1.1, smoothWheel: true });
      function raf(time){ lenis.raf(time); requestAnimationFrame(raf); }
      requestAnimationFrame(raf);
      if (hasGSAP && typeof ScrollTrigger !== "undefined"){
        lenis.on("scroll", ScrollTrigger.update);
        gsap.ticker.add((time)=> lenis.raf(time*1000));
        gsap.ticker.lagSmoothing(0);
      }
    }
  }catch(e){ /* smooth scroll optional */ }

  /* ============================================================
     3. MAGNETIC HOVER BUTTONS
     ============================================================ */
  document.querySelectorAll(".magnetic").forEach(btn=>{
    btn.addEventListener("mousemove", e=>{
      const r = btn.getBoundingClientRect();
      const x = e.clientX - r.left - r.width/2;
      const y = e.clientY - r.top - r.height/2;
      btn.style.transform = `translate(${x*0.25}px, ${y*0.35}px)`;
    });
    btn.addEventListener("mouseleave", ()=>{ btn.style.transform = "translate(0,0)"; });
  });

  /* ============================================================
     4. NAVBAR SCROLL AND TOGGLE LISTENERS
     ============================================================ */
  const navbar = document.getElementById("navbar");
  const navToggle = document.getElementById("navToggle");
  const navLinks = document.getElementById("navLinks");
  window.addEventListener("scroll", ()=>{
    navbar.classList.toggle("scrolled", window.scrollY > 40);
    document.getElementById("to-top").classList.toggle("show", window.scrollY > 700);
  });
  navToggle.addEventListener("click", ()=>{
    navLinks.classList.toggle("open");
    navToggle.classList.toggle("active");
  });
  document.querySelectorAll(".nav-link").forEach(l=> l.addEventListener("click", ()=> navLinks.classList.remove("open")));

  document.getElementById("to-top").addEventListener("click", ()=>{
    if (lenis) lenis.scrollTo(0); else window.scrollTo({top:0, behavior:"smooth"});
  });

  /* ============================================================
     5. HERO CANVAS CONNECTING PARTICLES
     ============================================================ */
  function initHeroLoad(){
    const canvas = document.getElementById("hero-canvas");
    if (!canvas || reduceMotion) return;
    const ctx = canvas.getContext("2d");
    let w,h,particles=[];
    
    /** Resizes particles canvas bounding sizes */
    function resize(){
      w = canvas.width = canvas.offsetWidth * devicePixelRatio;
      h = canvas.height = canvas.offsetHeight * devicePixelRatio;
    }
    resize();
    window.addEventListener("resize", resize);
    const COUNT = Math.min(70, Math.floor((canvas.offsetWidth*canvas.offsetHeight)/16000));
    const colors = ["37,99,235","124,58,237","6,182,212"];
    for(let i=0;i<COUNT;i++){
      particles.push({
        x:Math.random()*w, y:Math.random()*h,
        r:Math.random()*1.8+0.6,
        vx:(Math.random()-0.5)*0.25*devicePixelRatio,
        vy:(Math.random()-0.5)*0.25*devicePixelRatio,
        c:colors[i%3]
      });
    }

    /** Animation tick generator loop */
    function tick(){
      ctx.clearRect(0,0,w,h);
      particles.forEach((p,i)=>{
        p.x+=p.vx; p.y+=p.vy;
        if(p.x<0||p.x>w) p.vx*=-1;
        if(p.y<0||p.y>h) p.vy*=-1;
        ctx.beginPath();
        ctx.fillStyle = `rgba(${p.c},0.7)`;
        ctx.arc(p.x,p.y,p.r*devicePixelRatio,0,Math.PI*2);
        ctx.fill();
        for(let j=i+1;j<particles.length;j++){
          const q = particles[j];
          const dx=p.x-q.x, dy=p.y-q.y, dist=Math.sqrt(dx*dx+dy*dy);
          if(dist < 130*devicePixelRatio){
            ctx.strokeStyle = `rgba(${p.c},${0.12*(1-dist/(130*devicePixelRatio))})`;
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(p.x,p.y); ctx.lineTo(q.x,q.y); ctx.stroke();
          }
        }
      });
      requestAnimationFrame(tick);
    }
    tick();
  }

  /* ============================================================
     6. HERO ANIMATION TIMELINES (GSAP)
     ============================================================ */
  function playEntranceAnimations(){
    if (hasGSAP){
      gsap.to(".hero-line span", { yPercent:0, y:0, duration:1, ease:"power4.out", stagger:0.12, delay:0.15 });
      gsap.to(".hero-badge", { opacity:1, y:0, duration:0.8, delay:0.05 });
      gsap.to(".hero-ctas .btn", { opacity:1, y:0, duration:0.8, stagger:0.1, delay:0.6 });
      gsap.to(".hero-stats", { opacity:1, y:0, duration:0.8, delay:0.85 });
    } else {
      document.querySelectorAll(".hero-line span").forEach(el => el.style.transform = "none");
      document.querySelectorAll(".hero-badge, .hero-ctas .btn, .hero-stats").forEach(el => {
        el.style.opacity = "1";
        el.style.transform = "none";
      });
    }
  }
  if (hasGSAP){
    document.querySelectorAll("[data-float]").forEach((el,i)=>{
      gsap.to(el, { y: i%2===0 ? -22 : 22, duration: 3+i*0.4, ease:"sine.inOut", yoyo:true, repeat:-1 });
    });
  }

  /* ============================================================
     7. SCROLL TRIGGER REVEAL ENGINES
     ============================================================ */
  /**
   * Initializes ScrollTrigger reveal bindings for marked DOM nodes.
   */
  function setupReveal(){
    const items = document.querySelectorAll(".reveal");
    if (hasGSAP && typeof ScrollTrigger !== "undefined"){
      items.forEach(el=>{
        gsap.to(el, {
          opacity:1, y:0, duration:0.9, ease:"power3.out",
          scrollTrigger:{ trigger: el, start:"top 88%" }
        });
      });
      ScrollTrigger.refresh();
    } else {
      items.forEach(el=>{ el.style.opacity=1; el.style.transform="none"; });
    }
    
    // Safety fallback: force reveal all elements after 1.2s to guarantee visibility
    setTimeout(() => {
      items.forEach(el => {
        el.style.opacity = "1";
        el.style.transform = "none";
      });
      if (hasGSAP && typeof ScrollTrigger !== "undefined") {
        ScrollTrigger.refresh();
      }
    }, 1200);
  }



  /* ============================================================
     9. COURSES LIST RENDERER & FILTERS
     ============================================================ */
  
  /**
   * Formats Indian Rupee currency labels.
   * 
   * @param {number} n - Raw value.
   * @returns {string} Formatted label.
   */
  function getCourseImagePath(icon, title = "") {
    const titleLower = (title || "").toLowerCase();
    
    if (titleLower.includes("aws") || icon === "server") {
      return "/images/course%20images/aws.jpeg";
    }
    if (titleLower.includes("app") || titleLower.includes("mobile")) {
      return "/images/course%20images/app.jpeg";
    }
    if (titleLower.includes("python")) {
      return "/images/course%20images/python%20course.jpg";
    }
    if (titleLower.includes("java")) {
      return "/images/course%20images/java%20couse.webp";
    }
    if (titleLower.includes("data science") || titleLower.includes("ai") || icon === "brain" || icon === "chart") {
      return "/images/course%20images/Data-science.jpg";
    }
    if (titleLower.includes("cyber") || titleLower.includes("security") || icon === "shield") {
      return "/images/course%20images/cybersecurity.jpg";
    }
    if (titleLower.includes("full stack") || titleLower.includes("web") || titleLower.includes("devops") || titleLower.includes("cloud")) {
      return "/images/course%20images/fullstack%20development.jpg";
    }
    
    const map = {
      layers: '/images/course%20images/app.jpeg',
      code:   '/images/course%20images/fullstack%20development.jpg',
      coffee: '/images/course%20images/java%20couse.webp',
      brain:  '/images/course%20images/Data-science.jpg',
      chart:  '/images/course%20images/Data-science.jpg',
      cloud:  '/images/course%20images/fullstack%20development.jpg',
      server: '/images/course%20images/aws.jpeg',
      shield: '/images/course%20images/cybersecurity.jpg',
      palette:'/images/course_ui_ux.webp'
    };
    return map[icon] || '/images/course%20images/fullstack%20development.jpg';
  }

  /**
   * Formats Indian Rupee currency labels.
   * 
   * @param {number} n - Raw value.
   * @returns {string} Formatted label.
   */
  function money(n){ return "₹" + n.toLocaleString("en-IN"); }
  
  /**
   * Generates course catalog card row elements.
   * 
   * @param {Array<Object>} list - The courses data items array.
   */
  function renderCourses(list, isInitial = false){
    const grid = document.getElementById("coursesGrid");
    if (!list.length){ grid.innerHTML = `<p style="color:var(--muted); grid-column:1/-1; text-align:center; padding:40px 0;">No programs match that search.</p>`; return; }
    
    const revealClass = isInitial ? "reveal" : "";
    const revealStyle = isInitial ? "" : 'style="opacity:1; transform:none;"';

    grid.innerHTML = list.map(c => {
      const priceVal = c.price;
      const oldPriceVal = c.oldPrice || c.old_price;
      return `
      <div class="glass-card course-card alive-card ${revealClass}" ${revealStyle}>
        <div class="course-thumb" style="overflow:hidden; display:flex; align-items:center; justify-content:center; position:relative;">
          <img src="${getCourseImagePath(c.icon, c.title)}" alt="${c.title}" style="width:100%; height:100%; object-fit:cover; position:absolute; inset:0; opacity:0.8;">
          <div style="position:absolute; inset:0; background:linear-gradient(to bottom, transparent, rgba(2,6,23,0.5)); pointer-events:none;"></div>
          <span class="course-level" style="z-index:2;">${c.level}</span>
        </div>
        <div class="course-body">
          <h3>${c.title}</h3>
          <div class="course-meta">
            <span>${svgIcon('<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>')}${c.duration}</span>
            <span class="rating">${svgIcon('<polygon points="12 2 15 8.5 22 9.5 17 14.5 18.5 21.5 12 18 5.5 21.5 7 14.5 2 9.5 9 8.5 12 2"/>')}${c.rating}</span>
          </div>
          <div style="margin: 10px 0 16px 0; display: flex; align-items: baseline; gap: 8px;">
            <span style="font-size: 18px; font-weight: 700; color: white;">${money(priceVal)}</span>
            ${oldPriceVal ? `<span style="font-size: 13px; text-decoration: line-through; color: var(--muted);">${money(oldPriceVal)}</span>` : ''}
          </div>
          <div class="course-foot">
            <button class="btn btn-primary btn-sm magnetic enroll-btn" data-id="${c.id}">Enroll</button>
          </div>
        </div>
      </div>`;
    }).join("");

    grid.querySelectorAll(".enroll-btn").forEach(b=> b.addEventListener("click", ()=>{
      const courseId = b.getAttribute("data-id");
      window.openCourseDetail(courseId);
    }));

    if (hasGSAP && typeof ScrollTrigger !== "undefined") {
      ScrollTrigger.refresh();
    }
  }

  /**
   * Binds listeners to course search inputs and filter pills.
   */
  async function setupCourses(){
    let activeCourses = [];

    // Dynamically update Login/Dashboard navbar link based on session state
    const navLogin = document.getElementById("navLoginLink");
    if (navLogin && localStorage.getItem("edutech_token")) {
      navLogin.textContent = "Dashboard";
      navLogin.href = "dashboard.html";
    }

    try {
      const res = await fetch("/api/edutech/courses");
      if (res.ok) {
        activeCourses = await res.json();
      } else {
        throw new Error("API failed");
      }
    } catch(err) {
      console.warn("Could not load backend courses. Falling back to static data.");
      activeCourses = COURSES;
    }

    window.activeCoursesList = activeCourses;
    renderCourses(activeCourses, true);

    const search = document.getElementById("courseSearch");
    const pills = document.querySelectorAll(".pill");
    let activeFilter = "all";
    
    function apply(){
      const q = search.value.trim().toLowerCase();
      const filtered = activeCourses.filter(c=>{
        const matchesFilter = activeFilter==="all" || c.level===activeFilter;
        const matchesSearch = !q || 
                              c.title.toLowerCase().includes(q) || 
                              (c.description || "").toLowerCase().includes(q) || 
                              (c.category || "").toLowerCase().includes(q);
        return matchesFilter && matchesSearch;
      });
      renderCourses(filtered, false);
    }
    search.addEventListener("input", apply);
    pills.forEach(p=> p.addEventListener("click", ()=>{
      pills.forEach(x=>x.classList.remove("active"));
      p.classList.add("active");
      activeFilter = p.dataset.filter;
      apply();
    }));

    window.highlightCourseCard = function(event) {
      event.preventDefault();
      const title = document.getElementById('recTitle').textContent;
      
      const coursesSection = document.getElementById('courses');
      if (coursesSection) {
        coursesSection.scrollIntoView({ behavior: 'smooth' });
      }

      // Reset filter pills to All
      pills.forEach(x => x.classList.remove("active"));
      const allPill = Array.from(pills).find(p => p.dataset.filter === "all");
      if (allPill) allPill.classList.add("active");
      activeFilter = "all";

      const searchInput = document.getElementById('courseSearch');
      if (searchInput) {
        searchInput.value = title;
        apply();
      }

      // Dynamic glow highlight
      setTimeout(() => {
        const cards = document.querySelectorAll('.course-card');
        cards.forEach(card => {
          const h3 = card.querySelector('h3');
          if (h3 && (h3.textContent.toLowerCase().includes(title.toLowerCase()) || title.toLowerCase().includes(h3.textContent.toLowerCase()))) {
            card.classList.add('highlight-pulse');
            setTimeout(() => {
              card.classList.remove('highlight-pulse');
            }, 6000);
          }
        });
      }, 500);
    };
  }


  /* ============================================================
     10. ROADMAP ACTIVE PROGRESS RAILS
     ============================================================ */
  /**
   * Tracks roadmap list nodes scroll events to trigger active paths lines.
   */
  function setupRoadmap(){
    const nodes = document.querySelectorAll("[data-node]");
    const fill = document.getElementById("railFill");
    if (hasGSAP && typeof ScrollTrigger !== "undefined"){
      gsap.to(fill, {
        height:"100%", ease:"none",
        scrollTrigger:{ trigger:".roadmap-rail", start:"top 60%", end:"bottom 70%", scrub:0.6 }
      });
      nodes.forEach(node=>{
        ScrollTrigger.create({
          trigger: node, start:"top 65%",
          onEnter: ()=> node.classList.add("active"),
          onLeaveBack: ()=> node.classList.remove("active"),
        });
      });
      gsap.utils.toArray(".rail-content").forEach(el=>{
        gsap.from(el, { opacity:0, x:24, duration:0.7, scrollTrigger:{ trigger: el, start:"top 82%" } });
      });
    } else {
      nodes.forEach(n=> n.classList.add("active"));
      fill.style.height = "100%";
    }
  }


  /* ============================================================
     11. MENTOR PROFILES & FAQ ACCORDIONS
     ============================================================ */
  /**
   * Renders the leadership/mentor grid flip cards.
   */
  function renderTeam(){
    const grid = document.getElementById("teamGrid");
    if (!grid) return;
    grid.innerHTML = TEAM.map(t => `
      <div class="flip-card reveal">
        <div class="flip-inner">
          <div class="flip-front">
            <img src="${t.img}" alt="" aria-hidden="true" loading="lazy">
            <div class="info"><h4>${t.name}</h4><span>${t.role}</span></div>
          </div>
          <div class="flip-back">
            <p>${t.bio}</p>
            <div class="socials">
              <a href="#" aria-label="LinkedIn">${svgIcon('<rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/><path d="M10 9v12M10 13a4 4 0 0 1 8 0v8"/>')}</a>
              <a href="#" aria-label="Email">${svgIcon('<path d="M4 4h16v16H4z"/><path d="m22 6-10 7L2 6"/>')}</a>
            </div>
          </div>
        </div>
      </div>`).join("");
  }

  /**
   * Renders and binds accordion animations to FAQ cards.
   */
  function renderFAQ(){
    const list = document.getElementById("faqList");
    list.innerHTML = FAQS.map((f,i) => `
      <div class="glass-card faq-item reveal" data-i="${i}">
        <div class="faq-q"><h4>${f.q}</h4><span class="plus"></span></div>
        <div class="faq-a"><p>${f.a}</p></div>
      </div>`).join("");

    list.querySelectorAll(".faq-item").forEach(item=>{
      const a = item.querySelector(".faq-a");
      item.querySelector(".faq-q").addEventListener("click", ()=>{
        const isOpen = item.classList.contains("open");
        list.querySelectorAll(".faq-item.open").forEach(o=>{
          o.classList.remove("open"); o.querySelector(".faq-a").style.maxHeight = null;
        });
        if (!isOpen){
          item.classList.add("open");
          a.style.maxHeight = a.scrollHeight + "px";
        }
      });
    });
  }


  /* ============================================================
     12. TESTIMONIALS SLIDER CAROUSEL
     ============================================================ */
  /**
   * Sets up horizontal translation calculations for testimonials track.
   */
  function setupTestimonials(){
    const track = document.getElementById("testTrack");
    const cards = track.children;
    let index = 0;
    
    /** Returns single card outer bounding sizes */
    function cardWidth(){ return cards[0].getBoundingClientRect().width + 24; }
    
    /** Translates track container by increment step */
    function go(dir){
      const visible = Math.max(1, Math.floor(track.parentElement.offsetWidth / cardWidth()));
      index = Math.max(0, Math.min(cards.length - visible, index + dir));
      track.style.transform = `translateX(-${index * cardWidth()}px)`;
    }
    document.getElementById("testPrev").addEventListener("click", ()=> go(-1));
    document.getElementById("testNext").addEventListener("click", ()=> go(1));
  }


  /* ============================================================
     13. CONTACT FORM VALIDATIONS AND FETCH API
     ============================================================ */
  /**
   * Binds submission handlers and validation checks to input forms.
   */
  function setupForm(){
    const form = document.getElementById("contactForm");
    const success = document.getElementById("formSuccess");
    const validators = {
      name: v => v.trim().length >= 2 || "Enter your full name",
      email: v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) || "Enter a valid email address",
      phone: v => /^[0-9+\-\s()]{7,16}$/.test(v) || "Enter a valid phone number",
      track: v => v !== "" || "Select a track you're interested in",
      message: v => v.trim().length >= 10 || "Tell us a little more (10+ characters)",
    };
    
    // Submits main advisory inquiry contact details
    form.addEventListener("submit", e=>{
      e.preventDefault();
      let valid = true;
      const data = {};
      Object.keys(validators).forEach(name=>{
        const input = form.elements[name];
        data[name] = input.value;
        const wrap = document.getElementById("f-"+name);
        const result = validators[name](input.value);
        if (result !== true){
          valid = false;
          wrap.classList.add("invalid");
          wrap.querySelector(".err").textContent = result;
        } else {
          wrap.classList.remove("invalid");
          wrap.querySelector(".err").textContent = "";
        }
      });
      if (valid){
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalBtnHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = 'Sending...';
        
        fetch('/api/contact', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(data)
        })
        .then(response => response.json().then(json => ({ status: response.status, json })))
        .then(({ status, json }) => {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHtml;
          
          if (status === 201) {
            success.className = "form-success show";
            success.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m5 12 5 5L20 7"/></svg> ' + (json.message || "Thanks — an advisor will reach out within one business day.");
            form.reset();
            setTimeout(()=> success.classList.remove("show"), 6000);
          } else {
            success.className = "form-success show error";
            success.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg> ' + (json.error || "Submission failed. Please try again.");
          }
        })
        .catch(err => {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnHtml;
          success.className = "form-success show error";
          success.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg> Connection error. Please check backend is running.';
          console.error("Submission error:", err);
        });
      }
    });

    // Submits email address to newsletter registry endpoint
    const newsletter = document.getElementById("newsletterForm");
    if (newsletter) {
      newsletter.addEventListener("submit", e=>{
        e.preventDefault();
        const input = newsletter.querySelector("input");
        const btn = newsletter.querySelector("button");
        const original = btn.innerHTML;
        const email = input.value.trim();
        
        if (!email) return;
        btn.disabled = true;
        btn.innerHTML = "Subscribing...";
        
        fetch('/api/newsletter', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ email })
        })
        .then(response => response.json().then(json => ({ status: response.status, json })))
        .then(({ status, json }) => {
          btn.disabled = false;
          if (status === 200 || status === 201) {
            btn.innerHTML = "Subscribed ✓";
            input.value = "";
            setTimeout(()=> btn.innerHTML = original, 2400);
          } else {
            btn.innerHTML = "Failed ✗";
            setTimeout(()=> btn.innerHTML = original, 2400);
            console.error("Newsletter error:", json.error);
          }
        })
        .catch(err => {
          btn.disabled = false;
          btn.innerHTML = "Error ✗";
          setTimeout(()=> btn.innerHTML = original, 2400);
          console.error("Newsletter error:", err);
        });
      });
    }
  }


  /* ============================================================
     14. CHAT AI ADVISOR FLOATING PANEL
     ============================================================ */
  /**
   * Initializes state and listeners for advisor rule-based reply filters.
   */
  function setupAI(){
    const toggle = document.getElementById("ai-toggle");
    const panel = document.getElementById("ai-panel");
    const body = document.getElementById("aiBody");
    const input = document.getElementById("aiInput");
    const send = document.getElementById("aiSend");

    toggle.addEventListener("click", ()=> panel.classList.toggle("open"));

    const API_BASE = window.location.origin.startsWith('file:') ? "http://localhost:5000" : window.location.origin;

    let chatbotHistory = [
      {role: "assistant", content: "Hi! I'm Ascend, your AI guide. Ask me anything about our technical cohorts or career placement support!"}
    ];

    const responses = [
      { k:["beginner","start","new","zero"], r:"If you're starting from zero, Full Stack Web Development or Python for Backend Engineers are the best entry points — both assume no prior coding experience." },
      { k:["long","duration","weeks","time"], r:"Most programs run 12–22 weeks depending on the track. AI & Machine Learning is our longest at 22 weeks; UI/UX Design is our shortest at 12." },
      { k:["placement","job","hire","career"], r:"Yes — every program includes placement support: mock interviews, resume audits, and direct introductions across our 210+ hiring partners." },
      { k:["price","cost","fee","fees"], r:"Program fees range roughly ₹28,000–₹65,000 depending on the track and length. Scroll to the Courses section to compare exact pricing." },
      { k:["ai","machine learning","ml"], r:"Our AI & Machine Learning Bootcamp runs 22 weeks, from regression through transformer models, ending with a deployed capstone project." },
      { k:["contact","talk","human","advisor","call"], r:"Happy to connect you with a human advisor — scroll down to the Contact section and send a message, or use the WhatsApp option." },
    ];

    /** Filters text triggers to return matching rule response */
    function reply(text){
      const lower = text.toLowerCase();
      const hit = responses.find(r => r.k.some(k => lower.includes(k)));
      return hit ? hit.r : "Good question — an advisor can give you a precise answer on that. Want me to route you to the contact form?";
    }

    /** Appends message bubble wrapper element */
    function addMsg(text, who){
      const el = document.createElement("div");
      el.className = "ai-msg " + who;
      el.textContent = text;
      body.appendChild(el);
      body.scrollTop = body.scrollHeight;
      return el;
    }

    /** Handles parsing dispatch commands */
    async function handleSend(text){
      if (!text.trim()) return;
      addMsg(text, "user");
      chatbotHistory.push({role: "user", content: text});
      input.value = "";

      // Add temporary thinking indicator
      const thinkingBubble = addMsg("Thinking...", "bot");
      thinkingBubble.style.opacity = "0.7";

      try {
        const res = await fetch(`${API_BASE}/api/edutech/advisor/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: chatbotHistory })
        });
        
        thinkingBubble.remove();
        if (!res.ok) throw new Error("HTTP error");
        const data = await res.json();
        const replyText = data.reply || reply(text);
        
        chatbotHistory.push({role: "assistant", content: replyText});
        addMsg(replyText, "bot");
      } catch(err) {
        thinkingBubble.remove();
        // Fallback to local rule match if server offline or api error
        const fallbackTxt = reply(text);
        chatbotHistory.push({role: "assistant", content: fallbackTxt});
        addMsg(fallbackTxt, "bot");
      }
    }

    send.addEventListener("click", ()=> handleSend(input.value));
    input.addEventListener("keydown", e=>{ if(e.key==="Enter") handleSend(input.value); });
    document.querySelectorAll(".ai-quick button").forEach(b=>{
      b.addEventListener("click", ()=> handleSend(b.dataset.q));
    });
  }


  /* ============================================================
     14B. PATH FINDER QUIZ DECISION LOGIC
     ============================================================ */
  let quizAnswers = { step1: "", step2: "" };

  window.selectStep1 = function(val, btn) {
    quizAnswers.step1 = val;
    const container = btn.parentElement;
    container.querySelectorAll('.quiz-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    
    setTimeout(() => {
      document.getElementById('quizStep1').style.display = 'none';
      document.getElementById('quizStep2').style.display = 'block';
    }, 350);
  };

  window.selectStep2 = function(val, btn) {
    quizAnswers.step2 = val;
    const container = btn.parentElement;
    container.querySelectorAll('.quiz-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    
    setTimeout(() => {
      const recommendation = calculateQuizRecommendation();
      document.getElementById('recTitle').textContent = recommendation.title;
      document.getElementById('recDesc').textContent = recommendation.desc;
      
      document.getElementById('quizStep2').style.display = 'none';
      document.getElementById('quizResult').style.display = 'block';
    }, 350);
  };

  window.backToStep1 = function() {
    document.getElementById('quizStep2').style.display = 'none';
    document.getElementById('quizStep1').style.display = 'block';
  };

  window.resetQuiz = function() {
    quizAnswers = { step1: "", step2: "" };
    document.querySelectorAll('.quiz-btn').forEach(b => b.classList.remove('selected'));
    document.getElementById('quizResult').style.display = 'none';
    document.getElementById('quizStep2').style.display = 'none';
    document.getElementById('quizStep1').style.display = 'block';
  };



  function calculateQuizRecommendation() {
    const s1 = quizAnswers.step1;
    const s2 = quizAnswers.step2;
    
    if (s2 === 'visual') {
      if (s1 === 'beginner' || s1 === 'basic') {
        return {
          title: "Full Stack Web Development",
          desc: "Master frontend UI engineering (React) and backend services (Node.js/SQL) alongside direct hiring pipelines. Perfect for starting from scratch."
        };
      } else {
        return {
          title: "UI/UX Design Professional",
          desc: "Deep-dive into visual systems, wireframing, and user research. Learn to design premium user interfaces using Figma."
        };
      }
    } else if (s2 === 'analytical') {
      if (s1 === 'beginner') {
        return {
          title: "Data Science Professional",
          desc: "Learn statistical programming, Python data structures, SQL databases, and visualization frameworks to build corporate dashboards."
        };
      } else {
        return {
          title: "AI & Machine Learning Bootcamp",
          desc: "Learn probability, regression, deep neural networks, and transformer models. Specialized path for programmers seeking AI certification."
        };
      }
    } else {
      if (s1 === 'experienced') {
        return {
          title: "Cloud & DevOps Engineering",
          desc: "Master container orchestration (Docker/Kubernetes), secure networking, infrastructure-as-code, and AWS/Azure deployment frameworks."
        };
      } else {
        return {
          title: "Cyber Security Fundamentals",
          desc: "Master operating system security, risk auditing, compliance frameworks, penetration testing, and ethical hacking fundamentals."
        };
      }
    }
  }


  /* ============================================================
     15. INITIALIZATION CONTROLLER
     ============================================================ */
  async function initPortal() {
    document.getElementById("year").textContent = new Date().getFullYear();
    
    // 3s fallback safety timeout to prevent getting stuck
    const timeoutPromise = new Promise(resolve => setTimeout(resolve, 3000));
    const coursesPromise = setupCourses();
    
    // Race database courses fetch against the 3s timeout
    await Promise.race([coursesPromise, timeoutPromise]);
    
    // Remove preloader
    hidePreloader();
    
    renderTeam();
    renderFAQ();
    setupTestimonials();
    setupForm();
    setupAI();
    setupRoadmap();
    setupReveal();
  }
  initPortal();


  /* ============================================================
     15. COURSE DETAIL MODAL & ONLINE/OFFLINE SELECTIONS
     ============================================================ */

  const COURSE_DETAILS = {
    'full stack web development': {
      desc: 'Master the complete web stack from frontend UI to backend databases. Learn React, Node.js, Express, PostgreSQL, and deploy live production systems.',
      syllabus: [
        'Frontend Programming: HTML5, CSS3 Grid, Flexbox, Javascript ES6+',
        'React UI Applications: Hooks, Context, State Management, Responsive Layouts',
        'Backend Web Services: Node.js, Express, REST APIs, JSON Web Tokens',
        'Database Architecture: PostgreSQL schema design, indexing, and connection pools',
        'Cloud Deployment: AWS EC2 hosting, CI/CD pipelines, Docker containers'
      ]
    },
    'python for backend engineers': {
      desc: 'Deep dive into server-side engineering with Python. Write clean, scalable scripts, connect to SQL databases, and build enterprise REST APIs.',
      syllabus: [
        'Python Basics & OOP: Classes, objects, decorators, generators',
        'Web APIs: Django REST Framework and FastAPI architectures',
        'Data Integration: SQL databases, queries, and ORM setups',
        'Background Task Runners: Celery queues and Redis caches',
        'Testing: Pytest framework, mock assertions, unit test structures'
      ]
    },
    'java enterprise full stack': {
      desc: 'Build secure, scalable microservices with Java and Spring Boot. Learn to architecture high-volume backend APIs for global corporations.',
      syllabus: [
        'Java Core: Collections, Multi-threading, Streams API, design patterns',
        'Spring Framework: Spring Boot, Dependency Injection, Spring MVC',
        'Spring Data & Security: JPA, Hibernate ORM, OAuth2 protection',
        'Microservices: Spring Cloud Eureka, API Gateway, communication patterns',
        'Enterprise Tools: Maven, Gradle builds, JUnit unit testing'
      ]
    },
    'ai & machine learning bootcamp': {
      desc: 'Train predictive algorithms, neural networks, and computer vision models. Master the core mathematics and frameworks behind modern AI systems.',
      syllabus: [
        'Mathematics for AI: Linear Algebra, Calculus, Statistics, Probability',
        'Data Analysis: NumPy, Pandas, Matplotlib visualizations',
        'Machine Learning: Regression, Clustering, Decision Trees, Scikit-learn',
        'Deep Learning: Neural Networks, TensorFlow, PyTorch models',
        'Generative AI: LLM fine-tuning, prompt engineering pipelines'
      ]
    },
    'data science professional': {
      desc: 'Convert raw information into strategic company insights. Master statistical computing, data scraping, and analytics pipelines.',
      syllabus: [
        'Statistical Analysis: Distributions, hypothesis testing, regression models',
        'Data Wrangling: SQL databases, Pandas pipelines, ETL workflows',
        'Data Visualization: Tableau dashboards, Seaborn statistical plots',
        'Predictive Modeling: Forecasting models, time-series projections',
        'Big Data Tools: Apache Spark engine, Hadoop file systems'
      ]
    },
    'cloud & devops engineering': {
      desc: 'Deploy, scale, and secure high-availability cloud setups. Automate pipeline testing, builds, and infrastructure deployments.',
      syllabus: [
        'Linux Administration: Command-line utilities, bash scripting, permission rules',
        'Infrastructure as Code (IaC): Terraform schema design, AWS cloud setup',
        'Containerization: Docker container packaging, Kubernetes clusters',
        'CI/CD Pipelines: GitHub Actions automation, Jenkins workflows',
        'Monitoring: Prometheus logs, Grafana visualization dashboards'
      ]
    },
    'aws solutions architect prep': {
      desc: 'Comprehensive training for the AWS Solutions Architect Associate exam. Architect secure, resilient, and cost-effective cloud services.',
      syllabus: [
        'AWS Infrastructure: VPC setups, subnets, routing tables, security groups',
        'Compute & Storage: EC2 instances, S3 buckets, EBS storage systems',
        'Databases: RDS setups, DynamoDB nosql configurations',
        'High Availability: Auto-scaling, Elastic Load Balancer (ELB)',
        'Security: IAM policies, KMS encryption keys, CloudTrail audits'
      ]
    },
    'cyber security fundamentals': {
      desc: 'Inspect network protocols, identify vulnerability vectors, and build defensive shielding blocks against modern cyber threats.',
      syllabus: [
        'Networking Core: TCP/IP configurations, subnet routing, DNS security',
        'Ethical Hacking: Port scanning, Wireshark packet capture analysis',
        'Defensive Architectures: Firewalls, IDS/IPS tools, VPN shielding',
        'App Security: OWASP Top 10 web vulnerabilities, SQL injections',
        'Compliance: ISO 27001 models, GDPR rules, security audit checklists'
      ]
    },
    'ui/ux design professional': {
      desc: 'Design beautiful, user-centered application prototypes. Research candidate user behaviors and structure high-fidelity components.',
      syllabus: [
        'Design Foundations: Grid guidelines, visual hierarchy, typography pairings',
        'Prototyping Tools: Figma vector editor, components, auto-layout lists',
        'User Research: User persona blueprints, interviews, journey maps',
        'Wireframing: Low-fidelity sketches, high-fidelity UI components',
        'Design Systems: Reusable assets, tokens, developer handoff assets'
      ]
    }
  };

  let currentlySelectedCourseId = null;

  window.openCourseDetail = function(courseId) {
    const course = window.activeCoursesList ? window.activeCoursesList.find(c => c.id === Number(courseId)) : null;
    if (!course) return;

    currentlySelectedCourseId = courseId;
    document.getElementById("modalCourseTitle").textContent = course.title;
    document.getElementById("modalCourseLevel").textContent = course.level;
    document.getElementById("modalCoursePrice").textContent = "₹" + course.price.toLocaleString("en-IN");
    
    // Set custom icon SVG
    const iconBox = document.getElementById("modalCourseIcon");
    if (iconBox) {
      iconBox.innerHTML = svgIcon(ICONS[course.icon] || ICONS['layers']);
    }

    // Lookup descriptions & details
    const key = course.title.toLowerCase().trim();
    const details = COURSE_DETAILS[key] || {
      desc: 'Accelerated technical career path with hands-on labs, 1:1 mentor code reviews, and direct hiring pipelines.',
      syllabus: [
        'Module 1: Fundamental Concepts & Tools',
        'Module 2: Advanced Projects & Frameworks',
        'Module 3: Placement Prep & Mock Interviews'
      ]
    };

    document.getElementById("modalCourseDesc").textContent = details.desc;
    document.getElementById("modalCourseSyllabus").innerHTML = details.syllabus.map(s => `<li>${escapeHTML(s)}</li>`).join("");

    // Reset radio option visual check class states
    const onlineRadio = document.querySelector('input[name="enrollMode"][value="Online"]');
    if (onlineRadio) {
      onlineRadio.checked = true;
    }
    toggleModeSelection('Online');

    if (typeof openModal === "function") openModal("courseDetailModal");
  };

  window.toggleModeSelection = function(mode) {
    const onlineLbl = document.getElementById("lblModeOnline");
    const offlineLbl = document.getElementById("lblModeOffline");
    if (!onlineLbl || !offlineLbl) return;
    
    if (mode === 'Online') {
      onlineLbl.classList.add("selected");
      onlineLbl.style.borderColor = "var(--primary)";
      onlineLbl.style.background = "rgba(255, 122, 0, 0.05)";
      
      offlineLbl.classList.remove("selected");
      offlineLbl.style.borderColor = "var(--line)";
      offlineLbl.style.background = "rgba(255,255,255,0.01)";
    } else {
      offlineLbl.classList.add("selected");
      offlineLbl.style.borderColor = "var(--primary)";
      offlineLbl.style.background = "rgba(255, 122, 0, 0.05)";
      
      onlineLbl.classList.remove("selected");
      onlineLbl.style.borderColor = "var(--line)";
      onlineLbl.style.background = "rgba(255,255,255,0.01)";
    }
  };

  window.proceedToEnroll = function() {
    if (!currentlySelectedCourseId) return;
    const selectedMode = document.querySelector('input[name="enrollMode"]:checked').value;
    
    if (localStorage.getItem("edutech_token")) {
      window.location.href = `payment.html?course_id=${currentlySelectedCourseId}&mode=${selectedMode}`;
    } else {
      window.location.href = `login.html?redirect=payment.html?course_id=${currentlySelectedCourseId}%26mode=${selectedMode}`;
    }
  };

  window.openModal = function(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("open");
  };
  window.closeModal = function(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("open");
  };


  /* ============================================================
     16. ACTIVE VIEWPORT SCROLL NAVIGATION STYLES
     ============================================================ */
  const sections = document.querySelectorAll("section[id]");
  const navItems = document.querySelectorAll(".nav-links a");

  window.addEventListener("scroll", () => {
      let current = "";

      sections.forEach(section => {
          const sectionTop = section.offsetTop - 120;
          const sectionHeight = section.offsetHeight;

          if (window.scrollY >= sectionTop &&
              window.scrollY < sectionTop + sectionHeight) {
              current = section.getAttribute("id");
          }
      });

      navItems.forEach(link => {
          link.classList.remove("active");

          if (link.getAttribute("href") === "#" + current) {
              link.classList.add("active");
          }
      });
  });

})();

