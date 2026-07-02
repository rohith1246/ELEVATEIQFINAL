/* ===================== ElevateIQ — Interactions ===================== */
(function(){
  "use strict";

  const hasGSAP = typeof gsap !== "undefined";
  if (hasGSAP && typeof ScrollTrigger !== "undefined") gsap.registerPlugin(ScrollTrigger);
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------- Preloader ---------------- */
  window.addEventListener("load", () => {
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
      // hero canvas initialization removed for minimal UI
    }, 650);
  });

  /* ---------------- Lenis smooth scroll ---------------- */
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

  /* Custom cursor removed — use native pointer for accessibility and simplicity */

  /* ---------------- Magnetic buttons ---------------- */
  document.querySelectorAll(".magnetic").forEach(btn=>{
    btn.addEventListener("mousemove", e=>{
      const r = btn.getBoundingClientRect();
      const x = e.clientX - r.left - r.width/2;
      const y = e.clientY - r.top - r.height/2;
      btn.style.transform = `translate(${x*0.25}px, ${y*0.35}px)`;
    });
    btn.addEventListener("mouseleave", ()=>{ btn.style.transform = "translate(0,0)"; });
  });

  /* ---------------- Navbar ---------------- */
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

  /* ---------------- Hero canvas particles ---------------- */
  function initHeroLoad(){
    const canvas = document.getElementById("hero-canvas");
    if (!canvas || reduceMotion) return;
    const ctx = canvas.getContext("2d");
    let w,h,particles=[];
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

  /* ---------------- Hero text reveal + floating icons ---------------- */
  if (hasGSAP){
    gsap.from(".hero-line span", { yPercent:120, duration:1, ease:"power4.out", stagger:0.12, delay:0.2 });
    gsap.from(".hero-badge", { opacity:0, y:-14, duration:0.8, delay:0.1 });
    gsap.from(".hero-ctas .btn", { opacity:0, y:20, duration:0.8, stagger:0.1, delay:0.9 });
    gsap.from(".hero-stats", { opacity:0, y:20, duration:0.8, delay:1.1 });
    document.querySelectorAll("[data-float]").forEach((el,i)=>{
      gsap.to(el, { y: i%2===0 ? -22 : 22, duration: 3+i*0.4, ease:"sine.inOut", yoyo:true, repeat:-1 });
    });
  }

  /* ---------------- Scroll reveal ---------------- */
  function setupReveal(){
    const items = document.querySelectorAll(".reveal");
    if (hasGSAP && typeof ScrollTrigger !== "undefined"){
      items.forEach(el=>{
        gsap.to(el, {
          opacity:1, y:0, duration:0.9, ease:"power3.out",
          scrollTrigger:{ trigger: el, start:"top 88%" }
        });
      });
    } else {
      items.forEach(el=>{ el.style.opacity=1; el.style.transform="none"; });
    }
  }

  /* ---------------- Counters ---------------- */
  function setupCounters(){
    document.querySelectorAll("[data-count]").forEach(el=>{
      const target = parseFloat(el.getAttribute("data-count"));
      const decimals = parseInt(el.getAttribute("data-decimal")||"0");
      const prefix = el.getAttribute("data-prefix")||"";
      const suffix = el.getAttribute("data-suffix")||"";
      const run = ()=>{
        let obj = {val:0};
        if (hasGSAP){
          gsap.to(obj, { val: target, duration:1.8, ease:"power2.out",
            onUpdate: ()=> el.textContent = prefix + obj.val.toFixed(decimals) + suffix
          });
        } else {
          el.textContent = prefix + target.toFixed(decimals) + suffix;
        }
      };
      if ("IntersectionObserver" in window){
        const io = new IntersectionObserver((entries)=>{
          entries.forEach(entry=>{ if(entry.isIntersecting){ run(); io.unobserve(el); } });
        }, {threshold:0.4});
        io.observe(el);
      } else run();
    });
  }

  /* ---------------- Render: Courses ---------------- */
  function money(n){ return "₹" + n.toLocaleString("en-IN"); }
  function renderCourses(list){
    const grid = document.getElementById("coursesGrid");
    if (!list.length){ grid.innerHTML = `<p style="color:var(--muted); grid-column:1/-1; text-align:center; padding:40px 0;">No programs match that search.</p>`; return; }
    grid.innerHTML = list.map(c => `
      <div class="glass-card course-card reveal" style="opacity:1; transform:none;">
        <div class="course-thumb">
          ${svgIcon(ICONS[c.icon]||ICONS.layers)}
          <span class="course-level">${c.level}</span>
        </div>
        <div class="course-body">
          <h3>${c.title}</h3>
          <div class="course-meta">
            <span>${svgIcon('<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>')}${c.duration}</span>
            <span class="rating">${svgIcon('<polygon points="12 2 15 8.5 22 9.5 17 14.5 18.5 21.5 12 18 5.5 21.5 7 14.5 2 9.5 9 8.5 12 2"/>')}${c.rating}</span>
          </div>
          <div class="course-foot">
           
            <button class="btn btn-primary btn-sm magnetic enroll-btn">Enroll</button>
          </div>
        </div>
      </div>`).join("");

    grid.querySelectorAll(".enroll-btn").forEach(b=> b.addEventListener("click", ()=>{
      document.getElementById("contact").scrollIntoView({behavior:"smooth"});
    }));
  }

  function setupCourses(){
    renderCourses(COURSES);
    const search = document.getElementById("courseSearch");
    const pills = document.querySelectorAll(".pill");
    let activeFilter = "all";
    function apply(){
      const q = search.value.trim().toLowerCase();
      const filtered = COURSES.filter(c=>{
        const matchesFilter = activeFilter==="all" || c.level===activeFilter;
        const matchesSearch = !q || c.title.toLowerCase().includes(q);
        return matchesFilter && matchesSearch;
      });
      renderCourses(filtered);
    }
    search.addEventListener("input", apply);
    pills.forEach(p=> p.addEventListener("click", ()=>{
      pills.forEach(x=>x.classList.remove("active"));
      p.classList.add("active");
      activeFilter = p.dataset.filter;
      apply();
    }));
  }

  /* ---------------- Roadmap rail fill ---------------- */
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

  /* ---------------- Render: Team ---------------- */
  function renderTeam(){
    document.getElementById("teamGrid").innerHTML = TEAM.map(t => `
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

  /* ---------------- Render: FAQ ---------------- */
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

  /* ---------------- Testimonials carousel ---------------- */
  function setupTestimonials(){
    const track = document.getElementById("testTrack");
    const cards = track.children;
    let index = 0;
    function cardWidth(){ return cards[0].getBoundingClientRect().width + 24; }
    function go(dir){
      const visible = Math.max(1, Math.floor(track.parentElement.offsetWidth / cardWidth()));
      index = Math.max(0, Math.min(cards.length - visible, index + dir));
      track.style.transform = `translateX(-${index * cardWidth()}px)`;
    }
    document.getElementById("testPrev").addEventListener("click", ()=> go(-1));
    document.getElementById("testNext").addEventListener("click", ()=> go(1));
  }

  /* ---------------- Contact form validation ---------------- */
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

    const newsletter = document.getElementById("newsletterForm");
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

  /* ---------------- AI Advisor (rule-based) ---------------- */
  function setupAI(){
    const toggle = document.getElementById("ai-toggle");
    const panel = document.getElementById("ai-panel");
    const body = document.getElementById("aiBody");
    const input = document.getElementById("aiInput");
    const send = document.getElementById("aiSend");

    toggle.addEventListener("click", ()=> panel.classList.toggle("open"));

    const responses = [
      { k:["beginner","start","new","zero"], r:"If you're starting from zero, Full Stack Web Development or Python for Backend Engineers are the best entry points — both assume no prior coding experience." },
      { k:["long","duration","weeks","time"], r:"Most programs run 12–22 weeks depending on the track. AI & Machine Learning is our longest at 22 weeks; UI/UX Design is our shortest at 12." },
      { k:["placement","job","hire","career"], r:"Yes — every program includes placement support: mock interviews, resume audits, and direct introductions across our 210+ hiring partners." },
      { k:["price","cost","fee","fees"], r:"Program fees range roughly ₹28,000–₹65,000 depending on the track and length. Scroll to the Courses section to compare exact pricing." },
      { k:["ai","machine learning","ml"], r:"Our AI & Machine Learning Bootcamp runs 22 weeks, from regression through transformer models, ending with a deployed capstone project." },
      { k:["contact","talk","human","advisor","call"], r:"Happy to connect you with a human advisor — scroll down to the Contact section and send a message, or use the WhatsApp option." },
    ];

    function reply(text){
      const lower = text.toLowerCase();
      const hit = responses.find(r => r.k.some(k => lower.includes(k)));
      return hit ? hit.r : "Good question — an advisor can give you a precise answer on that. Want me to route you to the contact form?";
    }

    function addMsg(text, who){
      const el = document.createElement("div");
      el.className = "ai-msg " + who;
      el.textContent = text;
      body.appendChild(el);
      body.scrollTop = body.scrollHeight;
    }

    function handleSend(text){
      if (!text.trim()) return;
      addMsg(text, "user");
      input.value = "";
      setTimeout(()=> addMsg(reply(text), "bot"), 500);
    }

    send.addEventListener("click", ()=> handleSend(input.value));
    input.addEventListener("keydown", e=>{ if(e.key==="Enter") handleSend(input.value); });
    document.querySelectorAll(".ai-quick button").forEach(b=>{
      b.addEventListener("click", ()=> handleSend(b.dataset.q));
    });
  }

  /* ---------------- Init ---------------- */
  document.getElementById("year").textContent = new Date().getFullYear();
  setupCourses();
  renderTeam();
  renderFAQ();
  setupTestimonials();
  setupForm();
  setupAI();
  setupCounters();
  setupRoadmap();
  setupReveal();


/* ===== Active Navbar on Scroll ===== */

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
