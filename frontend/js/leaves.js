// 1. Admin Overview
async function loadAdminOverview() {
    const stats = await apiCall("/dashboard/stats");
    document.getElementById("stat_total_emp").textContent = stats.active_employees;
    document.getElementById("stat_present").textContent = stats.present_today;
    document.getElementById("stat_absent").textContent = stats.absent_today;
    document.getElementById("stat_pending_leaves").textContent = stats.pending_leaves;
    document.getElementById("stat_open_jobs").textContent = stats.active_jobs;
    document.getElementById("stat_total_apps").textContent = stats.total_applications;

    const noticeList = document.getElementById("adminNoticeList");
    noticeList.innerHTML = "";
    const notices = await apiCall("/announcements");
    if (notices.length === 0) noticeList.innerHTML = `<div style="color:var(--ink-faint); font-size:13px;">No announcements published.</div>`;
    notices.slice(0, 3).forEach(n => {
        noticeList.innerHTML += `
            <div style="background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:15px; border-radius:12px;">
                <h4 style="font-weight:600; font-size:14px; margin-bottom:4px;">${n.title}</h4>
                <p style="font-size:13px; color:var(--ink-soft);">${n.content}</p>
                <div style="font-size:11px; color:var(--ink-faint); margin-top:8px;">${new Date(n.created_at).toLocaleString()}</div>
            </div>
        `;
    });
    loadAdminMeetings();
}

// 2. Admin Employees Management
let allEmployees = [];

async function loadDesignations(selectedVal = null) {
    try {
        const list = await apiCall("/designations");
        const addSelect = document.getElementById("addDesg");
        const editSelect = document.getElementById("editDesg");
        
        let optionsHtml = '<option value="">-- Select Designation --</option>';
        list.forEach(d => {
            optionsHtml += `<option value="${escapeHTML(d.name)}">${escapeHTML(d.name)}</option>`;
        });
        
        if (addSelect) {
            addSelect.innerHTML = optionsHtml;
            if (selectedVal) {
                addSelect.value = selectedVal;
            }
        }
        if (editSelect) {
            editSelect.innerHTML = optionsHtml;
            if (selectedVal) {
                editSelect.value = selectedVal;
            }
        }
    } catch (e) {
        console.error("Could not load designations", e);
    }
}

function toggleDesgInput(mode, showInput) {
    const selectArea = document.getElementById(`${mode}DesgSelectArea`);
    const inputArea = document.getElementById(`${mode}DesgInputArea`);
    const customInput = document.getElementById(`${mode}DesgCustom`);
    
    if (showInput) {
        if (selectArea) selectArea.style.display = "none";
        if (inputArea) inputArea.style.display = "flex";
        if (customInput) {
            customInput.value = "";
            customInput.focus();
        }
    } else {
        if (selectArea) selectArea.style.display = "flex";
        if (inputArea) inputArea.style.display = "none";
    }
}

async function submitCustomDesignation(mode) {
    const customInput = document.getElementById(`${mode}DesgCustom`);
    if (!customInput) return;
    const name = customInput.value.trim();
    if (!name) return;
    
    try {
        const res = await apiCall("/designations", "POST", { name });
        alert(`Designation "${res.name}" created successfully!`);
        await loadDesignations(res.name);
        toggleDesgInput(mode, false);
    } catch(e) {
        console.error(e);
    }
}

async function loadAdminEmployees() {
    await loadDesignations();
    allEmployees = await apiCall("/employees");
    renderEmployeesTable(allEmployees);
}

function renderEmployeesTable(list) {
    const tbody = document.getElementById("employeesTableBody");
    tbody.innerHTML = "";
    list.forEach(emp => {
        tbody.innerHTML += `
            <tr>
                <td>${emp.employee_id}</td>
                <td>${emp.name}</td>
                <td>${emp.email}</td>
                <td>${emp.department}</td>
                <td>${emp.designation}</td>
                <td><span class="badge ${emp.status.toLowerCase()}">${emp.status}</span></td>
                <td>
                    <button onclick="editEmployeePopup(${JSON.stringify(emp).replace(/"/g, '&quot;')})" class="btn-action btn-edit">Edit</button>
                    <button onclick="deleteEmployee(${emp.id})" class="btn-action btn-reject">Delete</button>
                </td>
            </tr>
        `;
    });
}

