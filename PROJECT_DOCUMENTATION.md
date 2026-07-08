# ElevateIQ & EduTech Portal Overview

This document provides a comprehensive summary of the technical architecture, database schema, user roles, backend API endpoints, and frontend features of the **ElevateIQ** workspace portal and **EduTech** academy platform.

---

## 🛠️ Technology Stack

1. **Backend**: Python (Flask)
2. **Database**: PostgreSQL (relational tables managed by `psycopg2`)
3. **Frontend**: HTML5, Vanilla JavaScript, CSS3 (Glassmorphism layout system, responsive CSS grid, Lenis scroll, and GSAP/ScrollTrigger animations)
4. **Authentication**: JWT token-based auth stored in `localStorage` under `token` (ElevateIQ) and `edutech_token` (EduTech)

---

## 🗄️ Database Tables (`schema.sql`)

* **`users`**: Stores user profiles. Roles: `admin`, `employee`, `client`, `candidate`. Portals: `elevateiq`, `edutech`.
* **`courses`**: Catalog list of academic courses offered.
* **`course_enrollments`**: User course purchase orders and statuses.
* **`live_classes`**: Virtual classrooms scheduled by administrators.
* **`crm_projects`**: Corporate client projects and progress tracking.
* **`crm_tasks`**: Tasks nested within client projects.
* **`leaves`**: Employee workspace attendance check-ins, check-outs, and leave applications.
* **`crm_invoices`** & **`crm_proposals`**: Client accounting, proposals, and billing history.
* **`job_openings`**: Recruitment listings for candidate applications.
* **`candidate_applications`**: Job applicant logs and stage tracking.
* **`chat_messages`**: Real-time messaging logs for employee chat rooms.
* **`announcements`**: Corporate notice board logs.

---

## 🔑 Roles & Permissions

1. **`admin`**: Full control panel access. Management of courses, virtual classrooms, CRM clients, projects, invoices, recruitment, notice boards, and system configurations.
2. **`employee`**: Workspace log-in, check-in/out, leave requests, leave approvals (if HR manager), chat messaging, and viewing payroll slips.
3. **`client`**: Access to project progress trackers, tasks, billing invoices, and corporate project proposals.
4. **`candidate` / `student`**: Academy portal registration, course enrollment, Pathfinder recommendation quiz, checkout mock payment portals, and job application tracking.

---

## 📡 Backend API Endpoints

### 🔐 1. Authentication & Employee Management (`auth_routes.py`)
* `POST /register`: Registers new users on either portal.
* `POST /login`: authenticates credentials, returns JWT tokens and roles.
* `POST /logout`: Terminate user sessions.
* `GET/PUT /profile`: View and update profile settings.
* `GET /employees`: List all employees (restricted to admins).
* `POST /employees`: Create a new employee profile (bypasses DB `salary` write if column missing).
* `PUT /employees/<id>`: Update an employee's details.
* `DELETE /employees/<id>`: Remove an employee profile.
* `GET /designations`: Retrieve designation profiles.
* `POST /designations`: Create a new designation level.
* `GET /announcements`: Read notices.
* `POST /announcements`: Post new notices (Admin/HR only).

### 🎓 2. EduTech Academy routes (`edutech_routes.py`)
* `GET /api/edutech/courses`: Fetch all courses.
* `POST /api/edutech/courses`: Create a new course card (Admin only).
* `PUT /api/edutech/courses/<id>`: Modify course properties (Admin only).
* `DELETE /api/edutech/courses/<id>`: Delete a course card (Admin only).
* `GET /api/edutech/my-courses`: Fetch courses enrolled by the active logged-in student.
* `POST /api/edutech/enroll`: Process mock checkout payment and register student to a course.
* `GET /api/edutech/my-live-classes`: Fetch upcoming classes for enrolled courses.
* `GET /api/edutech/enrollments`: List all enrollments (Admin/Employee only).
* `POST /api/edutech/live-classes`: Schedule a virtual classroom meeting (Admin only).
* `GET /api/edutech/live-classes`: List scheduled virtual meetings.
* `DELETE /api/edutech/live-classes/<id>`: Cancel a virtual meeting (Admin only).
* `GET /api/edutech/invoice/<id>`: Retrieve checkout payment invoice details.

### 📅 3. Leave & Attendance Management (`leaves.py`)
* `POST /api/checkin`: Register work log check-in timestamp.
* `POST /api/checkout`: Register work log check-out timestamp.
* `GET /api/attendance/logs`: Fetch login and time tracking logs.
* `POST /api/leaves`: Submit a new leave application.
* `GET /api/leaves`: Fetch leave application history.
* `PUT /api/leaves/<id>`: Approve or reject employee leaves (restricted to HR managers).

### 💼 4. CRM Client Operations (`crm_routes.py`)
* `GET/POST /api/crm/projects`: Manage client projects (Admin/Client only).
* `GET/POST /api/crm/tasks`: Manage tasks (Admin/Client/Employee only).
* `GET/POST /api/crm/proposals`: Manage proposals.
* `GET/POST /api/crm/invoices`: Manage invoices.

### 💰 5. Demo Payroll Ledger (`payroll.py`)
* `GET /api/payroll/summary`: Returns static mock arrays of workspace payroll.
* `GET /api/payroll/ledger`: Returns mock payment lists for payslips (Decoupled from database writes to prevent migration conflicts).

### 📁 6. Recruitment Tracker (`recruitment.py`)
* `GET/POST /api/recruitment/jobs`: Manage job openings.
* `GET/POST /api/recruitment/applications`: Process job applicant profiles and statuses.

---

## 🎨 Frontend Features & Micro-Animations

1. **`frontend/style.css`**:
   * Global typography (`Space Grotesk`, `Inter`), resets, glassmorphism design tokens.
   * **Navbar click scale animation**: Scale-pulse transition (`@keyframes navClickScale`) giving physical-click user feedback.
   * **Alive-Card animations**: Applied to IT and Non-IT services cards. Elevates card by `10px`, scales image by `8%`, rotates floating badges, and slides checklist items staggered to the right.
2. **`edutech/style.css`**:
   * **FOUC Prevention**: Prefixes animated hero stats with `.js` to hide them before scripts parse.
   * **Highlight-Pulse glow**: Animates a pulsing neon outline glow around recommended program cards.
   * **Skeleton loading card shimmers**: Prevents layout shifts while loading asynchronous database courses.
3. **`edutech/script.js`**:
   * **Delayed Preloader**: Initial loading races the async API course fetch against a 3s timeout before removing preloader, allowing ScrollTrigger to hook clean.
   * **Pathfinder quiz recommendation highlight**: Resets pills to 'All', searches by course title, and highlights the recommended card with `.highlight-pulse`.
