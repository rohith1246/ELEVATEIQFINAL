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
async function loadAdminEmployees() {
    await loadDesignations();
    allEmployees = await apiCall("/employees?portal=elevateiq");
    renderEmployeesTable(allEmployees);
}

/**
 * Generates table row templates for employee accounts.
 * 
 * @param {Array<Object>} list - Employees list.
 */
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
    document.getElementById("editStatus").value = emp.status;
    
    await loadDesignations(emp.designation);
    openModal("editEmployeeModal");
}

// Save modified employee details form handler
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

/**
 * Loads daily attendance logs and updates registry table.
 * 
 * @async
 */
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


/* ==========================================================================
   4. ADMIN LEAVES REQUESTS REVIEW
   ========================================================================== */

/**
 * Fetches pending and processed leave request records and renders reviews table.
 * 
 * @async
 */
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
                <td>${actionBtn}</td>
            </tr>
        `;
    });
}

/**
 * Dispatches leave application review decision POST updates.
 * 
 * @async
 * @param {number} id - Target leave ID.
 * @param {string} action - Action status decision ('Approved' or 'Rejected').
 */
async function reviewLeave(id, action) {
    await apiCall(`/leaves/${id}`, "PUT", { status: action });
    alert(`Leave request ${action.toLowerCase()} successfully.`);
    loadAdminLeaves();
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
                        <td>${row.phone_number || "-"}</td>
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
 * Triggers a Check In attendance registration request.
 * 
 * @async
 */
async function markCheckIn(btn) {
    let originalText = "";
    if (btn) {
        btn.disabled = true;
        originalText = btn.innerHTML;
        btn.innerHTML = `<span class="spinner"></span> Loading...`;
    }
    try {
        const res = await apiCall("/attendance/checkin", "POST");
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

// Apply for leave form submission handler
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

// Modify settings profile form submit handler
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