function filterEmployees() {
    const q = document.getElementById("empSearchInput").value.toLowerCase();
    const filtered = allEmployees.filter(emp => 
        emp.name.toLowerCase().includes(q) || 
        emp.employee_id.toLowerCase().includes(q) || 
        emp.department.toLowerCase().includes(q) || 
        emp.designation.toLowerCase().includes(q)
    );
    renderEmployeesTable(filtered);
}

const addEmployeeForm = document.getElementById("addEmployeeForm");
if (addEmployeeForm) {
    addEmployeeForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        const payload = {
            employee_id: document.getElementById("addEmpId").value,
            name: document.getElementById("addName").value,
            email: document.getElementById("addEmail").value,
            password: document.getElementById("addPassword").value,
            phone_number: document.getElementById("addPhone").value,
            department: document.getElementById("addDept").value,
            designation: document.getElementById("addDesg").value,
            date_of_joining: document.getElementById("addJoinDate").value
        };
        await apiCall("/employees", "POST", payload);
        alert("Employee profile created successfully!");
        closeModal("addEmployeeModal");
        this.reset();
        loadAdminEmployees();
    });
}

async function editEmployeePopup(emp) {
    document.getElementById("editEmpId").value = emp.id;
    document.getElementById("editName").value = emp.name;
    document.getElementById("editEmail").value = emp.email;
    document.getElementById("editPhone").value = emp.phone_number || '';
    document.getElementById("editDept").value = emp.department;
    document.getElementById("editStatus").value = emp.status;
    
    await loadDesignations(emp.designation);
    openModal("editEmployeeModal");
}

const editEmployeeForm = document.getElementById("editEmployeeForm");
if (editEmployeeForm) {
    editEmployeeForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        const empId = document.getElementById("editEmpId").value;
        const payload = {
            name: document.getElementById("editName").value,
            email: document.getElementById("editEmail").value,
            phone_number: document.getElementById("editPhone").value,
            department: document.getElementById("editDept").value,
            designation: document.getElementById("editDesg").value,
            status: document.getElementById("editStatus").value
        };
        await apiCall(`/employees/${empId}`, "PUT", payload);
        alert("Employee record updated successfully!");
        closeModal("editEmployeeModal");
        loadAdminEmployees();
    });
}

async function deleteEmployee(id) {
    if (confirm("Are you sure you want to permanently delete this employee? This will also remove their user account.")) {
        await apiCall(`/employees/${id}`, "DELETE");
        alert("Employee deleted.");
        loadAdminEmployees();
    }
}

// 3. Admin Attendance Register
async function loadAdminAttendance() {
    const records = await apiCall("/attendance");
    const tbody = document.getElementById("attendanceTableBody");
    tbody.innerHTML = "";
    if (records.length === 0) tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;">No attendance logs found.</td></tr>`;
    records.forEach(r => {
        tbody.innerHTML += `
            <tr>
                <td>${r.employee_id}</td>
                <td>${r.name}</td>
                <td>${r.department}</td>
                <td>${r.date}</td>
                <td>${r.check_in || '-'}</td>
                <td>${r.check_out || '-'}</td>
                <td>${r.working_hours ? parseFloat(r.working_hours).toFixed(2) : '0.00'}</td>
                <td><span class="badge ${r.status.toLowerCase()}">${r.status}</span></td>
            </tr>
        `;
    });
}

