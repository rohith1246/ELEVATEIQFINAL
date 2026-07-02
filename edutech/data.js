/* ===================== Mock Data ===================== */

const ICONS = {
  code: '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
  coffee: '<path d="M17 8h1a4 4 0 1 1 0 8h-1"/><path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V8Z"/><line x1="6" y1="2" x2="6" y2="4"/><line x1="10" y1="2" x2="10" y2="4"/><line x1="14" y1="2" x2="14" y2="4"/>',
  layers: '<path d="M12 2 2 7l10 5 10-5-10-5Z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>',
  brain: '<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04Z"/>',
  chart: '<path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
  cloud: '<path d="M17.5 19a4.5 4.5 0 0 0 0-9 6 6 0 0 0-11.3-2A5 5 0 0 0 6.5 19h11Z"/>',
  server: '<rect x="2" y="3" width="20" height="7" rx="1"/><rect x="2" y="14" width="20" height="7" rx="1"/><line x1="6" y1="6.5" x2="6" y2="6.51"/><line x1="6" y1="17.5" x2="6" y2="17.51"/>',
  workflow: '<rect x="3" y="3" width="8" height="8" rx="1"/><path d="M7 11v4a2 2 0 0 0 2 2h4"/><rect x="13" y="13" width="8" height="8" rx="1"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>',
  bar: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
  palette: '<circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2a10 10 0 1 0 0 20 2 2 0 0 0 1.5-3.3 1.4 1.4 0 0 1 1-2.4H17a5 5 0 0 0 5-5c0-5-4.5-9-10-9Z"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z"/><path d="M14 2v6h6"/>',
  compass: '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
  mic: '<path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v1a7 7 0 0 1-14 0v-1M12 18v4M8 22h8"/>',
  users: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  briefcase: '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
  award: '<circle cx="12" cy="8" r="6"/><path d="M15.5 13.5 17 22l-5-3-5 3 1.5-8.5"/>',
  rocket: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09Z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2Z"/>',
};

const svgIcon = (paths) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;

/* ---------- Courses ---------- */
const COURSES = [
  { title:'Full Stack Web Development', level:'Beginner', duration:'20 weeks', price:45000, oldPrice:60000, rating:4.8, icon:'layers' },
  { title:'Python for Backend Engineers', level:'Beginner', duration:'12 weeks', price:28000, oldPrice:35000, rating:4.7, icon:'code' },
  { title:'Java Enterprise Full Stack', level:'Intermediate', duration:'18 weeks', price:42000, oldPrice:52000, rating:4.6, icon:'coffee' },
  { title:'AI & Machine Learning Bootcamp', level:'Advanced', duration:'22 weeks', price:65000, oldPrice:82000, rating:4.9, icon:'brain' },
  { title:'Data Science Professional', level:'Intermediate', duration:'20 weeks', price:52000, oldPrice:65000, rating:4.7, icon:'chart' },
  { title:'Cloud & DevOps Engineering', level:'Intermediate', duration:'16 weeks', price:48000, oldPrice:58000, rating:4.6, icon:'cloud' },
  { title:'AWS Solutions Architect Prep', level:'Advanced', duration:'10 weeks', price:32000, oldPrice:40000, rating:4.8, icon:'server' },
  { title:'Cyber Security Fundamentals', level:'Beginner', duration:'14 weeks', price:36000, oldPrice:45000, rating:4.5, icon:'shield' },
  { title:'UI/UX Design Professional', level:'Beginner', duration:'12 weeks', price:34000, oldPrice:42000, rating:4.8, icon:'palette' },
];

/* ---------- Team ---------- */
const TEAM = [
  { name:'Vikram Anand', role:'Founder & CEO', img:"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><rect width='100%' height='100%' fill='%230f1724'/><circle cx='150' cy='110' r='70' fill='%239aa0a6'/><rect x='60' y='210' width='180' height='60' rx='30' fill='%239aa0a6'/></svg>", bio:'Ex-engineering lead. 14 years building hiring pipelines.' },
  { name:'Meera Kapoor', role:'Head of Curriculum', img:"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><rect width='100%' height='100%' fill='%230f1724'/><circle cx='150' cy='110' r='70' fill='%239aa0a6'/><rect x='60' y='210' width='180' height='60' rx='30' fill='%239aa0a6'/></svg>", bio:'Designs every roadmap from real job descriptions.' },
  { name:'Rohan Das', role:'Lead Mentor, Full Stack', img:"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><rect width='100%' height='100%' fill='%230f1724'/><circle cx='150' cy='110' r='70' fill='%239aa0a6'/><rect x='60' y='210' width='180' height='60' rx='30' fill='%239aa0a6'/></svg>", bio:'Reviews 200+ student PRs a month, personally.' },
  { name:'Ananya Iyer', role:'Head of Placements', img:"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><rect width='100%' height='100%' fill='%230f1724'/><circle cx='150' cy='110' r='70' fill='%239aa0a6'/><rect x='60' y='210' width='180' height='60' rx='30' fill='%239aa0a6'/></svg>", bio:'Runs the hiring partner network of 210+ companies.' },
];

/* ---------- FAQ ---------- */
const FAQS = [
  { q:'Do I need prior coding experience to join?', a:'No. Most of our tracks (Full Stack, Python, UI/UX) start from zero. Advanced tracks like AI/ML assume basic programming comfort, which we can help you build first with a short prep module.' },
  { q:'How does the placement guarantee work?', a:"We don't promise a specific salary, but our placement team works with every eligible graduate — mock interviews, referrals, and application support — until you accept an offer or exhaust our partner network." },
  { q:'Can I learn part-time while working a job?', a:'Yes. Most programs offer an evening/weekend cohort schedule alongside the full-time track, with the same mentor access and project requirements.' },
  { q:'What happens if I fall behind during the program?', a:'Every cohort has buffer weeks and 1:1 catch-up sessions with mentors. You can also pause and resume in the next cohort at no extra cost.' },
  { q:'Are the certificates recognized by employers?', a:"Our certificates carry weight primarily because of the outcomes attached to them — but what actually gets you hired is the project portfolio and mock interview record we build with you." },
  { q:'What is the refund policy?', a:'Full refund within the first 7 days of a cohort if the program is not the right fit — no questions asked. See our Refund Policy for the complete terms.' },
];
