/**
 * @file leaves.js
 * @description Central dashboard sub-controller managing Admin Overview stats, employee CRUD operations,
 * attendance registries, leave application approvals, notice boards, report engines, and candidate application tracking.
 */

/* ==========================================================================
   1. ADMIN OVERVIEW CONTROLLER
   ========================================================================== */

/**
 * Loads dashboard overview metrics and company notice board announcements.
 * 
 * @async
 */
async function loadAdminOverview() {
    const [stats, notices] = await Promise.all([
        apiCall("/dashboard/stats"),
        apiCall("/announcements")
    ]);
    if (document.getElementById("stat_total_emp")) document.getElementById("stat_total_emp").textContent = stats.active_employees;
    if (document.getElementById("stat_emp_shift_sub")) document.getElementById("stat_emp_shift_sub").textContent = `${stats.day_total || 0} Day | ${stats.night_total || 0} Night`;

    // Day Shift Present / Absent / Total
    if (document.getElementById("stat_day_present")) document.getElementById("stat_day_present").textContent = stats.day_present ?? 0;
    if (document.getElementById("stat_day_absent")) document.getElementById("stat_day_absent").textContent = stats.day_absent ?? 0;
    if (document.getElementById("stat_day_total")) document.getElementById("stat_day_total").textContent = stats.day_total ?? 0;

    // Night Shift Present / Absent / Total
    if (document.getElementById("stat_night_present")) document.getElementById("stat_night_present").textContent = stats.night_present ?? 0;
    if (document.getElementById("stat_night_absent")) document.getElementById("stat_night_absent").textContent = stats.night_absent ?? 0;
    if (document.getElementById("stat_night_total")) document.getElementById("stat_night_total").textContent = stats.night_total ?? 0;

    // General fallback
    if (document.getElementById("stat_present")) document.getElementById("stat_present").textContent = stats.present_today;
    if (document.getElementById("stat_absent")) document.getElementById("stat_absent").textContent = stats.absent_today;

    if (document.getElementById("stat_pending_leaves")) document.getElementById("stat_pending_leaves").textContent = stats.pending_leaves;
    if (document.getElementById("stat_open_jobs")) document.getElementById("stat_open_jobs").textContent = stats.active_jobs;
    if (document.getElementById("stat_total_apps")) document.getElementById("stat_total_apps").textContent = stats.total_applications;

    const noticeList = document.getElementById("adminNoticeList");
    noticeList.innerHTML = "";
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


/* ==========================================================================
   2. ADMIN EMPLOYEES MANAGEMENT
   ========================================================================== */

let allEmployees = [];

/**
 * Fetches company designations list and populates add/edit dropdown selectors.
 * 
 * @async
 * @param {string|null} [selectedVal=null] - Pre-selected designation name.
 */
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

/**
 * Toggles the designation selector interface between dropdown and custom input modes.
 * 
 * @param {string} mode - Mode key identifier ('add' or 'edit').
 * @param {boolean} showInput - Whether to show the text input.
 */
function toggleDesgInput(mode, showInput) {
    const selectArea = document.getElementById(`${mode}DesgSelectArea`);
    const inputArea = document.getElementById(`${mode}DesgInputArea`);
    const selectElem = document.getElementById(`${mode}Desg`);
    const customInput = document.getElementById(`${mode}DesgCustom`);
    
    if (showInput) {
        if (selectArea) selectArea.style.display = "none";
        if (inputArea) inputArea.style.display = "flex";
        if (selectElem) selectElem.required = false;
        if (customInput) {
            customInput.required = true;
            customInput.value = "";
            customInput.focus();
        }
    } else {
        if (selectArea) selectArea.style.display = "flex";
        if (inputArea) inputArea.style.display = "none";
        if (selectElem) selectElem.required = true;
        if (customInput) customInput.required = false;
    }
}

/**
 * Dispatches a POST request to add a new custom designation.
 * 
 * @async
 * @param {string} mode - 'add' or 'edit' context marker.
 */
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

/**
 * Loads employee database roster list and updates table.
 * 
 * @async
 */
let currentEmpShiftFilter = "All";

/**
 * Loads employee database roster list and updates table.
 * 
 * @async
 */
async function loadAdminEmployees() {
    await loadDesignations();
    allEmployees = await apiCall("/employees?portal=elevateiq");
    updateEmployeeShiftCounts();
    filterEmployeesBySearchAndShift();
}

function updateEmployeeShiftCounts() {
    const total = allEmployees.length;
    const day = allEmployees.filter(e => (e.shift || "Day Shift") === "Day Shift").length;
    const night = allEmployees.filter(e => (e.shift || "Day Shift") === "Night Shift").length;

    if (document.getElementById("cntEmpAll")) document.getElementById("cntEmpAll").textContent = total;
    if (document.getElementById("cntEmpDay")) document.getElementById("cntEmpDay").textContent = day;
    if (document.getElementById("cntEmpNight")) document.getElementById("cntEmpNight").textContent = night;
}

function filterEmployeesByShift(shift, btn) {
    currentEmpShiftFilter = shift;
    document.querySelectorAll(".btn-emp-shift-filter").forEach(b => {
        b.style.background = "transparent";
        b.style.color = "var(--ink-soft)";
    });
    if (btn) {
        btn.style.background = "var(--blue)";
        btn.style.color = "white";
    }
    filterEmployeesBySearchAndShift();
}

function filterEmployeesBySearchAndShift() {
    const qElem = document.getElementById("empSearchInput");
    const q = qElem ? qElem.value.toLowerCase() : "";
    let filtered = allEmployees;

    if (currentEmpShiftFilter !== "All") {
        filtered = filtered.filter(emp => (emp.shift || "Day Shift").toLowerCase() === currentEmpShiftFilter.toLowerCase());
    }

    if (q) {
        filtered = filtered.filter(emp => 
            (emp.name || "").toLowerCase().includes(q) || 
            (emp.employee_id || "").toLowerCase().includes(q) || 
            (emp.department || "").toLowerCase().includes(q) || 
            (emp.designation || "").toLowerCase().includes(q) ||
            (emp.email || "").toLowerCase().includes(q)
        );
    }

    renderEmployeesTable(filtered);
}

/**
 * Generates table row templates for employee accounts.
 * 
 * @param {Array<Object>} list - Employees list.
 */
function renderEmployeesTable(list) {
    const tbody = document.getElementById("employeesTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;">No employee records found.</td></tr>`;
        return;
    }

    list.forEach(emp => {
        const empShift = emp.shift || "Day Shift";
        const isNight = empShift === "Night Shift";
        const shiftBadge = isNight 
            ? `<span style="background:rgba(139,92,246,0.15); color:#c084fc; border:1px solid rgba(139,92,246,0.3); padding:3px 8px; border-radius:6px; font-size:11.5px; font-weight:600; display:inline-flex; align-items:center; gap:4px;">🌙 Night</span>`
            : `<span style="background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.3); padding:3px 8px; border-radius:6px; font-size:11.5px; font-weight:600; display:inline-flex; align-items:center; gap:4px;">☀️ Day</span>`;

        tbody.innerHTML += `
            <tr>
                <td style="font-weight:600;">${emp.employee_id}</td>
                <td>${emp.name}</td>
                <td>${shiftBadge}</td>
                <td>${emp.email}</td>
                <td>${emp.department || 'General'}</td>
                <td>${emp.designation || '-'}</td>
                <td><span class="badge ${emp.status ? emp.status.toLowerCase() : 'active'}">${emp.status || 'Active'}</span></td>
                <td style="white-space: nowrap;">
                    <div style="display: flex; gap: 6px; align-items: center;">
                        <button onclick="viewEmployeeDetails(${JSON.stringify(emp).replace(/"/g, '&quot;')})" class="btn-action btn-approve" style="background: rgba(75, 255, 120, 0.15); color: #99ffaa; border: 1px solid rgba(75, 255, 120, 0.3); margin: 0;">View</button>
                        <button onclick="editEmployeePopup(${JSON.stringify(emp).replace(/"/g, '&quot;')})" class="btn-action btn-edit" style="margin: 0;">Edit</button>
                        <button onclick="deleteEmployee(${emp.id})" class="btn-action btn-reject" style="margin: 0;">Delete</button>
                    </div>
                </td>
            </tr>
        `;
    });
}

/**
 * Opens a detailed view modal displaying complete employee record file.
 * 
 * @param {Object} emp - The employee record object.
 */
function viewEmployeeDetails(emp) {
    document.getElementById("viewEmpId").textContent = emp.employee_id || "-";
    document.getElementById("viewEmpName").textContent = emp.name || "-";
    document.getElementById("viewEmpEmail").textContent = emp.email || "-";
    document.getElementById("viewEmpPhone").textContent = emp.phone_number || "Not provided";
    document.getElementById("viewEmpJoinDate").textContent = emp.date_of_joining || "Not provided";
    document.getElementById("viewEmpDept").textContent = emp.department || "-";
    document.getElementById("viewEmpDesg").textContent = emp.designation || "-";
    if (document.getElementById("viewEmpShift")) {
        const empShift = emp.shift || "Day Shift";
        document.getElementById("viewEmpShift").textContent = empShift === "Night Shift" ? "🌙 Night Shift" : "☀️ Day Shift";
        document.getElementById("viewEmpShift").style.color = empShift === "Night Shift" ? "#c084fc" : "#60a5fa";
    }
    
    // Status badge formatting
    const statusSpan = document.getElementById("viewEmpStatus");
    statusSpan.textContent = emp.status || "Active";
    statusSpan.className = `badge ${emp.status ? emp.status.toLowerCase() : "active"}`;
    
    // Leave balances
    document.getElementById("viewEmpCasual").textContent = emp.casual_leave !== undefined ? emp.casual_leave : "0";
    document.getElementById("viewEmpSick").textContent = emp.sick_leave !== undefined ? emp.sick_leave : "0";
    document.getElementById("viewEmpEarned").textContent = emp.earned_leave !== undefined ? emp.earned_leave : "0";
    document.getElementById("viewEmpEmergency").textContent = emp.emergency_leave !== undefined ? emp.emergency_leave : "0";
    
    openModal("viewEmployeeModal");
    
    // Initialize Lucide icons if any inside the modal
    if (window.lucide) {
        lucide.createIcons();
    }
}

/**
 * Filters employee management list depending on search query matching terms.
 */
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

// Add Employee submission form handler
const addEmployeeForm = document.getElementById("addEmployeeForm");
if (addEmployeeForm) {
    addEmployeeForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        try {
            const payload = {
                employee_id: document.getElementById("addEmpId").value,
                name: document.getElementById("addName").value,
                email: document.getElementById("addEmail").value,
                password: document.getElementById("addPassword").value,
                phone_number: document.getElementById("addPhone").value,
                department: document.getElementById("addDept").value,
                designation: document.getElementById("addDesg").value,
                shift: document.getElementById("addShift") ? document.getElementById("addShift").value : "Day Shift",
                date_of_joining: document.getElementById("addJoinDate").value
            };
            const res = await apiCall("/employees", "POST", payload);
            alert((res && res.message) ? res.message : "Employee profile created successfully!");
            closeModal("addEmployeeModal");
            this.reset();
            loadAdminEmployees();
        } catch(err) {
            alert(err.message || "Failed to create employee.");
        }
    });
}

/**
 * Populates employee modification form with active details.
 * 
 * @async
 * @param {Object} emp - Target employee account.
 */
async function editEmployeePopup(emp) {
    document.getElementById("editEmpId").value = emp.id;
    document.getElementById("editName").value = emp.name;
    document.getElementById("editEmail").value = emp.email;
    document.getElementById("editPhone").value = emp.phone_number || '';
    document.getElementById("editDept").value = emp.department;
    if (document.getElementById("editShift")) {
        document.getElementById("editShift").value = emp.shift || "Day Shift";
    }
    document.getElementById("editStatus").value = emp.status;
    
    await loadDesignations(emp.designation);
    openModal("editEmployeeModal");
}

// Save modified employee details form handler
const editEmployeeForm = document.getElementById("editEmployeeForm");
if (editEmployeeForm) {
    editEmployeeForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        try {
            const empId = document.getElementById("editEmpId").value;
            const payload = {
                name: document.getElementById("editName").value,
                email: document.getElementById("editEmail").value,
                phone_number: document.getElementById("editPhone").value,
                department: document.getElementById("editDept").value,
                designation: document.getElementById("editDesg").value,
                shift: document.getElementById("editShift") ? document.getElementById("editShift").value : "Day Shift",
                status: document.getElementById("editStatus").value
            };
            const res = await apiCall(`/employees/${empId}`, "PUT", payload);
            alert((res && res.message) ? res.message : "Employee record updated successfully!");
            closeModal("editEmployeeModal");
            loadAdminEmployees();
        } catch(err) {
            alert(err.message || "Failed to update employee.");
        }
    });
}

/**
 * Dispatches a delete request to terminate an employee account and profile.
 * 
 * @async
 * @param {number} id - Target employee database primary key ID.
 */
async function deleteEmployee(id) {
    if (confirm("Are you sure you want to permanently delete this employee? This will also remove their user account.")) {
        await apiCall(`/employees/${id}`, "DELETE");
        alert("Employee deleted.");
        loadAdminEmployees();
    }
}


/* ==========================================================================
   3. ADMIN ATTENDANCE REGISTER
   ========================================================================== */

let allAttendanceRecords = [];
let currentShiftFilter = "All";
let currentAttStatusFilter = "All";
let currentAttSelectedDate = new Date().toISOString().split("T")[0];

/**
 * Loads daily attendance logs and updates registry table.
 * 
 * @async
 */
async function loadAdminAttendance(targetDate = null) {
    if (targetDate) {
        currentAttSelectedDate = targetDate;
    } else if (!currentAttSelectedDate) {
        currentAttSelectedDate = new Date().toISOString().split("T")[0];
    }

    const dateInput = document.getElementById("attReportDate");
    if (dateInput) dateInput.value = currentAttSelectedDate;

    const lblDate = document.getElementById("lblAttReportDate");
    if (lblDate) {
        const todayStr = new Date().toISOString().split("T")[0];
        lblDate.textContent = currentAttSelectedDate === todayStr ? `Today (${currentAttSelectedDate})` : currentAttSelectedDate;
    }

    allAttendanceRecords = await apiCall(`/attendance?date=${currentAttSelectedDate}`);
    updateAttendanceSummaryCards();
    renderAttendanceReportTable();
}

function changeAttendanceReportDate(dateVal) {
    if (!dateVal) return;
    loadAdminAttendance(dateVal);
}

function setAttendancePresetDate(preset) {
    const d = new Date();
    if (preset === 'yesterday') {
        d.setDate(d.getDate() - 1);
    }
    const dateStr = d.toISOString().split("T")[0];
    loadAdminAttendance(dateStr);
}

function updateAttendanceSummaryCards() {
    let recordsForShift = allAttendanceRecords;
    if (currentShiftFilter !== "All") {
        recordsForShift = allAttendanceRecords.filter(r => (r.shift || "Day Shift").toLowerCase() === currentShiftFilter.toLowerCase());
    }

    const total = recordsForShift.length;
    const presenties = recordsForShift.filter(r => r.status === "Present" || r.status === "Half Day").length;
    const absenties = recordsForShift.filter(r => r.status === "Absent" || r.status === "Leave").length;

    const dayPresent = allAttendanceRecords.filter(r => (r.shift || "Day Shift") === "Day Shift" && (r.status === "Present" || r.status === "Half Day")).length;
    const nightPresent = allAttendanceRecords.filter(r => (r.shift || "Day Shift") === "Night Shift" && (r.status === "Present" || r.status === "Half Day")).length;

    const rate = total > 0 ? ((presenties / total) * 100).toFixed(1) + "%" : "0%";

    if (document.getElementById("stat_att_total")) document.getElementById("stat_att_total").textContent = total;
    if (document.getElementById("stat_att_present")) document.getElementById("stat_att_present").textContent = presenties;
    if (document.getElementById("stat_att_absent")) document.getElementById("stat_att_absent").textContent = absenties;
    if (document.getElementById("stat_att_rate")) document.getElementById("stat_att_rate").textContent = rate;
    if (document.getElementById("stat_att_shift_breakdown")) document.getElementById("stat_att_shift_breakdown").textContent = `☀️ ${dayPresent} Day | 🌙 ${nightPresent} Night`;

    if (document.getElementById("cntAttAll")) document.getElementById("cntAttAll").textContent = total;
    if (document.getElementById("cntAttPresent")) document.getElementById("cntAttPresent").textContent = presenties;
    if (document.getElementById("cntAttAbsent")) document.getElementById("cntAttAbsent").textContent = absenties;
}

function filterAttendanceByStatus(status, btn) {
    currentAttStatusFilter = status;
    document.querySelectorAll(".btn-att-status-filter").forEach(b => {
        b.style.background = "transparent";
        b.style.color = "var(--ink-soft)";
    });
    if (btn) {
        btn.style.background = "var(--blue)";
        btn.style.color = "white";
    }
    renderAttendanceReportTable();
}

function filterAttendanceByShift(shift, btn) {
    currentShiftFilter = shift;
    document.querySelectorAll(".btn-shift-filter").forEach(b => {
        b.style.background = "transparent";
        b.style.color = "var(--ink-soft)";
    });
    if (btn) {
        btn.style.background = "var(--blue)";
        btn.style.color = "white";
    }
    updateAttendanceSummaryCards();
    renderAttendanceReportTable();
}

function renderAttendanceReportTable() {
    const tbody = document.getElementById("attendanceTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    let filtered = allAttendanceRecords;

    if (currentAttStatusFilter === "Present") {
        filtered = filtered.filter(r => r.status === "Present" || r.status === "Half Day");
    } else if (currentAttStatusFilter === "Absent") {
        filtered = filtered.filter(r => r.status === "Absent" || r.status === "Leave");
    }

    if (currentShiftFilter !== "All") {
        filtered = filtered.filter(r => (r.shift || "Day Shift").toLowerCase() === currentShiftFilter.toLowerCase());
    }

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;">No ${currentAttStatusFilter !== 'All' ? currentAttStatusFilter : ''} attendance records found for selected filters.</td></tr>`;
        return;
    }

    filtered.forEach(r => {
        const isNight = (r.shift || "Day Shift").toLowerCase() === "night shift";
        const shiftBadge = isNight 
            ? `<span style="background:rgba(139,92,246,0.15); color:#c084fc; border:1px solid rgba(139,92,246,0.3); padding:3px 8px; border-radius:6px; font-size:11.5px; font-weight:600; display:inline-flex; align-items:center; gap:4px;">🌙 Night</span>`
            : `<span style="background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.3); padding:3px 8px; border-radius:6px; font-size:11.5px; font-weight:600; display:inline-flex; align-items:center; gap:4px;">☀️ Day</span>`;

        let statusBadge = `<span class="badge ${r.status.toLowerCase()}">${r.status}</span>`;
        if (r.status === "Absent") {
            statusBadge = `<span style="background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.3); padding:4px 10px; border-radius:8px; font-size:12px; font-weight:700;">ABSENT</span>`;
        } else if (r.status === "Present") {
            statusBadge = `<span style="background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.3); padding:4px 10px; border-radius:8px; font-size:12px; font-weight:700;">PRESENT</span>`;
        }

        tbody.innerHTML += `
            <tr>
                <td style="font-weight:600;">${r.employee_id || r.employee_code || '-'}</td>
                <td>${r.name}</td>
                <td>${shiftBadge}</td>
                <td>${r.department || 'General'}</td>
                <td>${r.date}</td>
                <td>${r.check_in || '-'}</td>
                <td>${r.check_out || '-'}</td>
                <td>${r.working_hours ? parseFloat(r.working_hours).toFixed(2) : '0.00'}</td>
                <td>${statusBadge}</td>
            </tr>
        `;
    });
}