// 4. Admin Leaves Requests Review
async function loadAdminLeaves() {
    const leaves = await apiCall("/leaves?scope=all");
    const tbody = document.getElementById("leavesTableBody");
    tbody.innerHTML = "";
    if (leaves.length === 0) tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;">No leave applications found.</td></tr>`;
    leaves.forEach(l => {
        const leaveDays = Math.ceil((new Date(l.end_date) - new Date(l.start_date)) / (1000 * 60 * 60 * 24)) + 1;
        const start = new Date(l.start_date).toLocaleDateString();
        const end = new Date(l.end_date).toLocaleDateString();
        
        let actionBtn = "";
        if (l.status === "Pending") {
            actionBtn = `
                <button onclick="reviewLeave(${l.id}, 'Approved')" class="btn-action btn-approve">Approve</button>
                <button onclick="reviewLeave(${l.id}, 'Rejected')" class="btn-action btn-reject">Reject</button>
            `;
        } else {
            actionBtn = `<span style="font-size:12px; color:var(--ink-faint);">Processed</span>`;
        }

        tbody.innerHTML += `
            <tr>
                <td>${l.employee_id}</td>
                <td>${l.name}</td>
                <td>${l.leave_type}</td>
                <td>
                    <div style="font-weight:500;">${leaveDays} Days</div>
                    <div style="font-size:11px; color:var(--ink-faint);">${start} to ${end}</div>
                </td>
                <td style="max-width:180px; word-break:break-all;">${l.reason || '-'}</td>
                <td><span class="badge ${l.status.toLowerCase()}">${l.status}</span></td>
                <td style="font-size:12px; line-height:1.4;">
                    C:${l.casual_leave} | S:${l.sick_leave}<br>
                    E:${l.earned_leave} | Em:${l.emergency_leave}
                </td>
                <td>${actionBtn}</td>
            </tr>
        `;
    });
}

async function reviewLeave(id, action) {
    await apiCall(`/leaves/${id}`, "PUT", { status: action });
    alert(`Leave request ${action.toLowerCase()} successfully.`);
    loadAdminLeaves();
}

// 6. Admin Announcements Panel
async function loadAdminAnnouncements() {
    const list = await apiCall("/announcements");
    const log = document.getElementById("announcementLog");
    log.innerHTML = "";
    if (list.length === 0) log.innerHTML = `<div style="color:var(--ink-faint); font-size:13px;">No announcements published yet.</div>`;
    list.forEach(a => {
        log.innerHTML += `
            <div style="background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:20px; border-radius:16px;">
                <h4 style="font-weight:600; font-size:15px; margin-bottom:6px;">${a.title}</h4>
                <p style="font-size:14px; color:var(--ink-soft); line-height:1.6;">${a.content}</p>
                <div style="font-size:11px; color:var(--ink-faint); margin-top:10px;">Published on ${new Date(a.created_at).toLocaleString()}</div>
            </div>
        `;
    });
}

const announcementForm = document.getElementById("announcementForm");
if (announcementForm) {
    announcementForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        const payload = {
            title: document.getElementById("annTitle").value,
            content: document.getElementById("annContent").value
        };
        await apiCall("/announcements", "POST", payload);
        alert("Board announcement posted successfully!");
        this.reset();
        loadAdminAnnouncements();
    });
}

