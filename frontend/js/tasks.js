/**
 * Daily Tasks JavaScript Controller
 * Handles Employee Daily Task Logging & Admin Tasks Roster & Day-Wise Reports & Excel Downloads
 */

let allAdminTasksCache = [];
let activeAdminTaskShift = "All";
let activeAdminTaskStatus = "All";
let activeAdminTaskViewMode = "detailed"; // 'detailed' or 'summary'

/**
 * Helper to show global popup notifications (forwards to alert-override)
 */
function showGlobalAlert(title, message, type) {
    alert(message || title);
}

/**
 * Loads the Employee My Daily Tasks Panel
 */
async function loadMyTasksPanel() {
    const dateInput = document.getElementById("taskDateInput");
    if (dateInput && !dateInput.value) {
        dateInput.value = new Date().toISOString().split("T")[0];
    }

    const tbody = document.getElementById("myTasksTableBody");
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Loading your daily task logs...</td></tr>';

    try {
        const tasks = await apiCall("/api/daily-tasks/my-tasks");
        if (!tasks || tasks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--ink-soft);">No tasks logged yet. Submit your first task above!</td></tr>';
            if (document.getElementById("myTaskTotalHours")) {
                document.getElementById("myTaskTotalHours").textContent = "0.0 hrs";
            }
            return;
        }

        let totalHours = 0;

        tbody.innerHTML = tasks.map(t => {
            const hrs = parseFloat(t.hours_spent || 0);
            totalHours += hrs;
            
            let statusBadgeClass = "badge-completed";
            let statusIcon = "✅";
            const stLower = (t.status || "").toLowerCase();

            if (stLower === "in progress") {
                statusBadgeClass = "badge-in-progress";
                statusIcon = "⏳";
            } else if (stLower === "pending") {
                statusBadgeClass = "badge-pending";
                statusIcon = "📌";
            } else if (stLower === "blocked") {
                statusBadgeClass = "badge-blocked";
                statusIcon = "⚠️";
            }

            const taskJson = JSON.stringify(t).replace(/'/g, "&apos;").replace(/"/g, "&quot;");

            return `
                <tr>
                    <td style="white-space:nowrap; font-weight:600;">${t.task_date || '-'}</td>
                    <td style="font-weight:600; color:#60a5fa;">${escapeHtml(t.project_name || 'General')}</td>
                    <td style="max-width:320px; line-height:1.4;">${escapeHtml(t.task_description || '-')}</td>
                    <td style="text-align:center; font-weight:700; font-family:monospace; color:#34d399;">${hrs.toFixed(1)} hrs</td>
                    <td style="text-align:center;">
                        <span class="status-pill ${stLower.replace(' ', '-')}">${statusIcon} ${t.status || 'Completed'}</span>
                    </td>
                    <td style="color:var(--ink-soft); font-size:12.5px;">${escapeHtml(t.remarks || '-')}</td>
                    <td style="white-space:nowrap; text-align:center;">
                        <button onclick='editMyTask(${taskJson})' class="btn-action btn-edit" title="Edit Task">✏️ Edit</button>
                        <button onclick='deleteMyTask(${t.id})' class="btn-action btn-reject" title="Delete Task" style="margin-left:4px;">🗑️</button>
                    </td>
                </tr>
            `;
        }).join("");

        if (document.getElementById("myTaskTotalHours")) {
            document.getElementById("myTaskTotalHours").textContent = `${totalHours.toFixed(1)} hrs`;
        }
    } catch (e) {
        console.error("Failed to load my daily tasks:", e);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#ef4444;">Error loading task logs: ${e.message || e}</td></tr>`;
    }
}

/**
 * Handles submission of new or edited daily task log
 */
async function submitMyDailyTask(event) {
    event.preventDefault();

    const editId = document.getElementById("editTaskId").value;
    const task_date = document.getElementById("taskDateInput").value;
    const project_name = document.getElementById("taskProjectInput").value;
    const task_description = document.getElementById("taskDescInput").value;
    const hours_spent = document.getElementById("taskHoursInput").value;
    const status = document.getElementById("taskStatusInput").value;
    const remarks = document.getElementById("taskRemarksInput").value;

    const payload = { task_date, project_name, task_description, hours_spent, status, remarks };

    try {
        if (editId) {
            await apiCall(`/api/daily-tasks/${editId}`, "PUT", payload);
            showGlobalAlert("Success", "Task log updated successfully!", "success");
        } else {
            await apiCall("/api/daily-tasks", "POST", payload);
            showGlobalAlert("Success", "Daily task logged successfully!", "success");
        }

        cancelTaskEdit();
        loadMyTasksPanel();
    } catch (e) {
        console.error("Error submitting task:", e);
        showGlobalAlert("Error", e.message || "Failed to save daily task log", "error");
    }
}

