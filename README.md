# ElevateIQ Enterprise Portal

ElevateIQ is a premium, modular Flask and Vanilla HTML5/CSS3 application designed for enterprise resource management, candidate recruitment, client CRM tracking, real-time workspace communication, and dynamic meeting planning.

---

## 📂 Project Architecture

The project is clean, modularized, and divided into two core directories:

```
elavateiq/
├── frontend/                     # Static files (HTML, CSS, JS) served by Flask
│   ├── css/                      # Curated CSS styling systems
│   │   ├── variables.css         # Custom properties (color palettes, typography)
│   │   ├── components.css        # Shared components (glass cards, buttons, tables)
│   │   └── chat.css              # Custom styling for Workspace and Group chats
│   ├── js/                       # Client-side API and modular logic
│   │   ├── api.js                # Core AJAX request handling wrapper
│   │   ├── auth.js               # Login, session persistence, and logout flow
│   │   ├── leaves.js             # Leaves balance and employee record controller
│   │   ├── recruitment.js        # Job listings and application tracker controller
│   │   ├── chat.js               # direct messaging (Workspace) and groups logic
│   │   └── crm.js                # Lead provisioning and customer relations CRM
│   ├── edutech/                  # Integrated EduTech Sub-portal (Landing page & CSS)
│   ├── index.html                # Main company landing page
│   ├── dashboard.html            # Role-based dashboard (Admin, Employee, Candidate)
│   └── openings.html             # Job opportunities board
│
├── backend/                      # Modular Flask API Engine
│   ├── app/                      # Main package directory
│   │   ├── __init__.py           # Application Factory & Blueprint registers
│   │   ├── config.py             # Server config schema and secret keys
│   │   ├── database.py           # Thread-safe PostgreSQL connection pooling & seeds
│   │   ├── auth.py               # Token checking and role auth wrappers
│   │   └── routes/               # Blueprint Route Handlers
│   │       ├── auth_routes.py    # Login, registration, report queries, and EduTech static routes
│   │       ├── crm_routes.py     # CRM client lists, meeting schedulers, and feedback
│   │       ├── chat.py           # Real-time workspace chat list and messaging
│   │       ├── leaves.py         # Attendance loggers, leave management, and employee registers
│   │       └── recruitment.py    # Careers engine and application submissions
│   ├── run.py                    # Server launch entry point
│   └── test_app.py               # Backend automated test suite
│
├── schema.sql                    # Full PostgreSQL database table definitions
├── init_db.py                    # Database schema runner & system admin seeder
└── .env                          # Local environment variables
```

---

## ✨ Core Features & Subpages

### 1. Unified Authentication & Access Control
- Custom JWT auth checking.
- Automated role-based layout rendering (Admin / Employee / Candidate).

### 2. Administrator Controls
- **Employees Management**: Complete database registry with dynamic Designation mapping. Admins can add new designations directly via the **"+"** form field.
- **Attendance Registry**: Live check-in/out logs for all active employees.
- **Leave Requests**: View, approve, or deny employee leave applications.
- **Notice Board Announcements**: Push news updates that display on all employee dashboards.
- **Admin CRM Panel**: Sales pipeline tracker allowing lead generation, interactions tracking, and client account provisioning.
- **Admin Report Center**: Generate custom printable PDF summaries for Attendance Audits, Department breakdowns, and Recruitment funnels.

### 3. Employee Workspace
- **Workspace Chats**: Chat with other employees (replacing old DMs).
- **Group Channels**: Join specific text groups for departments and teams.
- **Daily Attendance**: Mark "Check In" and "Check Out" directly from the overview tab.
- **Leave Requests**: Submit applications for Casual, Sick, Earned, or Emergency leaves with live balance counters.
- **Notice Board**: Read general team announcements.
- **Team Meetings**: See Zoom, Google Meet, Microsoft Teams, Slack Huddle, Cisco Webex, or Custom meeting schedules and join them instantly.

### 4. Candidate Portal
- **Careers Page**: Public careers portal detailing available roles.
- **Application Tracker**: Apply for open positions and track status updates (Screening, Interview, Offer, Rejected).

### 5. EduTech Sub-portal
- Fully isolated sub-application reachable via the main navbar.
- Dynamic courses list, track-specific contact inquiry form, and newsletter subscription forms hooked directly into dedicated database models (`edutech_contacts`, `newsletter_subscribers`).

---

## 🛠️ Local Development Setup

### 1. Prerequisites
- Python 3.8+
- PostgreSQL database (e.g. local install or Neon Cloud DB instance)

### 2. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/rohith1246/ELEVATEIQFINAL.git
cd ELEVATEIQFINAL
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql://<username>:<password>@<host>/<database>?sslmode=require
PORT=5000
```

### 4. Database Setup & Seeding
Execute `init_db.py` to create the tables in PostgreSQL and seed the default **System Administrator** account:
```bash
python init_db.py
```

### 5. Running the Application
Launch the Flask development server:
```bash
# Windows (PowerShell)
$env:PYTHONPATH="backend"
$env:FLASK_ENV="development"
python backend/run.py
```
The application will start on **`http://localhost:5000`**.

---

## 🔑 Seeding / Testing Credentials

You can log in to the dashboard (`http://localhost:5000/login.html`) using the following default test accounts:

| Role | Email address / Login ID | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@elevateiq.com` | `admin123` | Control panel, CRM lead gen, recruitment, notice boards. |
| **Employee** | `bathikadileep@gmail.com` | `test1234` | Check-in/out, apply leaves, workspace chat, view meetings. |
| **Candidate** | `rohith@gmail.com` | `test1234` | Job portal, application tracking status. |