// 7. Admin Reports Module
async function generateReport(type) {
    const data = await apiCall(`/reports/${type}`);
    const card = document.getElementById("reportOutputCard");
    const title = document.getElementById("reportTitle");
    const container = document.getElementById("reportContainer");

    card.style.display = "block";
    container.innerHTML = "";

    if (type === "attendance") {
        title.innerHTML = "📊 Company Attendance History (Recent 30 Days)";
        let table = `
            <table>
                <thead>
                    <tr><th>Date</th><th>Status Type</th><th>Records Count</th></tr>
                </thead>
                <tbody>
        `;
        data.forEach(r => {
            table += `<tr><td>${r.date}</td><td><span class="badge ${r.status.toLowerCase()}">${r.status}</span></td><td>${r.count} Employees</td></tr>`;
        });
        table += `</tbody></table>`;
        container.innerHTML = table;
    } else if (type === "employee") {
        title.innerHTML = "👥 Active Headcount breakdown by Department";
        let table = `
            <table>
                <thead>
                    <tr><th>Department</th><th>Active Headcount</th></tr>
                </thead>
                <tbody>
        `;
        data.forEach(r => {
            table += `<tr><td>${r.department}</td><td><strong>${r.employee_count}</strong> Employees</td></tr>`;
        });
        table += `</tbody></table>`;
        container.innerHTML = table;
    } else if (type === "recruitment") {
        title.innerHTML = "🎯 Recruitment Funnel — Applications breakdown by Status";
        let table = `
            <table>
                <thead>
                    <tr><th>Application Status</th><th>Total Count</th></tr>
                </thead>
                <tbody>
        `;
        data.forEach(r => {
            table += `<tr><td><span class="badge ${r.status.toLowerCase()}">${r.status}</span></td><td><strong>${r.application_count}</strong> Applications</td></tr>`;
        });
        table += `</tbody></table>`;
        container.innerHTML = table;
    }
}


// === EMPLOYEE PORTAL HANDLERS ===

// 1. Employee Overview
async function loadEmpOverview() {
    const stats = await apiCall("/dashboard/stats");
    document.getElementById("bal_casual").textContent = stats.casual_leave_balance;
    document.getElementById("bal_sick").textContent = stats.sick_leave_balance;
    document.getElementById("bal_earned").textContent = stats.earned_leave_balance;
    document.getElementById("bal_emergency").textContent = stats.emergency_leave_balance;

    const noticeList = document.getElementById("empNoticeList");
    noticeList.innerHTML = "";
    const notices = await apiCall("/announcements");
    if (notices.length === 0) noticeList.innerHTML = `<div style="color:var(--ink-faint); font-size:13px;">No announcements posted.</div>`;
    notices.slice(0, 3).forEach(n => {
        noticeList.innerHTML += `
            <div style="background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:12px; border-radius:10px; margin-bottom:8px;">
                <h5 style="font-weight:600; font-size:13px; margin-bottom:3px;">${n.title}</h5>
                <p style="font-size:12px; color:var(--ink-soft);">${n.content}</p>
            </div>
        `;
    });
    loadEmployeeMeetings();
}

async function markCheckIn() {
    const res = await apiCall("/attendance/checkin", "POST");
    document.getElementById("attendanceTimerStatus").textContent = res.message;
    alert(res.message);
}

async function markCheckOut() {
    const res = await apiCall("/attendance/checkout", "POST");
    document.getElementById("attendanceTimerStatus").textContent = res.message;
    alert(res.message);
}

// 2. Employee Attendance Logs
async function loadEmpAttendance() {
    const records = await apiCall("/attendance");
    const tbody = document.getElementById("empAttendanceTableBody");
    tbody.innerHTML = "";
    if (records.length === 0) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;">No attendance records registered.</td></tr>`;
    records.forEach(r => {
        tbody.innerHTML += `
            <tr>
                <td>${r.date}</td>
                <td>${r.check_in || '-'}</td>
                <td>${r.check_out || '-'}</td>
                <td>${r.working_hours ? parseFloat(r.working_hours).toFixed(2) : '0.00'} hours</td>
                <td><span class="badge ${r.status.toLowerCase()}">${r.status}</span></td>
            </tr>
        `;
    });
}

