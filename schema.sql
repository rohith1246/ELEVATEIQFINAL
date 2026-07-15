-- Elevate IQ PostgreSQL Schema

-- 1. Users Table (Auth and Roles)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'candidate', -- 'admin', 'employee', 'candidate'
    portal VARCHAR(20) NOT NULL DEFAULT 'elevateiq', -- 'elevateiq', 'edutech'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Employees Table (Linked to Users for employee details & leave balances)
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    user_id INT UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    employee_id VARCHAR(50) UNIQUE NOT NULL,
    phone_number VARCHAR(20),
    department VARCHAR(100),
    designation VARCHAR(100),
    date_of_joining DATE,
    status VARCHAR(20) DEFAULT 'Active', -- 'Active', 'Inactive'
    casual_leave INT DEFAULT 12,
    sick_leave INT DEFAULT 10,
    earned_leave INT DEFAULT 15,
    emergency_leave INT DEFAULT 5
);

-- 3. Attendance Table
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    check_in TIME,
    check_out TIME,
    working_hours DECIMAL(5,2) DEFAULT 0.00,
    status VARCHAR(20) DEFAULT 'Present', -- 'Present', 'Absent', 'Half Day', 'Leave'
    UNIQUE (employee_id, date)
);

-- 4. Leaves Table
CREATE TABLE IF NOT EXISTS leaves (
    id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    leave_type VARCHAR(20) NOT NULL, -- 'Casual', 'Sick', 'Earned', 'Emergency'
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'Pending', -- 'Pending', 'Approved', 'Rejected'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Jobs Table (Recruitment openings)
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    department VARCHAR(100) NOT NULL,
    experience_required VARCHAR(50),
    skills_required VARCHAR(255),
    location VARCHAR(100),
    salary_range VARCHAR(100),
    description TEXT,
    status VARCHAR(20) DEFAULT 'Open', -- 'Open', 'Closed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Applications Table
CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    job_id INT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    candidate_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,
    phone VARCHAR(20),
    resume_filename VARCHAR(255),
    status VARCHAR(20) DEFAULT 'Pending', -- 'Pending', 'Shortlisted', 'Accepted', 'Rejected'
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Announcements Table
CREATE TABLE IF NOT EXISTS announcements (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Chat Conversations (DM or Group)
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    type VARCHAR(10) NOT NULL DEFAULT 'dm',   -- 'dm' | 'group'
    name VARCHAR(150),                         -- only for groups
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Members of a conversation
CREATE TABLE IF NOT EXISTS conversation_members (
    id SERIAL PRIMARY KEY,
    conversation_id INT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (conversation_id, user_id)
);

-- 10. Messages
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id INT REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. Read receipts (for unread badge counts)
CREATE TABLE IF NOT EXISTS message_reads (
    id SERIAL PRIMARY KEY,
    message_id INT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (message_id, user_id)
);

-- 12. EduTech Contact inquiries
CREATE TABLE IF NOT EXISTS edutech_contacts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    track VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. EduTech Newsletter subscribers
CREATE TABLE IF NOT EXISTS newsletter_subscribers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 14. ElevateIQ Main Contact inquiries
CREATE TABLE IF NOT EXISTS elevate_iq_contacts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 15. Meetings Table (Zoom/GMeet Integration)
CREATE TABLE IF NOT EXISTS meetings (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    meeting_link VARCHAR(500) NOT NULL,
    scheduled_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 16. Clients Table (CRM and Portals)
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    user_id INT UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    client_id VARCHAR(50) UNIQUE,
    company_name VARCHAR(150) NOT NULL,
    contact_name VARCHAR(150),
    email VARCHAR(150),
    phone_number VARCHAR(20),
    deal_size DECIMAL(12,2) DEFAULT 0.00,
    status VARCHAR(30) DEFAULT 'Lead', -- 'Lead', 'Contacted', 'Proposal', 'Active Client', 'Lost'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 17. Client Interactions Table
CREATE TABLE IF NOT EXISTS client_interactions (
    id SERIAL PRIMARY KEY,
    client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL, -- 'Call', 'Email', 'Meeting', 'Note'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alter meetings table for B2B Client integration
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS client_id INT REFERENCES clients(id) ON DELETE SET NULL;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS meeting_type VARCHAR(20) DEFAULT 'internal';

-- 18. Designations Table
CREATE TABLE IF NOT EXISTS designations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 19. Courses Table
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL UNIQUE,
    level VARCHAR(50) NOT NULL, -- 'Beginner', 'Intermediate', 'Advanced'
    duration VARCHAR(50) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    old_price DECIMAL(10,2),
    rating DECIMAL(3,2) DEFAULT 5.00,
    icon VARCHAR(50) DEFAULT 'layers',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 20. Course Enrollments
CREATE TABLE IF NOT EXISTS course_enrollments (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    price_paid DECIMAL(10,2) NOT NULL,
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'Active', -- 'Active', 'Completed', 'Cancelled'
    mode VARCHAR(20) DEFAULT 'Online',
    UNIQUE (user_id, course_id)
);

-- 21. Live Classes
CREATE TABLE IF NOT EXISTS live_classes (
    id SERIAL PRIMARY KEY,
    course_id INT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL, -- 'Zoom', 'Google Meet', 'Teams', etc.
    meeting_link VARCHAR(500) NOT NULL,
    scheduled_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ==================== PERFORMANCE OPTIMIZATION INDEXES ====================

-- Index for user role queries
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Index for employees table user_id join keys
CREATE INDEX IF NOT EXISTS idx_employees_user_id ON employees(user_id);

-- Index for employee attendance records
CREATE INDEX IF NOT EXISTS idx_attendance_employee_id ON attendance(employee_id);

-- Indexes for employee leaves (by employee and status)
CREATE INDEX IF NOT EXISTS idx_leaves_employee_id ON leaves(employee_id);
CREATE INDEX IF NOT EXISTS idx_leaves_status ON leaves(status);

-- Index for job applications
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);

-- Index for conversation membership lookups
CREATE INDEX IF NOT EXISTS idx_conversation_members_user_id ON conversation_members(user_id);

-- Indexes for chat message history retrievals (single and composite)
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_sent_at ON messages(conversation_id, sent_at);

-- Index for client table user_id join keys
CREATE INDEX IF NOT EXISTS idx_clients_user_id ON clients(user_id);

-- Index for client interactions
CREATE INDEX IF NOT EXISTS idx_client_interactions_client_id ON client_interactions(client_id);

-- Indexes for meetings scheduled times and client keys
CREATE INDEX IF NOT EXISTS idx_meetings_client_id ON meetings(client_id);
CREATE INDEX IF NOT EXISTS idx_meetings_scheduled_at ON meetings(scheduled_at);

-- Indexes for EduTech extensions
CREATE INDEX IF NOT EXISTS idx_course_enrollments_user ON course_enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_live_classes_course ON live_classes(course_id);

-- 22. Assignments Table
CREATE TABLE IF NOT EXISTS assignments (
    id SERIAL PRIMARY KEY,
    course_id INT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    due_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 23. Assignment Submissions
CREATE TABLE IF NOT EXISTS assignment_submissions (
    id SERIAL PRIMARY KEY,
    assignment_id INT NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    submission_text TEXT,
    file_path VARCHAR(255),
    grade VARCHAR(10), -- e.g., 'A', 'B', 'Pass', 'Pending'
    feedback TEXT,
    status VARCHAR(20) DEFAULT 'Pending', -- 'Pending', 'Graded', 'Submitted'
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (assignment_id, user_id)
);

-- 24. Quizzes
CREATE TABLE IF NOT EXISTS quizzes (
    id SERIAL PRIMARY KEY,
    course_id INT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    duration_minutes INT DEFAULT 30,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 25. Quiz Questions
CREATE TABLE IF NOT EXISTS quiz_questions (
    id SERIAL PRIMARY KEY,
    quiz_id INT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    option_a VARCHAR(255) NOT NULL,
    option_b VARCHAR(255) NOT NULL,
    option_c VARCHAR(255) NOT NULL,
    option_d VARCHAR(255) NOT NULL,
    correct_option CHAR(1) NOT NULL -- 'A', 'B', 'C', 'D'
);

-- 26. Quiz Attempts
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id SERIAL PRIMARY KEY,
    quiz_id INT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    score INT NOT NULL,
    total_questions INT NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 27. Course Resources
CREATE TABLE IF NOT EXISTS course_resources (
    id SERIAL PRIMARY KEY,
    course_id INT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    resource_type VARCHAR(50) DEFAULT 'PDF', -- 'PDF', 'Link', 'Repo', 'Slides'
    resource_url VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 28. Placement Tracks
CREATE TABLE IF NOT EXISTS placement_tracks (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    current_stage VARCHAR(50) DEFAULT 'Profile Setup', -- 'Profile Setup', 'Resume Review', 'Mock Interview Prep', 'Technical Assessment', 'HR Interview', 'Placed'
    next_steps TEXT,
    resume_approved BOOLEAN DEFAULT FALSE,
    mock_interview_score INT DEFAULT 0,
    recruiter_feedback TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 29. Student Leaves
CREATE TABLE IF NOT EXISTS student_leaves (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    leave_type VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'Pending', -- 'Pending', 'Approved', 'Rejected'
    approved_by INT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for student dashboard extensions
CREATE INDEX IF NOT EXISTS idx_assignments_course ON assignments(course_id);
CREATE INDEX IF NOT EXISTS idx_submissions_user ON assignment_submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_course ON quizzes(course_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user ON quiz_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_resources_course ON course_resources(course_id);
CREATE INDEX IF NOT EXISTS idx_placement_user ON placement_tracks(user_id);
CREATE INDEX IF NOT EXISTS idx_student_leaves_user ON student_leaves(user_id);
CREATE INDEX IF NOT EXISTS idx_student_leaves_status ON student_leaves(status);

-- 30. Tickets Table (Support system)
CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'General', -- 'Technical', 'Billing', 'HR', 'Academic', 'General'
    status VARCHAR(20) DEFAULT 'Open', -- 'Open', 'In Progress', 'Resolved', 'Closed'
    priority VARCHAR(20) DEFAULT 'Medium', -- 'Low', 'Medium', 'High'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    admin_notes TEXT,
    resolved_by INT REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMP
);

-- Indexes for ticketing query performance
CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);

-- ==================== JOB ASSESSMENT SYSTEM ====================

-- 31. Assessment Questions (Per-Job question bank)
CREATE TABLE IF NOT EXISTS assessment_questions (
    id SERIAL PRIMARY KEY,
    job_id INT REFERENCES jobs(id) ON DELETE CASCADE,  -- NULL = global fallback for all jobs
    question_text TEXT NOT NULL,
    option_a VARCHAR(500) NOT NULL,
    option_b VARCHAR(500) NOT NULL,
    option_c VARCHAR(500) NOT NULL,
    option_d VARCHAR(500) NOT NULL,
    correct_option CHAR(1) NOT NULL CHECK (correct_option IN ('A','B','C','D')),
    difficulty VARCHAR(20) DEFAULT 'Medium' CHECK (difficulty IN ('Easy','Medium','Hard')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 32. Assessments (One per application — holds token, status, score, anti-cheat data)
CREATE TABLE IF NOT EXISTS assessments (
    id SERIAL PRIMARY KEY,
    application_id INT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    token VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'Pending' CHECK (status IN ('Pending','In Progress','Completed','Expired','Flagged')),
    score INT,
    total_questions INT,
    percentage DECIMAL(5,2),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    tab_switches INT DEFAULT 0,
    screen_share_granted BOOLEAN DEFAULT FALSE,
    is_suspicious BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 33. Assessment Answers (Candidate's submitted answers per question)
CREATE TABLE IF NOT EXISTS assessment_answers (
    id SERIAL PRIMARY KEY,
    assessment_id INT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    question_id INT NOT NULL REFERENCES assessment_questions(id) ON DELETE CASCADE,
    selected_option CHAR(1) CHECK (selected_option IN ('A','B','C','D')),
    is_correct BOOLEAN
);

-- Indexes for assessment system
CREATE INDEX IF NOT EXISTS idx_assessments_application ON assessments(application_id);
CREATE INDEX IF NOT EXISTS idx_assessments_token ON assessments(token);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessment_questions_job ON assessment_questions(job_id);
CREATE INDEX IF NOT EXISTS idx_assessment_answers_assessment ON assessment_answers(assessment_id);

-- 34. Password Resets (Forgot password token storage)
CREATE TABLE IF NOT EXISTS password_resets (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(128) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_password_resets_token ON password_resets(token);
CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);