/**
 * Populates task form for editing
 */
function editMyTask(task) {
    document.getElementById("editTaskId").value = task.id;
    document.getElementById("taskDateInput").value = task.task_date;
    document.getElementById("taskProjectInput").value = task.project_name || "";
    document.getElementById("taskDescInput").value = task.task_description || "";
    document.getElementById("taskHoursInput").value = task.hours_spent || 8.0;
    document.getElementById("taskStatusInput").value = task.status || "Completed";
    document.getElementById("taskRemarksInput").value = task.remarks || "";

    document.getElementById("btnCancelTaskEdit").style.display = "inline-block";
    document.getElementById("btnSaveTaskSubmit").textContent = "🔄 Update Task Entry";
    
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/**
 * Resets task form from editing state
 */
function cancelTaskEdit() {
    document.getElementById("editTaskId").value = "";
    document.getElementById("dailyTaskForm").reset();
    document.getElementById("taskDateInput").value = new Date().toISOString().split("T")[0];
    document.getElementById("taskHoursInput").value = 8.0;
    document.getElementById("btnCancelTaskEdit").style.display = "none";
    document.getElementById("btnSaveTaskSubmit").textContent = "💾 Save Task Entry";
}

/**
 * Deletes a personal daily task log
 */
async function deleteMyTask(taskId) {
    if (!confirm("Are you sure you want to delete this daily task log?")) return;

    try {
        await apiCall(`/api/daily-tasks/${taskId}`, "DELETE");
        showGlobalAlert("Deleted", "Task log removed successfully", "success");
        loadMyTasksPanel();
    } catch (e) {
        console.error("Error deleting task:", e);
        showGlobalAlert("Error", e.message || "Could not delete task log", "error");
    }
}


/* ============================================================
   ADMIN DAILY TASKS ROSTER & DAY-WISE REPORTS CONTROLLERS
   ============================================================ */

/**
 * Sets quick date presets for Admin Tasks Roster
 */
function setAdminTaskDatePreset(preset) {
    const startInput = document.getElementById("adminTaskStartDate");
    const endInput = document.getElementById("adminTaskEndDate");

    const todayStr = new Date().toISOString().split("T")[0];

    if (preset === "today") {
        startInput.value = todayStr;
        endInput.value = todayStr;
    } else if (preset === "yesterday") {
        const d = new Date();
        d.setDate(d.getDate() - 1);
        const yestStr = d.toISOString().split("T")[0];
        startInput.value = yestStr;
        endInput.value = yestStr;
    } else if (preset === "week") {
        const d = new Date();
        d.setDate(d.getDate() - 7);
        startInput.value = d.toISOString().split("T")[0];
        endInput.value = todayStr;
    } else if (preset === "all") {
        startInput.value = "";
        endInput.value = "";
    }

    loadAdminTasksRosterPanel();
}

/**
 * Switch view mode between Detailed Task Logs and Day-Wise Summary Reports
 */
function switchAdminTaskViewMode(mode, btn) {
    activeAdminTaskViewMode = mode;

    document.querySelectorAll(".btn-task-view-mode").forEach(b => {
        b.classList.remove("active");
        b.style.background = "transparent";
        b.style.color = "var(--ink-soft)";
    });

    if (btn) {
        btn.classList.add("active");
        btn.style.background = "var(--blue)";
        btn.style.color = "white";
    }

    const detailedWrap = document.getElementById("adminTaskDetailedWrap");
    const summaryWrap = document.getElementById("adminTaskSummaryWrap");
    const subFiltersRow = document.getElementById("taskSubFiltersRow");

    if (mode === "summary") {
        detailedWrap.style.display = "none";
        summaryWrap.style.display = "block";
        if (subFiltersRow) subFiltersRow.style.display = "none";
        loadAdminDailySummaryReport();
    } else {
        summaryWrap.style.display = "none";
        detailedWrap.style.display = "block";
        if (subFiltersRow) subFiltersRow.style.display = "flex";
        loadAdminTasksRosterPanel();
    }
}

/**
 * Loads Admin Daily Tasks Roster Panel
 */
async function loadAdminTasksRosterPanel() {
    if (activeAdminTaskViewMode === "summary") {
        return loadAdminDailySummaryReport();
    }

    const tbody = document.getElementById("adminTasksTableBody");
    if (!tbody) return;

    await ensureAdminEmployeeDropdownLoaded();

    const startDate = document.getElementById("adminTaskStartDate") ? document.getElementById("adminTaskStartDate").value : "";
    const endDate = document.getElementById("adminTaskEndDate") ? document.getElementById("adminTaskEndDate").value : "";
    const empFilter = document.getElementById("adminTaskEmpFilter") ? document.getElementById("adminTaskEmpFilter").value : "All";

    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;">Loading employee task logs...</td></tr>';

    try {
        let queryParams = [];
        if (startDate) queryParams.push(`start_date=${encodeURIComponent(startDate)}`);
        if (endDate) queryParams.push(`end_date=${encodeURIComponent(endDate)}`);
        if (empFilter && empFilter !== "All") queryParams.push(`employee_id=${encodeURIComponent(empFilter)}`);

        const queryString = queryParams.length ? `?${queryParams.join("&")}` : "";
        const tasks = await apiCall(`/api/daily-tasks/admin/tasks${queryString}`);

        allAdminTasksCache = tasks || [];
        renderAdminTasksRosterTable();
    } catch (e) {
        console.error("Failed to load admin daily tasks:", e);
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:#ef4444;">Error loading tasks roster: ${e.message || e}</td></tr>`;
    }
}

/**
 * Loads Day-Wise Aggregated Summary Reports
 */
async function loadAdminDailySummaryReport() {
    const tbody = document.getElementById("adminTaskSummaryTableBody");
    if (!tbody) return;

    const startDate = document.getElementById("adminTaskStartDate") ? document.getElementById("adminTaskStartDate").value : "";
    const endDate = document.getElementById("adminTaskEndDate") ? document.getElementById("adminTaskEndDate").value : "";

    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Loading day-wise summary reports...</td></tr>';

    try {
        let queryParams = [];
        if (startDate) queryParams.push(`start_date=${encodeURIComponent(startDate)}`);
        if (endDate) queryParams.push(`end_date=${encodeURIComponent(endDate)}`);

        const queryString = queryParams.length ? `?${queryParams.join("&")}` : "";
        const summaries = await apiCall(`/api/daily-tasks/admin/daily-summary${queryString}`);

        if (!summaries || summaries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--ink-soft);">No task records found for selected date range.</td></tr>';
            return;
        }

        let overallHours = 0;
        let overallTasks = 0;

        tbody.innerHTML = summaries.map(s => {
            const totHrs = parseFloat(s.total_hours || 0);
            overallHours += totHrs;
            overallTasks += parseInt(s.total_tasks || 0);

            const dayHrs = parseFloat(s.day_shift_hours || 0).toFixed(1);
            const nightHrs = parseFloat(s.night_shift_hours || 0).toFixed(1);

            return `
                <tr>
                    <td style="font-weight:700; font-size:14px; color:white; white-space:nowrap;">${s.task_date}</td>
                    <td style="text-align:center;">
                        <span class="badge" style="background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.3); font-weight:600;">👥 ${s.total_employees} Staff</span>
                    </td>
                    <td style="text-align:center; font-weight:600;">${s.total_tasks} tasks</td>
                    <td style="text-align:center; font-weight:700; font-family:monospace; color:#34d399; font-size:15px;">${totHrs.toFixed(1)} hrs</td>
                    <td style="text-align:center; font-size:12.5px;">
                        <span style="color:#fbbf24; font-weight:600;">☀️ ${dayHrs}h Day</span> &nbsp;|&nbsp; 
                        <span style="color:#60a5fa; font-weight:600;">🌙 ${nightHrs}h Night</span>
                    </td>
                    <td style="text-align:center; font-size:12.5px;">
                        <span style="color:#34d399; font-weight:600;">✅ ${s.completed_tasks} Comp</span> &nbsp;|&nbsp; 
                        <span style="color:#fbbf24; font-weight:600;">⏳ ${s.pending_tasks} Pend</span>
                    </td>
                    <td style="white-space:nowrap; text-align:center;">
                        <button onclick="inspectDayTasks('${s.task_date}')" class="btn-action btn-edit" title="Filter to this Date">👁️ Inspect Tasks</button>
                        <button onclick="downloadDayExcel('${s.task_date}')" class="btn-action btn-approve" style="margin-left:4px; background:rgba(16,185,129,0.2); color:#34d399; border:1px solid rgba(16,185,129,0.3);" title="Export Day Excel">📊 Excel</button>
                    </td>
                </tr>
            `;
        }).join("");

        // Update Stat Cards with aggregated totals
        if (document.getElementById("stat_task_total_count")) document.getElementById("stat_task_total_count").textContent = overallTasks;
        if (document.getElementById("stat_task_total_hours")) document.getElementById("stat_task_total_hours").textContent = `${overallHours.toFixed(1)} hrs`;
    } catch (e) {
        console.error("Failed to load daily summary report:", e);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#ef4444;">Error loading summary reports: ${e.message || e}</td></tr>`;
    }
}