// 3. Employee Leave Applying
async function loadEmpLeaves() {
    const records = await apiCall("/leaves");
    const tbody = document.getElementById("empLeavesTableBody");
    tbody.innerHTML = "";
    if (records.length === 0) tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;">No leave applications submitted.</td></tr>`;
    records.forEach(l => {
        const leaveDays = Math.ceil((new Date(l.end_date) - new Date(l.start_date)) / (1000 * 60 * 60 * 24)) + 1;
        tbody.innerHTML += `
            <tr>
                <td>${l.leave_type}</td>
                <td>
                    <div style="font-weight:500;">${leaveDays} Days</div>
                    <div style="font-size:11px; color:var(--ink-faint);">${new Date(l.start_date).toLocaleDateString()} to ${new Date(l.end_date).toLocaleDateString()}</div>
                </td>
                <td>${l.reason || '-'}</td>
                <td><span class="badge ${l.status.toLowerCase()}">${l.status}</span></td>
            </tr>
        `;
    });
}

const applyLeaveForm = document.getElementById("applyLeaveForm");
if (applyLeaveForm) {
    applyLeaveForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        const payload = {
            leave_type: document.getElementById("leaveType").value,
            start_date: document.getElementById("leaveStart").value,
            end_date: document.getElementById("leaveEnd").value,
            reason: document.getElementById("leaveReason").value
        };
        await apiCall("/leaves", "POST", payload);
        alert("Leave application submitted successfully for review!");
        this.reset();
        loadEmpLeaves();
        loadEmpOverview(); // refresh leave balances
    });
}

// 4. Employee Announcements Log
async function loadEmpAnnouncements() {
    const list = await apiCall("/announcements");
    const container = document.getElementById("empAnnouncementBoard");
    container.innerHTML = "";
    if (list.length === 0) container.innerHTML = `<div style="color:var(--ink-faint); font-size:13px;">No announcements posted.</div>`;
    list.forEach(a => {
        container.innerHTML += `
            <div style="background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:20px; border-radius:16px;">
                <h4 style="font-weight:600; font-size:15px; margin-bottom:6px;">${a.title}</h4>
                <p style="font-size:14px; color:var(--ink-soft); line-height:1.6;">${a.content}</p>
                <div style="font-size:11px; color:var(--ink-faint); margin-top:10px;">Posted on ${new Date(a.created_at).toLocaleString()}</div>
            </div>
        `;
    });
}


// === PROFILE HANDLERS (Shared) ===
async function loadProfile() {
    const prof = await apiCall("/profile");
    document.getElementById("profName").value = prof.name;
    document.getElementById("profEmail").value = prof.email;
    document.getElementById("profPassword").value = "";

    document.getElementById("profEmpIdField").style.display = "none";
    document.getElementById("profDeptField").style.display = "none";
    document.getElementById("profDesgField").style.display = "none";
    document.getElementById("profPhoneField").style.display = "none";

    if (user.role === "employee") {
        document.getElementById("profEmpIdField").style.display = "block";
        document.getElementById("profDeptField").style.display = "block";
        document.getElementById("profDesgField").style.display = "block";
        document.getElementById("profPhoneField").style.display = "block";

        document.getElementById("profEmpId").value = prof.employee_id;
        document.getElementById("profDept").value = prof.department;
        document.getElementById("profDesg").value = prof.designation;
        document.getElementById("profPhone").value = prof.phone_number || "";
    } else if (user.role === "client") {
        document.getElementById("profPhoneField").style.display = "block";
        document.getElementById("profPhone").value = prof.phone_number || "";
    }
}

const profileForm = document.getElementById("profileForm");
if (profileForm) {
    profileForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        const payload = {
            name: document.getElementById("profName").value,
            email: document.getElementById("profEmail").value
        };
        const phone = document.getElementById("profPhone").value;
        const pwd = document.getElementById("profPassword").value;
        
        if (phone) payload.phone_number = phone;
        if (pwd) payload.password = pwd;

        await apiCall("/profile", "PUT", payload);
        alert("Profile settings saved successfully!");
        
        user.name = payload.name;
        user.email = payload.email;
        localStorage.setItem("user", JSON.stringify(user));
        document.getElementById("userGreeting").textContent = `Hello, ${user.name} (${user.role.toUpperCase()})`;
        loadProfile();
    });
}