/* ==========================================================================
   4. ADMIN LEAVES REQUESTS REVIEW
   ========================================================================== */

/**
 * Fetches pending and processed leave request records and renders reviews table.
 * 
 * @async
 */
function getStatusBadgeHtml(status) {
    let text = status || "Pending";
    let style = "background:rgba(255,145,0,0.12); color:#ff9100; border:1px solid rgba(255,145,0,0.3);";
    
    const sLower = text.toLowerCase();
    if (sLower.includes("approved")) {
        style = "background:rgba(34,197,94,0.12); color:#22c55e; border:1px solid rgba(34,197,94,0.3);";
        if (sLower === "approved") text = "Approved by Admin";
    } else if (sLower.includes("rejected")) {
        style = "background:rgba(239,68,68,0.12); color:#ef4444; border:1px solid rgba(239,68,68,0.3);";
    } else if (sLower.includes("withdrawn")) {
        style = "background:rgba(112,122,138,0.12); color:#707a8a; border:1px solid rgba(112,122,138,0.3);";
        text = "Withdrawn";
    } else if (sLower.includes("pending hr")) {
        style = "background:rgba(0,176,255,0.12); color:#00b0ff; border:1px solid rgba(0,176,255,0.3);";
        text = "Pending HR Approval";
    } else if (sLower.includes("pending tl") || sLower === "pending") {
        style = "background:rgba(255,145,0,0.12); color:#ff9100; border:1px solid rgba(255,145,0,0.3);";
        text = "Pending TL Approval";
    }
    
    return `<span class="badge" style="padding:4px 10px; border-radius:8px; font-weight:600; font-size:12px; display:inline-block; text-transform:none; ${style}">${text}</span>`;
}

