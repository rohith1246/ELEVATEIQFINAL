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