// === CANDIDATE PORTAL HANDLERS ===
async function loadCandidateOverview() {
    const apps = await apiCall("/applications");
    const tbody = document.getElementById("candApplicationsTableBody");
    tbody.innerHTML = "";
    if (apps.length === 0) tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;">You have not applied for any positions yet. <a href="openings.html" style="color:var(--blue);">Browse Careers</a></td></tr>`;
    apps.forEach(a => {
        tbody.innerHTML += `
            <tr>
                <td><strong>${a.job_title}</strong></td>
                <td>${a.job_department}</td>
                <td>${new Date(a.applied_at).toLocaleDateString()}</td>
                <td><span class="badge ${a.status.toLowerCase()}">${a.status}</span></td>
            </tr>
        `;
    });
}

// --- Contacts Tab Controller ---
async function loadAdminContacts() {
    try {
        const edutechBody = document.getElementById("edutechContactsTableBody");
        const elevateBody = document.getElementById("elevateContactsTableBody");

        edutechBody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--ink-soft);">Loading submissions...</td></tr>`;
        const edutechData = await apiCall("/admin/contacts/edutech");
        edutechBody.innerHTML = "";
        if (edutechData.length === 0) {
            edutechBody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--ink-faint);">No EduTech inquiries found.</td></tr>`;
        } else {
            edutechData.forEach(c => {
                const dateStr = new Date(c.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
                edutechBody.innerHTML += `
                    <tr>
                        <td style="white-space: nowrap;">${dateStr}</td>
                        <td style="font-weight: 600;">${escapeHTML(c.name)}</td>
                        <td><a href="mailto:${c.email}" style="color: var(--orange);">${escapeHTML(c.email)}</a></td>
                        <td><a href="tel:${c.phone}" style="color: var(--blue);">${escapeHTML(c.phone)}</a></td>
                        <td style="color: var(--pink-light); font-weight: 500;">${escapeHTML(c.track)}</td>
                        <td style="max-width: 300px; word-break: break-word;">${escapeHTML(c.message)}</td>
                    </tr>
                `;
            });
        }

        elevateBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--ink-soft);">Loading messages...</td></tr>`;
        const elevateData = await apiCall("/admin/contacts/elevate");
        elevateBody.innerHTML = "";
        if (elevateData.length === 0) {
            elevateBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--ink-faint);">No messages from main site.</td></tr>`;
        } else {
            elevateData.forEach(c => {
                const dateStr = new Date(c.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
                elevateBody.innerHTML += `
                    <tr>
                        <td style="white-space: nowrap;">${dateStr}</td>
                        <td style="font-weight: 600;">${escapeHTML(c.name)}</td>
                        <td><a href="mailto:${c.email}" style="color: var(--orange);">${escapeHTML(c.email)}</a></td>
                        <td style="max-width: 400px; word-break: break-word;">${escapeHTML(c.message)}</td>
                    </tr>
                `;
            });
        }
    } catch (e) {
        console.error(e);
    }
}

function switchContactTab(type) {
    const btnEdu = document.getElementById("btnEduTechContacts");
    const btnElv = document.getElementById("btnElevateContacts");
    const secEdu = document.getElementById("edutechContactsSection");
    const secElv = document.getElementById("elevateContactsSection");

    if (type === 'edutech') {
        secEdu.style.display = "block";
        secElv.style.display = "none";
        
        btnEdu.className = "btn-primary";
        btnEdu.style.background = "var(--orange)";
        btnEdu.style.color = "#ffffff";
        
        btnElv.className = "btn-login";
        btnElv.style.background = "transparent";
        btnElv.style.color = "var(--ink-soft)";
    } else {
        secEdu.style.display = "none";
        secElv.style.display = "block";
        
        btnEdu.className = "btn-login";
        btnEdu.style.background = "transparent";
        btnEdu.style.color = "var(--ink-soft)";
        
        btnElv.className = "btn-primary";
        btnElv.style.background = "var(--orange)";
        btnElv.style.color = "#ffffff";
    }
}