/**
 * Loads admin leaves requests history.
 * 
 * @async
 */
async function loadAdminLeaves() {
    const leaves = await apiCall("/leaves?scope=all");
    const tbody = document.getElementById("adminLeavesTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (leaves.length === 0) tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:15px; color:var(--ink-faint);">No leave requests found.</td></tr>`;
    
    const isTl = currentUser.designation && (currentUser.designation.toLowerCase().includes("team leader") || currentUser.designation.toLowerCase().includes("team lead"));
    const isHrOrAdmin = currentUser.role === 'admin' || (currentUser.designation && (currentUser.designation.toLowerCase().includes("hr") || currentUser.designation.toLowerCase().includes("human resource")));

    leaves.forEach(l => {
        // Parse dates as explicit UTC midnight to avoid local timezone offset skewing the diff
        function parseUTCDate(str) {
            if (!str) return new Date(0);
            const parts = str.split('-').map(Number);
            return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
        }
        const start = parseUTCDate(l.start_date).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' });
        const end = parseUTCDate(l.end_date).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' });
        const leaveDays = Math.round((parseUTCDate(l.end_date) - parseUTCDate(l.start_date)) / 86400000) + 1;

        let actionBtn = "";
        const isPending = l.status.toLowerCase().includes("pending");

        if (isPending) {
            if (currentUser.role === 'admin') {
                actionBtn = `
                    <div style="display:flex; gap:6px;">
                        <button onclick="reviewLeave(${l.id}, 'Approved')" class="btn-action btn-approve" style="padding:4px 8px; font-size:11px; margin:0;">Approve</button>
                        <button onclick="reviewLeave(${l.id}, 'Rejected')" class="btn-action btn-reject" style="padding:4px 8px; font-size:11px; margin:0;">Reject</button>
                    </div>
                `;
            } else if (l.status === "Pending TL Approval" && (isTl || isHrOrAdmin)) {
                actionBtn = `
                    <div style="display:flex; gap:6px;">
                        <button onclick="reviewLeave(${l.id}, 'Approved')" class="btn-action btn-approve" style="padding:4px 8px; font-size:11px; margin:0;">Approve</button>
                        <button onclick="reviewLeave(${l.id}, 'Rejected')" class="btn-action btn-reject" style="padding:4px 8px; font-size:11px; margin:0;">Reject</button>
                    </div>
                `;
            } else if (l.status === "Pending HR Approval" && isHrOrAdmin) {
                actionBtn = `
                    <div style="display:flex; gap:6px;">
                        <button onclick="reviewLeave(${l.id}, 'Approved')" class="btn-action btn-approve" style="padding:4px 8px; font-size:11px; margin:0;">Approve</button>
                        <button onclick="reviewLeave(${l.id}, 'Rejected')" class="btn-action btn-reject" style="padding:4px 8px; font-size:11px; margin:0;">Reject</button>
                    </div>
                `;
            } else {
                actionBtn = `<span style="font-size:12px; color:#00b0ff; font-weight:600;">Awaiting HR</span>`;
            }
        } else {
            actionBtn = `<span style="font-size:12px; color:var(--ink-faint);">Processed</span>`;
        }

        tbody.innerHTML += `
            <tr id="leave_row_${l.id}">
                <td>${l.employee_id}</td>
                <td>${l.name}</td>
                <td>${l.leave_type}</td>
                <td>
                    <div style="font-weight:500;">${leaveDays} Days</div>
                    <div style="font-size:11px; color:var(--ink-faint);">${start} to ${end}</div>
                </td>
                <td style="max-width:180px; word-break:break-all;">${l.reason || '-'}</td>
                <td class="leave-status-cell">${getStatusBadgeHtml(l.status)}</td>
                <td class="leave-actions-cell">${actionBtn}</td>
            </tr>
        `;
    });
}

/**
 * Dispatches leave application review decision POST updates without reloading the page.
 * 
 * @async
 * @param {number} id - Target leave ID.
 * @param {string} action - Action status decision ('Approved' or 'Rejected').
 */
async function reviewLeave(id, action) {
    try {
        const res = await apiCall(`/leaves/${id}`, "PUT", { status: action });
        const newStatus = res.new_status || (action === "Approved" ? "Approved by Admin" : "Rejected by Admin");
        
        // Instant Real-time UI Update without reloading!
        const row = document.getElementById(`leave_row_${id}`);
        if (row) {
            const statusCell = row.querySelector(".leave-status-cell");
            const actionCell = row.querySelector(".leave-actions-cell");
            if (statusCell) statusCell.innerHTML = getStatusBadgeHtml(newStatus);
            if (actionCell) actionCell.innerHTML = `<span style="font-size:12px; color:var(--ink-faint);">Processed</span>`;
        }

        // Push real-time notification toast
        if (typeof addNotification === 'function') {
            addNotification({
                icon: action === 'Approved' ? '✅' : '❌',
                title: 'Leave Decision Updated',
                message: `Leave request #${id} marked as ${newStatus}`,
                category: 'leave',
                targetView: 'leaves'
            });
        }

        // Refresh stats quietly in background
        if (typeof loadAdminOverview === 'function') loadAdminOverview();
    } catch(err) {
        alert("Failed to review leave: " + err.message);
    }
}


