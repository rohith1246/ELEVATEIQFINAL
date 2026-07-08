/**
 * @file recruitment.js
 * @description Admin/HR Recruitment workflows sub-controller.
 * Manages active job vacancies creation, application auditing, resume downloads, and applicant status pipelines.
 */

/**
 * Loads job postings and submitted candidate applications lists into the dashboard.
 * 
 * @async
 */
async function loadAdminRecruitment() {
    // Renders active Job vacancies list
    const jobs = await apiCall("/jobs");
    const jobsTbody = document.getElementById("jobsTableBody");
    jobsTbody.innerHTML = "";
    if (jobs.length === 0) jobsTbody.innerHTML = `<tr><td colspan="6" style="text-align:center;">No job openings published.</td></tr>`;
    jobs.forEach(j => {
        const toggleStatus = j.status === 'Open' ? 'Closed' : 'Open';
        jobsTbody.innerHTML += `
            <tr>
                <td>${j.title}</td>
                <td>${j.department}</td>
                <td>${j.location}</td>
                <td>${j.salary_range}</td>
                <td><span class="badge ${j.status.toLowerCase()}">${j.status}</span></td>
                <td>
                    <button onclick="toggleJobStatus(${j.id}, '${toggleStatus}')" class="btn-action btn-edit">Set ${toggleStatus}</button>
                </td>
            </tr>
        `;
    });

    // Renders candidate job applications list
    const apps = await apiCall("/applications");
    const appsTbody = document.getElementById("applicationsTableBody");
    appsTbody.innerHTML = "";
    if (apps.length === 0) appsTbody.innerHTML = `<tr><td colspan="7" style="text-align:center;">No applications received.</td></tr>`;
    apps.forEach(a => {
        const date = new Date(a.applied_at).toLocaleDateString();
        appsTbody.innerHTML += `
            <tr>
                <td>${a.candidate_name}</td>
                <td>${a.email}</td>
                <td>
                    <div style="font-weight:500;">${a.job_title}</div>
                    <div style="font-size:11px; color:var(--ink-faint);">${a.job_department}</div>
                </td>
                <td><a href="#" onclick="viewResumeFile('${a.resume_filename}')" style="color:var(--blue); text-decoration:none;">📄 View Resume</a></td>
                <td>${date}</td>
                <td><span class="badge ${a.status.toLowerCase()}">${a.status}</span></td>
                <td style="white-space: nowrap;">
                    <div style="display: flex; gap: 6px; align-items: center;">
                        <button onclick="updateAppStatus(${a.id}, 'Shortlisted')" class="btn-action btn-approve" style="background:rgba(230,230,75,0.2); color:#ffffaa; border-color:rgba(230,230,75,0.4); margin: 0;">Shortlist</button>
                        <button onclick="updateAppStatus(${a.id}, 'Accepted')" class="btn-action btn-approve" style="margin: 0;">Accept</button>
                        <button onclick="updateAppStatus(${a.id}, 'Rejected')" class="btn-action btn-reject" style="margin: 0;">Reject</button>
                    </div>
                </td>
            </tr>
        `;
    });
}

/**
 * Triggers an authenticated file transfer to download a candidate resume.
 * 
 * @param {string} filename - The target filename stored in backend upload directory.
 */
function viewResumeFile(filename) {
    // Fetch binary file blob passing Bearer authentication token
    fetch(`${API_BASE}/uploads/resumes/${filename}`, {
        headers: { "Authorization": `Bearer ${token}` }
    })
    .then(res => res.blob())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
    })
    .catch(err => alert("Error downloading resume file: " + err));
}

/**
 * Dispatches a request to toggle a job status between Open and Closed.
 * 
 * @async
 * @param {number} id - Target job vacancy ID.
 * @param {string} newStatus - New status value ('Open' or 'Closed').
 */
async function toggleJobStatus(id, newStatus) {
    await apiCall(`/jobs/${id}`, "PUT", { status: newStatus });
    alert(`Job status updated to ${newStatus}`);
    loadAdminRecruitment();
}

/**
 * Updates an applicant's review pipeline status (e.g. Shortlisted, Accepted, Rejected).
 * 
 * @async
 * @param {number} id - Target application ID.
 * @param {string} newStatus - Target status.
 */
async function updateAppStatus(id, newStatus) {
    await apiCall(`/applications/${id}`, "PUT", { status: newStatus });
    alert(`Application status updated to ${newStatus}`);
    loadAdminRecruitment();
}

// Handle job creation form submission
const addJobForm = document.getElementById("addJobForm");
if (addJobForm) {
    addJobForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        const payload = {
            title: document.getElementById("jobTitle").value,
            department: document.getElementById("jobDept").value,
            location: document.getElementById("jobLoc").value,
            experience_required: document.getElementById("jobExp").value,
            salary_range: document.getElementById("jobSalary").value,
            skills_required: document.getElementById("jobSkills").value,
            description: document.getElementById("jobDesc").value
        };
        await apiCall("/jobs", "POST", payload);
        alert("Job posting created!");
        closeModal("addJobModal");
        this.reset();
        loadAdminRecruitment();
    });
}