/**
 * Filter detailed view to a specific date from Day Summary row
 */
function inspectDayTasks(dateStr) {
    document.getElementById("adminTaskStartDate").value = dateStr;
    document.getElementById("adminTaskEndDate").value = dateStr;
    switchAdminTaskViewMode('detailed', document.getElementById("btnTaskViewDetailed"));
}

/**
 * Download Excel report for a specific single date
 */
function downloadDayExcel(dateStr) {
    showGlobalAlert("Downloading...", `Generating Excel report for ${dateStr}...`, "success");
    window.location.href = `/api/daily-tasks/export-excel?start_date=${dateStr}&end_date=${dateStr}`;
}

/**
 * Ensures the admin employee filter dropdown is populated
 */
async function ensureAdminEmployeeDropdownLoaded() {
    const select = document.getElementById("adminTaskEmpFilter");
    if (!select || select.children.length > 1) return;

    try {
        const emps = await apiCall("/employees");
        if (emps && emps.length) {
            select.innerHTML = '<option value="All">All Staff Members</option>' + emps.map(e => `
                <option value="${e.id}">${escapeHtml(e.name)} (${e.employee_id})</option>
            `).join("");
        }
    } catch (e) {
        console.error("Could not populate employee filter dropdown:", e);
    }
}

/**
 * Renders filtered admin daily tasks roster table and updates summary cards
 */