/* ==========================================================================
   6. ADMIN ANNOUNCEMENTS PANEL
   ========================================================================== */

/**
 * Loads published announcements history logs.
 * 
 * @async
 */
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

// Notice Board announcement publish form handler
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


/* ==========================================================================
   7. ADMIN REPORTS MODULE
   ========================================================================== */

/**
 * Triggers backend reporting queries and structures output results.
 * 
 * @async
 * @param {string} type - Report category key ('attendance', 'employee', or 'recruitment').
 */
let reportChartInstances = {};
let currentActiveReportType = null;

async function generateReport(type, forcePrintColors = false) {
    currentActiveReportType = type;
    const data = await apiCall(`/reports/${type}`);
    const card = document.getElementById("reportOutputCard");
    const title = document.getElementById("reportTitle");
    const container = document.getElementById("reportContainer");

    card.style.display = "block";
    container.innerHTML = "";

    // Set Print-only header metadata
    const reportTitleText = type === "attendance" ? "Attendance Audit Report" : 
                            type === "employee" ? "Department Breakdown Report" : "Recruitment Funnel Report";
    document.getElementById("printReportName").textContent = reportTitleText;
    document.getElementById("printReportDate").textContent = "Generated: " + new Date().toLocaleDateString(undefined, { 
        year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' 
    });

    // Reset previous charts
    if (reportChartInstances.chart1) {
        reportChartInstances.chart1.destroy();
    }
    if (reportChartInstances.chart2) {
        reportChartInstances.chart2.destroy();
    }

    const ctx1 = document.getElementById("reportChart1").getContext("2d");
    const ctx2 = document.getElementById("reportChart2").getContext("2d");

    const isPrintMode = forcePrintColors || window.matchMedia('print').matches;

    // Colors matching style.css theme
    const colors = {
        present: "#22C55E",
        halfDay: "#FF8A3D",
        absent: "#EC2F7B",
        leave: "#3FD0FF",
        blue: "#3FD0FF",
        orange: "#FF8A3D",
        pink: "#EC2F7B",
        border: isPrintMode ? "#d3d3d3" : "rgba(255, 255, 255, 0.12)",
        text: isPrintMode ? "#000000" : "#EAF2FF",
        grid: isPrintMode ? "rgba(0, 0, 0, 0.08)" : "rgba(255, 255, 255, 0.05)"
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: colors.text,
                    font: { family: 'Poppins', size: 11 }
                }
            },
            tooltip: {
                backgroundColor: "rgba(10, 15, 30, 0.95)",
                titleColor: "#fff",
                bodyColor: "#fff",
                borderColor: "rgba(255,255,255,0.12)",
                borderWidth: 1
            }
        }
    };

    if (type === "attendance") {
        title.innerHTML = "📊 Company Attendance History (Recent 30 Days)";
        
        // Group data by date
        const dateGroups = {};
        data.forEach(r => {
            if (!dateGroups[r.date]) {
                dateGroups[r.date] = { Present: 0, "Half Day": 0, Absent: 0, Leave: 0 };
            }
            dateGroups[r.date][r.status] = r.count;
        });

        // Sort dates chronologically
        const sortedDates = Object.keys(dateGroups).sort();
        const datasetPresent = [];
        const datasetHalfDay = [];
        const datasetAbsent = [];
        const datasetLeave = [];

        sortedDates.forEach(d => {
            datasetPresent.push(dateGroups[d].Present);
            datasetHalfDay.push(dateGroups[d]["Half Day"]);
            datasetAbsent.push(dateGroups[d].Absent);
            datasetLeave.push(dateGroups[d].Leave);
        });

        // Chart 1: Stacked Bar Chart for day-wise counts
        reportChartInstances.chart1 = new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: sortedDates,
                datasets: [
                    { label: 'Present', data: datasetPresent, backgroundColor: colors.present },
                    { label: 'Half Day', data: datasetHalfDay, backgroundColor: colors.halfDay },
                    { label: 'Absent', data: datasetAbsent, backgroundColor: colors.absent },
                    { label: 'Leave', data: datasetLeave, backgroundColor: colors.leave }
                ]
            },
            options: {
                ...chartOptions,
                scales: {
                    x: {
                        stacked: true,
                        grid: { color: colors.grid },
                        ticks: { color: colors.text }
                    },
                    y: {
                        stacked: true,
                        grid: { color: colors.grid },
                        ticks: { color: colors.text, stepSize: 1 }
                    }
                }
            }
        });

        // Aggregate counts for Donut Chart
        let totalPresent = 0, totalHalfDay = 0, totalAbsent = 0, totalLeave = 0;
        data.forEach(r => {
            if (r.status === "Present") totalPresent += r.count;
            else if (r.status === "Half Day") totalHalfDay += r.count;
            else if (r.status === "Absent") totalAbsent += r.count;
            else if (r.status === "Leave") totalLeave += r.count;
        });

        // Chart 2: Donut Chart for overall distribution
        reportChartInstances.chart2 = new Chart(ctx2, {
            type: 'doughnut',
            data: {
                labels: ['Present', 'Half Day', 'Absent', 'Leave'],
                datasets: [{
                    data: [totalPresent, totalHalfDay, totalAbsent, totalLeave],
                    backgroundColor: [colors.present, colors.halfDay, colors.absent, colors.leave],
                    borderWidth: 0
                }]
            },
            options: chartOptions
        });

        // Render Table
        let table = `
            <table>
                <thead>
                    <tr><th>Date</th><th>Status Type</th><th>Records Count</th></tr>
                </thead>
                <tbody>
        `;
        data.forEach(r => {
            table += `<tr>
                <td>${r.date}</td>
                <td><span class="badge ${r.status.toLowerCase().replace(' ', '-')}">${r.status}</span></td>
                <td>
                    <button onclick="viewReportDetails('attendance', '${r.date}', '${r.status}')" class="btn-action btn-edit" style="margin:0; padding:4px 12px; font-size:12px; font-weight:600; border-radius:8px;">${r.count} Employees</button>
                </td>
            </tr>`;
        });
        table += `</tbody></table>`;
        container.innerHTML = table;

    } else if (type === "employee") {
        title.innerHTML = "👥 Active Headcount breakdown by Department";

        const depts = data.map(r => r.department);
        const headcounts = data.map(r => r.employee_count);

        // Chart 1: Bar Chart of Headcount by Department
        reportChartInstances.chart1 = new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: depts,
                datasets: [{
                    label: 'Active Headcount',
                    data: headcounts,
                    backgroundColor: [colors.blue, colors.orange, colors.pink, '#A855F7', '#EC4899', '#3B82F6'],
                    borderWidth: 0
                }]
            },
            options: {
                ...chartOptions,
                plugins: {
                    ...chartOptions.plugins,
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: colors.grid },
                        ticks: { color: colors.text }
                    },
                    y: {
                        grid: { color: colors.grid },
                        ticks: { color: colors.text, stepSize: 1 }
                    }
                }
            }
        });

        // Chart 2: Pie Chart of Headcount Distribution
        reportChartInstances.chart2 = new Chart(ctx2, {
            type: 'pie',
            data: {
                labels: depts,
                datasets: [{
                    data: headcounts,
                    backgroundColor: [colors.blue, colors.orange, colors.pink, '#A855F7', '#EC4899', '#3B82F6'],
                    borderWidth: 0
                }]
            },
            options: chartOptions
        });

        // Render Table
        let table = `
            <table>
                <thead>
                    <tr><th>Department</th><th>Active Headcount</th></tr>
                </thead>
                <tbody>
        `;
        data.forEach(r => {
            table += `<tr>
                <td>${r.department}</td>
                <td>
                    <button onclick="viewReportDetails('employee', '${r.department.replace(/'/g, "\\'")}')" class="btn-action btn-edit" style="margin:0; padding:4px 12px; font-size:12px; font-weight:600; border-radius:8px;">${r.employee_count} Employees</button>
                </td>
            </tr>`;
        });
        table += `</tbody></table>`;
        container.innerHTML = table;

    } else if (type === "recruitment") {
        title.innerHTML = "🎯 Recruitment Funnel — Applications breakdown by Status";

        const statuses = data.map(r => r.status);
        const counts = data.map(r => r.application_count);

        // Chart 1: Horizontal Bar Chart for Funnel feel
        reportChartInstances.chart1 = new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: statuses,
                datasets: [{
                    label: 'Applications Count',
                    data: counts,
                    backgroundColor: [colors.pink, colors.orange, colors.blue, '#10B981', '#F59E0B'],
                    borderWidth: 0
                }]
            },
            options: {
                ...chartOptions,
                indexAxis: 'y',
                plugins: {
                    ...chartOptions.plugins,
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: colors.grid },
                        ticks: { color: colors.text, stepSize: 1 }
                    },
                    y: {
                        grid: { color: colors.grid },
                        ticks: { color: colors.text }
                    }
                }
            }
        });

        // Chart 2: Donut Chart
        reportChartInstances.chart2 = new Chart(ctx2, {
            type: 'doughnut',
            data: {
                labels: statuses,
                datasets: [{
                    data: counts,
                    backgroundColor: [colors.pink, colors.orange, colors.blue, '#10B981', '#F59E0B'],
                    borderWidth: 0
                }]
            },
            options: chartOptions
        });

        // Render Table
        let table = `
            <table>
                <thead>
                    <tr><th>Application Status</th><th>Total Count</th></tr>
                </thead>
                <tbody>
        `;
        data.forEach(r => {
            table += `<tr>
                <td><span class="badge ${r.status.toLowerCase().replace(' ', '-')}">${r.status}</span></td>
                <td>
                    <button onclick="viewReportDetails('recruitment', '${r.status}')" class="btn-action btn-edit" style="margin:0; padding:4px 12px; font-size:12px; font-weight:600; border-radius:8px;">${r.application_count} Applications</button>
                </td>
            </tr>`;
        });
        table += `</tbody></table>`;
        container.innerHTML = table;
    }
}

