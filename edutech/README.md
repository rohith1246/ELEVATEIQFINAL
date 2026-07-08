# ElevateIQ — EdTech Website

A production-ready, single-page marketing site for a career-first tech academy. Built as static HTML/CSS/JS (no build step required) so it can be deployed anywhere instantly.

## What's inside
- `index.html` — all page markup/sections
- `style.css` — full design system (colors, type, components, responsive rules)
- `data.js` — mock content for services, courses, team, FAQ
- `script.js` — all interactions: preloader, cursor glow, magnetic buttons, particle hero canvas, GSAP scroll reveals, animated counters, course search/filter, scroll-linked roadmap, testimonials carousel, flip-card team, FAQ accordion, validated contact form, newsletter form, and a rule-based AI advisor chat widget

## Run locally
No build tools needed. Either:
- Double-click `index.html`, or
- Serve it (recommended, avoids browser file:// restrictions):
  ```
  npx serve .
  ```
  then open the printed local URL.

## Deploy in under a minute
**Vercel / Netlify:** drag the whole folder into the dashboard (or run `vercel` / `netlify deploy` from inside this folder — no build command needed, output directory is `.`).

**GitHub Pages:** push this folder to a repo and enable Pages on the `main` branch root.

**Any static host (S3, Cloudflare Pages, Render, etc.):** upload the 4 files as-is.

## Editing content
All copy for Services, Courses, Team bios, and FAQ lives in `data.js` as plain arrays — edit those objects and the page re-renders automatically, no HTML editing required.

Colors and type live at the top of `style.css` under `:root` — change the CSS variables to re-theme the whole site.

## Notes
- GSAP, ScrollTrigger, and Lenis (smooth scroll) load from CDN — an internet connection is required for animations; core functionality (nav, forms, filtering, FAQ) works even if those fail to load.
- Avatar/team photos use `i.pravatar.cc` placeholders — swap the `img` URLs in `data.js` / `index.html` for real photos before launch.
- The contact form and newsletter form are front-end only (validate + show a success state). Wire the `submit` handlers in `script.js` to your email service (e.g. Resend, Formspree) or backend endpoint to actually send data.
- `robots`/sitemap and analytics snippets aren't included — add before going live.