function renderAdminTasksRosterTable() {
    const tbody = document.getElementById("adminTasksTableBody");
    if (!tbody) return;

    let filtered = allAdminTasksCache;

    if (activeAdminTaskShift !== "All") {
        filtered = filtered.filter(t => (t.shift || "Day Shift").toLowerCase() === activeAdminTaskShift.toLowerCase());
    }

    if (activeAdminTaskStatus !== "All") {
        filtered = filtered.filter(t => (t.status || "").toLowerCase() === activeAdminTaskStatus.toLowerCase());
    }

    let totalCount = filtered.length;
    let totalHours = 0;
    let completedCount = 0;
    let pendingCount = 0;

    filtered.forEach(t => {
        const hrs = parseFloat(t.hours_spent || 0);
        totalHours += hrs;
        const st = (t.status || "").toLowerCase();
        if (st === "completed") completedCount++;
        else pendingCount++;
    });

    if (document.getElementById("stat_task_total_count")) document.getElementById("stat_task_total_count").textContent = totalCount;
    if (document.getElementById("stat_task_total_hours")) document.getElementById("stat_task_total_hours").textContent = `${totalHours.toFixed(1)} hrs`;
    if (document.getElementById("stat_task_completed_count")) document.getElementById("stat_task_completed_count").textContent = completedCount;
    if (document.getElementById("stat_task_pending_count")) document.getElementById("stat_task_pending_count").textContent = pendingCount;

    if (!filtered || filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:var(--ink-soft);">No task records found matching selected filters.</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(t => {
        const isNight = (t.shift || "").toLowerCase() === "night shift";
        const shiftBadge = isNight ? 
            '<span class="badge" style="background:rgba(96,165,250,0.15); color:#60a5fa; border:1px solid rgba(96,165,250,0.3);">🌙 Night</span>' :
            '<span class="badge" style="background:rgba(251,191,36,0.15); color:#fbbf24; border:1px solid rgba(251,191,36,0.3);">☀️ Day</span>';

        let statusIcon = "✅";
        const stLower = (t.status || "").toLowerCase();
        if (stLower === "in progress") statusIcon = "⏳";
        else if (stLower === "pending") statusIcon = "📌";
        else if (stLower === "blocked") statusIcon = "⚠️";

        return `
            <tr>
                <td style="white-space:nowrap; font-weight:600;">${t.task_date || '-'}</td>
                <td style="font-family:monospace; color:var(--ink-soft);">${escapeHtml(t.employee_code || '-')}</td>
                <td style="font-weight:600; color:white;">${escapeHtml(t.employee_name || '-')}</td>
                <td style="text-align:center;">${shiftBadge}</td>
                <td style="color:var(--ink-soft);">${escapeHtml(t.department || 'General')}</td>
                <td style="font-weight:600; color:#60a5fa;">${escapeHtml(t.project_name || 'General')}</td>
                <td style="max-width:320px; line-height:1.4;">${escapeHtml(t.task_description || '-')}</td>
                <td style="text-align:center; font-weight:700; font-family:monospace; color:#34d399;">${parseFloat(t.hours_spent || 0).toFixed(1)}</td>
                <td style="text-align:center;">
                    <span class="status-pill ${stLower.replace(' ', '-')}">${statusIcon} ${t.status || 'Completed'}</span>
                </td>
                <td style="color:var(--ink-soft); font-size:12.5px;">${escapeHtml(t.remarks || '-')}</td>
            </tr>
        `;
    }).join("");
}