/**
 * Fetches breakdown detail records contributing to a report metric and opens detail modal.
 * 
 * @async
 * @param {string} type - Report category key.
 * @param {string} param1 - Query filter parameter 1 (date or department or status).
 * @param {string} [param2] - Query filter parameter 2 (status for attendance).
 */
async function viewReportDetails(type, param1, param2) {
    let url = `/reports/details/${type}`;
    let modalTitle = "";
    let headersHtml = "";
    
    if (type === "attendance") {
        url += `?date=${encodeURIComponent(param1)}&status=${encodeURIComponent(param2)}`;
        modalTitle = `Attendance Breakdown — ${param1} (${param2.toUpperCase()})`;
        headersHtml = `<tr><th>Employee ID</th><th>Name</th><th>Department</th><th>Designation</th><th>Check In</th><th>Check Out</th><th>Hours</th></tr>`;
    } else if (type === "employee") {
        url += `?department=${encodeURIComponent(param1)}`;
        modalTitle = `Active Headcount — ${param1}`;
        headersHtml = `<tr><th>Employee ID</th><th>Name</th><th>Designation</th><th>Phone</th><th>Status</th></tr>`;
    } else if (type === "recruitment") {
        url += `?status=${encodeURIComponent(param1)}`;
        modalTitle = `Applications List — Status: ${param1}`;
        headersHtml = `<tr><th>Candidate Name</th><th>Email</th><th>Phone</th><th>Job Title</th><th>Department</th><th>Applied On</th></tr>`;
    }

    try {
        const data = await apiCall(url);
        const titleEl = document.getElementById("reportDetailsModalTitle");
        const headerEl = document.getElementById("reportDetailsTableHeader");
        const bodyEl = document.getElementById("reportDetailsTableBody");

        titleEl.innerHTML = `<i data-lucide="file-text" style="color: var(--orange); width: 22px; height: 22px;"></i> <span>${modalTitle}</span>`;
        headerEl.innerHTML = headersHtml;
        bodyEl.innerHTML = "";

        if (data.length === 0) {
            const colCount = headerEl.querySelectorAll("th").length;
            bodyEl.innerHTML = `<tr><td colspan="${colCount}" style="text-align:center; color:var(--ink-soft); padding: 20px;">No matching records found.</td></tr>`;
        } else {
            data.forEach(row => {
                let rowHtml = "<tr>";
                if (type === "attendance") {
                    const whRaw = row.working_hours;
                    const whNum = typeof whRaw === 'number' ? whRaw : parseFloat(whRaw);
                    const whStr = (!isNaN(whNum) && whNum !== null) ? whNum.toFixed(2) : "0.00";
                    rowHtml += `
                        <td>${row.employee_id || "-"}</td>
                        <td><strong>${row.name || "-"}</strong></td>
                        <td>${row.department || "-"}</td>
                        <td>${row.designation || "-"}</td>
                        <td>${row.check_in || "-"}</td>
                        <td>${row.check_out || "-"}</td>
                        <td>${whStr} hrs</td>
                    `;
                } else if (type === "employee") {
                    rowHtml += `
                        <td>${row.employee_id || "-"}</td>
                        <td><strong>${row.name || "-"}</strong></td>
                        <td>${row.designation || "-"}</td>
                        <td>${row.phone_number || row.phone || "-"}</td>
                        <td><span class="badge ${row.status.toLowerCase()}">${row.status}</span></td>
                    `;
                } else if (type === "recruitment") {
                    const appliedDate = row.applied_at ? row.applied_at.split("T")[0] : "-";
                    rowHtml += `
                        <td><strong>${row.candidate_name || "-"}</strong></td>
                        <td>${row.email || "-"}</td>
                        <td>${row.phone || "-"}</td>
                        <td>${row.job_title || "-"}</td>
                        <td>${row.department || "-"}</td>
                        <td>${appliedDate}</td>
                    `;
                }
                rowHtml += "</tr>";
                bodyEl.innerHTML += rowHtml;
            });
        }

        openModal("viewReportDetailsModal");
        if (window.lucide) {
            lucide.createIcons();
        }
    } catch (e) {
        alert("Failed to load report detailed data.");
    }
}


/* ==========================================================================
   EMPLOYEE PORTAL HANDLERS
   ========================================================================== */

/**
 * Pulls employee dashboard details, notice board, and remaining leave balances.
 * 
 * @async
 */
async function loadEmpOverview() {
    const stats = await apiCall("/dashboard/stats");
    const presentEl = document.getElementById("bal_present_days");
    if (presentEl) presentEl.textContent = stats.total_present_days;
    const leavesEl = document.getElementById("bal_total_leaves");
    if (leavesEl) leavesEl.textContent = stats.total_leaves;

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

/**
 * Helper to retrieve user's live GPS coordinates via HTML5 Geolocation API.
 * @returns {Promise<{latitude: number, longitude: number}>}
 */
function getGPSCoordinates() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error("Geolocation is not supported by your browser."));
            return;
        }
        // Attempt 1: High accuracy GPS lookup (8s timeout)
        navigator.geolocation.getCurrentPosition(
            (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
            (err) => {
                if (err.code === err.PERMISSION_DENIED) {
                    reject(new Error("Location permission denied. Please allow location access on your browser/phone to check in."));
                    return;
                }
                // Attempt 2: Fallback to standard accuracy (Wi-Fi/Network location) if GPS times out or is unavailable
                navigator.geolocation.getCurrentPosition(
                    (pos2) => resolve({ latitude: pos2.coords.latitude, longitude: pos2.coords.longitude }),
                    (err2) => {
                        if (err2.code === err2.PERMISSION_DENIED) {
                            reject(new Error("Location permission denied. Please allow location access on your browser/phone to check in."));
                        } else {
                            reject(new Error("Location request timed out. Please ensure GPS / Location Services are turned ON on your device and try again."));
                        }
                    },
                    { enableHighAccuracy: false, timeout: 20000, maximumAge: 60000 }
                );
            },
            { enableHighAccuracy: true, timeout: 8000, maximumAge: 30000 }
        );
    });
}

/**
 * Triggers a Check In attendance registration request with Geofenced GPS verification.
 * 
 * @async
 */