/**
 * Filter Admin Tasks Roster by Shift
 */
function filterAdminTasksByShift(shift, btn) {
    activeAdminTaskShift = shift;
    document.querySelectorAll(".btn-task-shift-filter").forEach(b => {
        b.classList.remove("active");
        b.style.background = "transparent";
        b.style.color = "var(--ink-soft)";
    });
    if (btn) {
        btn.classList.add("active");
        btn.style.background = "var(--blue)";
        btn.style.color = "white";
    }
    renderAdminTasksRosterTable();
}

/**
 * Filter Admin Tasks Roster by Status
 */
function filterAdminTasksByStatus(status, btn) {
    activeAdminTaskStatus = status;
    document.querySelectorAll(".btn-task-status-filter").forEach(b => {
        b.classList.remove("active");
        b.style.background = "transparent";
        b.style.color = "var(--ink-soft)";
    });
    if (btn) {
        btn.classList.add("active");
        btn.style.background = "var(--blue)";
        btn.style.color = "white";
    }
    renderAdminTasksRosterTable();
}

/**
 * Triggers download of formatted Excel report (.xlsx)
 */
function downloadAdminTasksExcel() {
    const startDate = document.getElementById("adminTaskStartDate") ? document.getElementById("adminTaskStartDate").value : "";
    const endDate = document.getElementById("adminTaskEndDate") ? document.getElementById("adminTaskEndDate").value : "";
    const empFilter = document.getElementById("adminTaskEmpFilter") ? document.getElementById("adminTaskEmpFilter").value : "All";

    let params = [];
    if (startDate) params.push(`start_date=${encodeURIComponent(startDate)}`);
    if (endDate) params.push(`end_date=${encodeURIComponent(endDate)}`);
    if (empFilter && empFilter !== "All") params.push(`employee_id=${encodeURIComponent(empFilter)}`);
    if (activeAdminTaskShift && activeAdminTaskShift !== "All") params.push(`shift=${encodeURIComponent(activeAdminTaskShift)}`);
    if (activeAdminTaskStatus && activeAdminTaskStatus !== "All") params.push(`status=${encodeURIComponent(activeAdminTaskStatus)}`);

    const queryString = params.length ? `?${params.join("&")}` : "";

    showGlobalAlert("Downloading...", "Generating multi-sheet formatted Excel spreadsheet report...", "success");

    window.location.href = `/api/daily-tasks/export-excel${queryString}`;
}

/**
 * Helper to escape HTML characters
 */
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