async function markCheckIn(btn) {
    let originalText = "";
    if (btn) {
        btn.disabled = true;
        originalText = btn.innerHTML;
        btn.innerHTML = `<span class="spinner"></span> Locating...`;
    }
    try {
        let payload = {};
        try {
            const coords = await getGPSCoordinates();
            payload = coords;
        } catch (locErr) {
            alert("📍 GPS Location Access Required:\n\n" + locErr.message);
            return;
        }

        if (btn) btn.innerHTML = `<span class="spinner"></span> Verifying Location...`;
        const res = await apiCall("/attendance/checkin", "POST", payload);
        document.getElementById("attendanceTimerStatus").textContent = res.message;
        alert(res.message);
    } catch (err) {
        alert(err.message || "Failed to mark check-in");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

/**
 * Triggers a Check Out attendance registration request.
 * 
 * @async
 */
async function markCheckOut(btn) {
    let originalText = "";
    if (btn) {
        btn.disabled = true;
        originalText = btn.innerHTML;
        btn.innerHTML = `<span class="spinner"></span> Loading...`;
    }
    try {
        const res = await apiCall("/attendance/checkout", "POST");
        document.getElementById("attendanceTimerStatus").textContent = res.message;
        alert(res.message);
    } catch (err) {
        alert(err.message || "Failed to mark check-out");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
}

/**
 * Pulls personal attendance logs and renders history tables.
 * 
 * @async
 */
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

/**
 * Loads employee submitted leave applications log history.
 * 
 * @async
 */
async function loadEmpLeaves() {
    const records = await apiCall("/leaves");
    const tbody = document.getElementById("empLeavesTableBody");
    tbody.innerHTML = "";
    if (records.length === 0) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--ink-faint); padding:15px;">No leave applications submitted.</td></tr>`;
    records.forEach(l => {
        const leaveDays = Math.ceil((new Date(l.end_date) - new Date(l.start_date)) / (1000 * 60 * 60 * 24)) + 1;
        const isRevertible = !l.status.toLowerCase().includes("rejected") && !l.status.toLowerCase().includes("withdrawn");
        const revertBtn = isRevertible 
            ? `<button onclick="revertLeave(${l.id})" class="btn-action btn-reject" style="padding:4px 10px; font-size:11.5px; height:auto; border-radius:6px; display:inline-flex; align-items:center; gap:4px; margin:0;" title="Revert / Withdraw Leave Request">↩️ Revert</button>` 
            : '<span style="color:var(--ink-faint); font-size:11px;">-</span>';

        tbody.innerHTML += `
            <tr>
                <td>${escapeHTML(l.leave_type)}</td>
                <td>
                    <div style="font-weight:500;">${leaveDays} Day${leaveDays > 1 ? 's' : ''}</div>
                    <div style="font-size:11px; color:var(--ink-faint);">${new Date(l.start_date).toLocaleDateString()} to ${new Date(l.end_date).toLocaleDateString()}</div>
                </td>
                <td>${escapeHTML(l.reason || '-')}</td>
                <td>${getStatusBadgeHtml(l.status)}</td>
                <td>${revertBtn}</td>
            </tr>
        `;
    });
}

window.revertLeave = async function(leaveId) {
    if (!confirm("Are you sure you want to revert/withdraw this leave application?")) return;
    try {
        await apiCall(`/leaves/${leaveId}`, "DELETE");
        alert("Leave application reverted successfully.");
        loadEmpLeaves();
        if (typeof loadEmpOverview === 'function') loadEmpOverview();
    } catch(err) {
        alert("Failed to revert leave application: " + err.message);
    }
};

// Global submit handler for leave application
window.submitLeaveForm = async function(e) {
    if (e) e.preventDefault();
    const payload = {
        leave_type: document.getElementById("leaveType").value,
        start_date: document.getElementById("leaveStart").value,
        end_date: document.getElementById("leaveEnd").value,
        reason: document.getElementById("leaveReason").value
    };
    try {
        await apiCall("/leaves", "POST", payload);
        alert("Leave application submitted successfully for review!");
        const form = document.getElementById("applyLeaveForm");
        if (form) form.reset();
        loadEmpLeaves();
        loadEmpOverview(); // refresh leave balances
    } catch (err) {
        alert("Failed to submit leave request: " + err.message);
    }
};

/**
 * Loads notice board logs on employee notice board panels.
 * 
 * @async
 */
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


/* ==========================================================================
   PROFILE SETTINGS HANDLERS (SHARED BY ALL ROLES)
   ========================================================================== */

/**
 * Fetches active personal profile parameters and populates modifications form.
 * 
 * @async
 */
async function loadProfile() {
    try {
        const prof = await apiCall("/profile");
        if (!prof) return;

        // Populate basic values
        const nameInput = document.getElementById("profName");
        const emailInput = document.getElementById("profEmail");
        const phoneInput = document.getElementById("profPhone");
        const currentPwdInput = document.getElementById("profCurrentPassword");
        const pwdInput = document.getElementById("profPassword");
        const confirmPwdInput = document.getElementById("profConfirmPassword");

        if (nameInput) nameInput.value = prof.name || "";
        if (emailInput) emailInput.value = prof.email || "";
        if (phoneInput) phoneInput.value = prof.phone_number || "";
        if (currentPwdInput) currentPwdInput.value = "";
        if (pwdInput) pwdInput.value = "";
        if (confirmPwdInput) confirmPwdInput.value = "";

        // Header and avatar
        const headerName = document.getElementById("profHeaderName");
        const headerEmail = document.getElementById("profHeaderEmail");
        const avatarCircle = document.getElementById("profAvatarCircle");
        const roleBadge = document.getElementById("profRoleBadge");

        if (headerName) headerName.textContent = prof.name || "My Profile";
        if (headerEmail) headerEmail.textContent = prof.email || "";
        
        if (avatarCircle && prof.name) {
            const initials = prof.name.split(" ").map(n => n[0]).slice(0, 2).join("").toUpperCase();
            avatarCircle.textContent = initials || "U";
        }

        const userRole = (prof.role || user.role || "").toLowerCase();

        // Role badge styling
        if (roleBadge) {
            if (userRole === "admin") {
                roleBadge.textContent = "👑 EXECUTIVE ADMINISTRATOR";
                roleBadge.style.background = "rgba(255, 122, 0, 0.15)";
                roleBadge.style.borderColor = "rgba(255, 122, 0, 0.4)";
                roleBadge.style.color = "var(--orange)";
            } else if (userRole === "client") {
                roleBadge.textContent = "🤝 CLIENT PORTAL";
                roleBadge.style.background = "rgba(56, 189, 248, 0.15)";
                roleBadge.style.borderColor = "rgba(56, 189, 248, 0.4)";
                roleBadge.style.color = "#38bdf8";
            } else {
                roleBadge.textContent = "👔 INTERNAL EMPLOYEE";
                roleBadge.style.background = "rgba(124, 58, 237, 0.15)";
                roleBadge.style.borderColor = "rgba(124, 58, 237, 0.4)";
                roleBadge.style.color = "#a78bfa";
            }
        }

        // Employee / Executive details
        const empIdField = document.getElementById("profEmpIdField");
        const deptField = document.getElementById("profDeptField");
        const desgField = document.getElementById("profDesgField");
        const shiftField = document.getElementById("profShiftField");

        if (empIdField) empIdField.style.display = "block";
        if (deptField) deptField.style.display = "block";
        if (desgField) desgField.style.display = "block";

        const empIdInput = document.getElementById("profEmpId");
        const deptInput = document.getElementById("profDept");
        const desgInput = document.getElementById("profDesg");

        if (empIdInput) empIdInput.value = prof.employee_id || (userRole === "admin" ? "ADMIN-HQ" : "ETQP-SYS");
        if (deptInput) deptInput.value = prof.department || (userRole === "admin" ? "Executive Management" : "General");
        if (desgInput) desgInput.value = prof.designation || (userRole === "admin" ? "Executive Administrator" : "Staff");

        // Shift selector (only applicable for employees)
        if (shiftField) {
            if (userRole === "employee") {
                shiftField.style.display = "block";
                try {
                    const shiftData = await apiCall("/attendance/shift");
                    const shiftSelect = document.getElementById("profShift");
                    if (shiftSelect && shiftData.shift) {
                        shiftSelect.value = shiftData.shift;
                    }
                } catch(e) { /* silent fail */ }
            } else {
                shiftField.style.display = "none";
            }
        }

    } catch (err) {
        console.error("Failed to load profile:", err);
    }
}

// Modify settings profile form submit handler
const profileForm = document.getElementById("profileForm");
if (profileForm) {
    profileForm.addEventListener("submit", async function(e) {
        e.preventDefault();

        const nameVal = document.getElementById("profName").value.trim();
        const emailVal = document.getElementById("profEmail").value.trim();
        const phoneVal = document.getElementById("profPhone") ? document.getElementById("profPhone").value.trim() : "";
        const currentPwd = document.getElementById("profCurrentPassword") ? document.getElementById("profCurrentPassword").value : "";
        const newPwd = document.getElementById("profPassword") ? document.getElementById("profPassword").value : "";
        const confirmPwd = document.getElementById("profConfirmPassword") ? document.getElementById("profConfirmPassword").value : "";

        if (!nameVal || !emailVal) {
            alert("Name and Email Address are required.");
            return;
        }

        const payload = {
            name: nameVal,
            email: emailVal,
            phone_number: phoneVal
        };

        // Password change validations
        if (newPwd || confirmPwd || currentPwd) {
            if (!currentPwd) {
                alert("Please enter your Current Password to update your password.");
                if (document.getElementById("profCurrentPassword")) document.getElementById("profCurrentPassword").focus();
                return;
            }
            if (!newPwd) {
                alert("Please enter a New Password.");
                if (document.getElementById("profPassword")) document.getElementById("profPassword").focus();
                return;
            }
            if (newPwd !== confirmPwd) {
                alert("New Password and Confirm New Password do not match. Please verify.");
                if (document.getElementById("profConfirmPassword")) document.getElementById("profConfirmPassword").focus();
                return;
            }
            if (newPwd.length < 8) {
                alert("New password must be at least 8 characters long.");
                if (document.getElementById("profPassword")) document.getElementById("profPassword").focus();
                return;
            }
            payload.current_password = currentPwd;
            payload.password = newPwd;
        }

        const submitBtn = document.getElementById("profSubmitBtn");
        const originalBtnHtml = submitBtn ? submitBtn.innerHTML : "";
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = `<span>Saving changes...</span>`;
        }

        try {
            const res = await apiCall("/profile", "PUT", payload);

            // Save shift if employee
            const shiftSelect = document.getElementById("profShift");
            if (shiftSelect && user.role === "employee") {
                const selectedShift = shiftSelect.value;
                try {
                    await apiCall("/attendance/shift", "POST", { shift: selectedShift });
                    user.shift = selectedShift;
                    localStorage.setItem("user", JSON.stringify(user));
                } catch(e) { /* silent */ }
            }

            alert(newPwd ? "Profile and password updated successfully!" : "Profile settings saved successfully!");

            user.name = payload.name;
            user.email = payload.email;
            localStorage.setItem("user", JSON.stringify(user));
            
            const greeting = document.getElementById("userGreeting");
            if (greeting) {
                greeting.textContent = `Hello, ${user.name} (${user.role.toUpperCase()})`;
            }

            loadProfile();
        } catch (err) {
            alert(err.message || "Failed to update profile settings.");
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnHtml;
            }
        }
    });
}


/* ==========================================================================
   CANDIDATE PORTAL HANDLERS
   ========================================================================== */

/**
 * Retrieves submitted jobs applications status logs for active candidate portal.
 * 
 * @async
 */
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


/* ==========================================================================
   CONTACT INQUIRIES REGISTER CONTROLLER
   ========================================================================== */

/**
 * Loads contact submissions inquiries lists from both EduTech portal and ElevateIQ website.
 * 
 * @async
 */
async function loadAdminContacts() {
    try {
        const edutechBody = document.getElementById("edutechContactsTableBody");
        const elevateBody = document.getElementById("elevateContactsTableBody");

        if (edutechBody) edutechBody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--ink-soft);">Loading submissions...</td></tr>`;
        const edutechData = await apiCall("/api/admin/contacts/edutech");
        if (edutechBody) {
            edutechBody.innerHTML = "";
            if (!edutechData || edutechData.length === 0) {
                edutechBody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--ink-faint);">No EduTech inquiries found.</td></tr>`;
            } else {
                edutechData.forEach(c => {
                    const dateStr = c.created_at ? new Date(c.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : "-";
                    edutechBody.innerHTML += `
                        <tr>
                            <td style="white-space: nowrap;">${dateStr}</td>
                            <td style="font-weight: 600;">${escapeHTML(c.name || '-')}</td>
                            <td><a href="mailto:${c.email}" style="color: var(--orange);">${escapeHTML(c.email || '-')}</a></td>
                            <td><a href="tel:${c.phone}" style="color: var(--blue);">${escapeHTML(c.phone || '-')}</a></td>
                            <td style="color: var(--pink-light); font-weight: 500;">${escapeHTML(c.track || '-')}</td>
                            <td style="max-width: 300px; word-break: break-word;">${escapeHTML(c.message || '-')}</td>
                        </tr>
                    `;
                });
            }
        }

        if (elevateBody) elevateBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--ink-soft);">Loading messages...</td></tr>`;
        const elevateData = await apiCall("/api/admin/contacts/elevate");
        if (elevateBody) {
            elevateBody.innerHTML = "";
            if (!elevateData || elevateData.length === 0) {
                elevateBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--ink-faint);">No messages from main site.</td></tr>`;
            } else {
                elevateData.forEach(c => {
                    const dateStr = c.created_at ? new Date(c.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : "-";
                    elevateBody.innerHTML += `
                        <tr>
                            <td style="white-space: nowrap;">${dateStr}</td>
                            <td style="font-weight: 600;">${escapeHTML(c.name || '-')}</td>
                            <td><a href="mailto:${c.email}" style="color: var(--orange);">${escapeHTML(c.email || '-')}</a></td>
                            <td style="max-width: 400px; word-break: break-word;">${escapeHTML(c.message || '-')}</td>
                        </tr>
                    `;
                });
            }
        }
    } catch (e) {
        console.error("Error loading contacts:", e);
    }
}

/**
 * Switches the visual list table view context between EduTech contacts and ElevateIQ contacts.
 * 
 * @param {string} type - Tab key identifier ('edutech' or 'elevate').
 */
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

// Print Media Listeners to dynamically swap Chart.js color palette styles
window.addEventListener('beforeprint', () => {
    if (currentActiveReportType) {
        const card = document.getElementById("reportOutputCard");
        if (card && card.style.display !== "none") {
            generateReport(currentActiveReportType, true);
        }
    }
});

window.addEventListener('afterprint', () => {
    if (currentActiveReportType) {
        const card = document.getElementById("reportOutputCard");
        if (card && card.style.display !== "none") {
            generateReport(currentActiveReportType, false);
        }
    }
});
