/**
 * @file crm.js
 * @description Controls the Client Relationship Management (CRM) workflows and client portals.
 * Renders pipeline metrics, interaction log histories, B2B access provisioning, and client/internal meetings schedules.
 */

/**
 * Loads the active CRM pipeline table registry and computes key performance stats.
 * 
 * @async
 */
async function loadCRM() {
    try {
        const clients = await apiCall("/crm/clients");
        const tbody = document.getElementById("crmTableBody");
        if (!tbody) return;
        tbody.innerHTML = "";
        
        let totalLeads = clients.length;
        let activeClients = 0;
        let totalValue = 0;
        
        if (totalLeads === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;">No leads or clients found in CRM.</td></tr>`;
        }
        
        clients.forEach(c => {
            if (c.status === "Active Client") {
                activeClients++;
            }
            const val = parseFloat(c.deal_size) || 0;
            totalValue += val;
            
            const timeStr = new Date(c.created_at).toLocaleDateString();
            
            let actions = `
                <div style="display: flex; gap: 6px; align-items: center; white-space: nowrap;">
                    <button onclick="openEditLeadModal(${c.id})" class="btn-action btn-edit" style="margin: 0;">Edit</button>
                    <button onclick="openInteractionsModal(${c.id}, '${escapeHTML(c.company_name)}')" class="btn-action btn-approve" style="background:rgba(0,230,118,0.15); color:#00e676; border-color:rgba(0,230,118,0.3); margin: 0;">Log</button>
            `;
            
            if (!c.user_id && c.status === "Active Client") {
                actions += `<button onclick="openProvisionModal(${c.id}, '${escapeHTML(c.email || '')}')" class="btn-action btn-approve" style="margin: 0;">Access</button>`;
            } else if (c.user_id) {
                actions += `<span style="font-size:11px; color:var(--ink-faint); margin: 0;">Access Set</span>`;
            }
            actions += `</div>`;
            
            const badgeClass = c.status.toLowerCase().replace(" ", "-");
            
            tbody.innerHTML += `
                <tr>
                    <td style="font-weight:600;">${escapeHTML(c.company_name)}</td>
                    <td>${escapeHTML(c.contact_name || '-')}</td>
                    <td>
                        <div style="font-size:12px; font-weight:500;">${escapeHTML(c.email || '-')}</div>
                        <div style="font-size:11px; color:var(--ink-faint);">${escapeHTML(c.phone_number || '-')}</div>
                    </td>
                    <td style="font-weight:600; color:#fff;">₹${val.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                    <td><span class="badge ${badgeClass}">${escapeHTML(c.status)}</span></td>
                    <td style="font-size:11px; color:var(--ink-faint);">${timeStr}</td>
                    <td style="white-space: nowrap;">${actions}</td>
                </tr>
            `;
        });
        
        document.getElementById("crm_stat_total").textContent = totalLeads;
        document.getElementById("crm_stat_active").textContent = activeClients;
        document.getElementById("crm_stat_value").textContent = "₹" + totalValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        
        const conversion = totalLeads > 0 ? Math.round((activeClients / totalLeads) * 100) : 0;
        document.getElementById("crm_stat_conversion").textContent = conversion + "%";
        loadCRMMeetings();
        
    } catch (e) {
        console.error(e);
    }
}

/**
 * Opens add client lead modal popup.
 */
function openAddLeadModal() {
    const form = document.getElementById("addLeadForm");
    if (form) form.reset();
    openModal("addLeadModal");
}

/**
 * Fetches specific lead data and populates edit form controls.
 * 
 * @async
 * @param {number} id - Target client lead ID.
 */
async function openEditLeadModal(id) {
    try {
        const clients = await apiCall("/crm/clients");
        const c = clients.find(item => item.id === id);
        if (!c) return;
        
        document.getElementById("editLeadId").value = c.id;
        document.getElementById("editLeadCompany").value = c.company_name;
        document.getElementById("editLeadContact").value = c.contact_name || '';
        document.getElementById("editLeadEmail").value = c.email || '';
        document.getElementById("editLeadPhone").value = c.phone_number || '';
        document.getElementById("editLeadDealSize").value = c.deal_size;
        document.getElementById("editLeadStatus").value = c.status;
        document.getElementById("editLeadNotes").value = c.notes || '';
        
        openModal("editLeadModal");
    } catch (err) {
        console.error(err);
    }
}

/**
 * Opens interactions log modal pop-up dialogue.
 * 
 * @async
 * @param {number} id - Client ID.
 * @param {string} companyName - Company name.
 */
async function openInteractionsModal(id, companyName) {
    try {
        document.getElementById("logInteractionClientId").value = id;
        document.getElementById("interactionsSub").textContent = `Company: ${companyName}`;
        
        const form = document.getElementById("logInteractionForm");
        if (form) form.reset();
        
        await loadInteractions(id);
        openModal("interactionsModal");
    } catch (err) {
        console.error(err);
    }
}

/**
 * Pulls client interaction logs and renders list entries.
 * 
 * @async
 * @param {number} clientId - Client ID.
 */
async function loadInteractions(clientId) {
    const list = document.getElementById("interactionsList");
    if (!list) return;
    list.innerHTML = `<div style="color:var(--ink-soft); font-size:11px;">Loading history...</div>`;
    
    const data = await apiCall(`/crm/clients/${clientId}/interactions`);
    list.innerHTML = "";
    
    if (data.length === 0) {
        list.innerHTML = `<div style="color:var(--ink-faint); font-size:11px; padding:10px 0;">No logged interactions.</div>`;
        return;
    }
    
    data.forEach(i => {
        const timeStr = new Date(i.created_at).toLocaleString();
        let icon = "📝";
        if (i.interaction_type === "Call") icon = "📞";
        else if (i.interaction_type === "Email") icon = "✉️";
        else if (i.interaction_type === "Meeting") icon = "👥";
        
        list.innerHTML += `
            <div style="background:rgba(255,255,255,0.02); border:1px solid var(--glass-border); padding:10px; border-radius:8px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <span style="font-size:12px; font-weight:600; color:#fff;">${icon} ${escapeHTML(i.interaction_type)}</span>
                    <span style="font-size:10px; color:var(--ink-faint);">${timeStr}</span>
                </div>
                <div style="font-size:11.5px; color:var(--ink-soft); line-height:1.4;">${escapeHTML(i.notes)}</div>
            </div>
        `;
    });
}

/**
 * Prepares portal access provisioning modal values.
 * 
 * @param {number} id - Client ID.
 * @param {string} email - Auto fill login email address.
 */
function openProvisionModal(id, email) {
    document.getElementById("provisionClientId").value = id;
    document.getElementById("provisionEmail").value = email || '';
    document.getElementById("provisionPassword").value = "";
    openModal("provisionModal");
}

/**
 * Loads client landing page statistics, welcome descriptions, and upcoming schedules.
 * 
 * @async
 */
async function loadClientOverview() {
    try {
        const prof = await apiCall("/profile");
        document.getElementById("clientWelcomeCompany").textContent = `Welcome to your portal, ${escapeHTML(prof.company_name)}`;
        document.getElementById("clientPortalId").textContent = escapeHTML(prof.client_id || '-');
        document.getElementById("clientPortalContact").textContent = escapeHTML(prof.contact_name || prof.name || '-');
        document.getElementById("clientPortalEmail").textContent = escapeHTML(prof.email || '-');
        document.getElementById("clientPortalPhone").textContent = escapeHTML(prof.phone_number || '-');
        
        const dealVal = parseFloat(prof.deal_size) || 0;
        document.getElementById("clientPortalDealSize").textContent = "₹" + dealVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        
        const meetingsList = document.getElementById("clientOverviewMeetingsList");
        if (!meetingsList) return;
        meetingsList.innerHTML = `<div style="color:var(--ink-soft); font-size:11px;">Loading meetings...</div>`;
        
        const meetings = await apiCall("/dashboard/meetings");
        meetingsList.innerHTML = "";
        
        if (meetings.length === 0) {
            meetingsList.innerHTML = `<div style="color:var(--ink-faint); font-size:12px; padding:10px 0;">No upcoming meetings scheduled.</div>`;
            return;
        }
        
        meetings.slice(0, 3).forEach(m => {
            const timeStr = new Date(m.scheduled_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            meetingsList.innerHTML += `
                <div style="background:rgba(255,255,255,0.02); border:1px solid var(--glass-border); padding:10px 12px; border-radius:8px; display:flex; justify-content:space-between; align-items:center; gap:10px;">
                    <div style="display:flex; align-items:center; gap:10px; min-width:0; flex:1;">
                        <div style="flex-shrink:0;">${getPlatformIcon(m.platform)}</div>
                        <div style="min-width:0; flex:1;">
                            <div style="font-size:12.5px; font-weight:600; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${escapeHTML(m.title)}</div>
                            <div style="font-size:11px; color:var(--ink-faint); margin-top:2px;">${timeStr}</div>
                        </div>
                    </div>
                    <a href="${m.meeting_link}" target="_blank" class="btn-primary" style="padding:4px 8px; font-size:10px; text-decoration:none; flex-shrink:0;">Join</a>
                </div>
            `;
        });
        
    } catch (e) {
        console.error(e);
    }
}

/**
 * Loads meetings registry list and formats custom badges and platforms.
 * 
 * @async
 */
async function loadClientMeetings() {
    try {
        const container = document.getElementById("clientMeetingsList");
        if (!container) return;
        container.innerHTML = `<div style="color:var(--ink-soft); font-size:11px;">Loading meetings...</div>`;
        const res = await apiCall("/dashboard/meetings");
        container.innerHTML = "";
        if (res.length === 0) {
            container.innerHTML = `<div style="color:var(--ink-faint); font-size:11px;">No scheduled meetings.</div>`;
            return;
        }
        res.forEach(m => {
            const timeStr = new Date(m.scheduled_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            container.innerHTML += `
                <div style="background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:10px; border-radius:8px; display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:10px;">
                    <div style="display:flex; align-items:center; gap:10px; flex:1; min-width:0;">
                        <div style="width:34px; height:34px; border-radius:6px; display:flex; align-items:center; justify-content:center; flex-shrink:0; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05);">
                            ${getPlatformIcon(m.platform)}
                        </div>
                        <div style="min-width:0; flex:1;">
                            <h5 style="font-size:12px; font-weight:600; margin:0; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${escapeHTML(m.title)}">${escapeHTML(m.title)}</h5>
                            <div style="display:flex; align-items:center; gap:6px; margin-top:2px; flex-wrap:wrap;">
                                <span style="font-size:8px; padding:1px 4px; border-radius:100px; background:${getPlatformBg(m.platform)}; color:${getPlatformColor(m.platform)}; font-weight:600; display:inline-block;">${m.platform}</span>
                                <div style="font-size:10px; color:var(--ink-faint);">${timeStr}</div>
                            </div>
                        </div>
                    </div>
                    <a href="${m.meeting_link}" target="_blank" class="btn-primary" style="padding:5px 10px; font-size:10px; text-decoration:none; flex-shrink:0;">Join</a>
                </div>
            `;
        });
    } catch(e) {
        console.error(e);
    }
}

/**
 * Handles dropdown visibility changes depending on meeting type.
 */
function toggleMeetType() {
    const type = document.getElementById("meetType").value;
    const field = document.getElementById("meetClientField");
    if (!field) return;
    if (type === "client") {
        field.style.display = "block";
        loadCRMDropdowns();
    } else {
        field.style.display = "none";
    }
}

/**
 * Populates Client dropdown selection menu for scheduling client meetings.
 * 
 * @async
 */
async function loadCRMDropdowns() {
    try {
        const select = document.getElementById("meetClient");
        if (!select) return;
        
        const clients = await apiCall("/crm/clients");
        select.innerHTML = '<option value="">-- Select Client --</option>';
        clients.forEach(c => {
            select.innerHTML += `<option value="${c.id}">${escapeHTML(c.company_name)} (${escapeHTML(c.contact_name || '')})</option>`;
        });
    } catch (e) {
        console.error("Could not load CRM dropdowns", e);
    }
}

/**
 * Renders list of scheduled internal employee meetings.
 * 
 * @async
 */
async function loadAdminMeetings() {
    try {
        const container = document.getElementById("adminMeetingsList");
        if (!container) return;
        container.innerHTML = `<div style="color:var(--ink-soft); font-size:12px;">Loading meetings...</div>`;
        const res = await apiCall("/dashboard/meetings");
        container.innerHTML = "";
        
        const internalMeetings = res.filter(m => m.meeting_type === 'internal' || !m.meeting_type);
        
        if (internalMeetings.length === 0) {
            container.innerHTML = `<div style="color:var(--ink-faint); font-size:12px;">No scheduled employee meetings.</div>`;
            return;
        }
        internalMeetings.forEach(m => {
            const timeStr = new Date(m.scheduled_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            container.innerHTML += `
                <div style="background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:12px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; gap:12px;">
                    <div style="display:flex; align-items:center; gap:12px; flex:1; min-width:0;">
                        <div style="width:36px; height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05);">
                            ${getPlatformIcon(m.platform)}
                        </div>
                        <div style="min-width:0; flex:1;">
                            <h4 style="font-size:13px; font-weight:600; margin:0; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${escapeHTML(m.title)}">${escapeHTML(m.title)}</h4>
                            <div style="display:flex; align-items:center; gap:6px; margin-top:3px; flex-wrap:wrap;">
                                <span style="font-size:9px; padding:1px 5px; border-radius:100px; background:${getPlatformBg(m.platform)}; color:${getPlatformColor(m.platform)}; font-weight:600; display:inline-block;">${m.platform}</span>
                                <div style="font-size:11px; color:var(--ink-faint);">${timeStr}</div>
                            </div>
                        </div>
                    </div>
                    <a href="${m.meeting_link}" target="_blank" class="btn-primary" style="padding:6px 12px; font-size:11px; text-decoration:none; flex-shrink:0;">Join</a>
                </div>
            `;
        });
    } catch(e) {
        console.error(e);
    }
}

/**
 * Renders list of scheduled meetings on the employee workspace dashboard.
 * 
 * @async
 */
async function loadEmployeeMeetings() {
    try {
        const container = document.getElementById("empMeetingsList");
        if (!container) return;
        container.innerHTML = `<div style="color:var(--ink-soft); font-size:11px;">Loading meetings...</div>`;
        const res = await apiCall("/dashboard/meetings");
        container.innerHTML = "";
        if (res.length === 0) {
            container.innerHTML = `<div style="color:var(--ink-faint); font-size:11px;">No scheduled meetings.</div>`;
            return;
        }
        res.forEach(m => {
            const timeStr = new Date(m.scheduled_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            container.innerHTML += `
                <div style="background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:10px; border-radius:8px; display:flex; justify-content:space-between; align-items:center; gap:10px;">
                    <div style="display:flex; align-items:center; gap:10px; flex:1; min-width:0;">
                        <div style="width:34px; height:34px; border-radius:6px; display:flex; align-items:center; justify-content:center; flex-shrink:0; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05);">
                            ${getPlatformIcon(m.platform)}
                        </div>
                        <div style="min-width:0; flex:1;">
                            <h5 style="font-size:12px; font-weight:600; margin:0; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${escapeHTML(m.title)}">${escapeHTML(m.title)}</h5>
                            <div style="display:flex; align-items:center; gap:6px; margin-top:2px; flex-wrap:wrap;">
                                <span style="font-size:8px; padding:1px 4px; border-radius:100px; background:${getPlatformBg(m.platform)}; color:${getPlatformColor(m.platform)}; font-weight:600; display:inline-block;">${m.platform}</span>
                                <div style="font-size:10px; color:var(--ink-faint);">${timeStr}</div>
                            </div>
                        </div>
                    </div>
                    <a href="${m.meeting_link}" target="_blank" class="btn-primary" style="padding:5px 10px; font-size:10px; text-decoration:none; flex-shrink:0;">Join</a>
                </div>
            `;
        });
    } catch(e) {
        console.error(e);
    }
}

/**
 * Handles creation of an internal employee meeting link.
 * 
 * @async
 * @param {Event} event - Form submit event.
 */
async function submitCreateMeeting(event) {
    event.preventDefault();
    const form = event.target;
    
    const title = form.querySelector("#meetTitle").value;
    const platform = form.querySelector("#meetPlatform").value;
    const meeting_link = form.querySelector("#meetLink").value;
    const scheduled_at = form.querySelector("#meetTime").value;

    const meetTypeElem = form.querySelector("#meetType");
    const meetClientElem = form.querySelector("#meetClient");
    
    const meeting_type = meetTypeElem ? meetTypeElem.value : 'internal';
    const client_id = (meetClientElem && meeting_type === 'client') ? meetClientElem.value : null;

    const btn = form.querySelector('button[type="submit"]');
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Creating...";

    try {
        await apiCall("/dashboard/meetings", "POST", { 
            title, 
            platform, 
            meeting_link, 
            scheduled_at, 
            meeting_type,
            client_id
        });
        alert(meeting_type === 'client' ? "Client meeting scheduled successfully!" : "Employee meeting created and shared successfully!");
        form.reset();
        
        const meetClientField = form.querySelector("#meetClientField");
        if (meetClientField) {
            meetClientField.style.display = "none";
        }

        loadAdminMeetings();
        if (typeof loadCRMMeetings === 'function') {
            loadCRMMeetings();
        }
    } catch(e) {
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.textContent = original;
    }
}

/**
 * Loads meetings scheduled for B2B client partners.
 * 
 * @async
 */
async function loadCRMMeetings() {
    try {
        const container = document.getElementById("crmMeetingsList");
        if (!container) return;
        container.innerHTML = `<div style="color:var(--ink-soft); font-size:12px;">Loading meetings...</div>`;
        const res = await apiCall("/dashboard/meetings");
        container.innerHTML = "";
        
        const clientMeetings = res.filter(m => m.meeting_type === 'client');
        
        if (clientMeetings.length === 0) {
            container.innerHTML = `<div style="color:var(--ink-faint); font-size:12px;">No scheduled client meetings.</div>`;
            return;
        }
        clientMeetings.forEach(m => {
            const timeStr = new Date(m.scheduled_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            container.innerHTML += `
                <div style="background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:12px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:10px;">
                    <div style="display:flex; align-items:center; gap:12px; flex:1; min-width:0;">
                        <div style="width:36px; height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; flex-shrink:0; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05);">
                            ${getPlatformIcon(m.platform)}
                        </div>
                        <div style="min-width:0; flex:1;">
                            <h4 style="font-size:13px; font-weight:600; margin:0; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${escapeHTML(m.title)}">${escapeHTML(m.title)}</h4>
                            <div style="display:flex; align-items:center; gap:6px; margin-top:3px; flex-wrap:wrap;">
                                <span style="font-size:9px; padding:1px 5px; border-radius:100px; background:${getPlatformBg(m.platform)}; color:${getPlatformColor(m.platform)}; font-weight:600; display:inline-block;">${m.platform}</span>
                                <span style="font-size:9px; padding:1px 5px; border-radius:100px; background:rgba(0,230,118,0.1); color:#00e676; font-weight:600; display:inline-block;">${escapeHTML(m.company_name || 'Client')}</span>
                                <div style="font-size:11px; color:var(--ink-faint);">${timeStr}</div>
                            </div>
                        </div>
                    </div>
                    <a href="${m.meeting_link}" target="_blank" class="btn-primary" style="padding:6px 12px; font-size:11px; text-decoration:none; flex-shrink:0;">Join</a>
                </div>
            `;
        });
    } catch(e) {
        console.error(e);
    }
}

/**
 * Submits dynamic post to create client-focused conference calls.
 * 
 * @async
 * @param {Event} event - Submit event context.
 */
async function submitCreateClientMeeting(event) {
    event.preventDefault();
    const title = document.getElementById("clientMeetTitle").value;
    const platform = document.getElementById("clientMeetPlatform").value;
    const meeting_link = document.getElementById("clientMeetLink").value;
    const scheduled_at = document.getElementById("clientMeetTime").value;
    const meeting_type = "client";
    const client_id = document.getElementById("clientMeetClient").value;

    const btn = event.target.querySelector('button[type="submit"]');
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Creating...";

    try {
        await apiCall("/dashboard/meetings", "POST", { title, platform, meeting_link, scheduled_at, meeting_type, client_id });
        alert("Client meeting scheduled successfully!");
        event.target.reset();
        loadCRMMeetings();
    } catch(e) {
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.textContent = original;
    }
}


/* ==========================================================================
   CRM INTERFACE FORM HANDLERS AND LISTENERS
   ========================================================================== */

// Handle Lead submission form POST
const addLeadForm = document.getElementById("addLeadForm");
if (addLeadForm) {
    addLeadForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        const payload = {
            company_name: document.getElementById("addLeadCompany").value,
            contact_name: document.getElementById("addLeadContact").value,
            email: document.getElementById("addLeadEmail").value,
            phone_number: document.getElementById("addLeadPhone").value,
            deal_size: parseFloat(document.getElementById("addLeadDealSize").value) || 0,
            status: document.getElementById("addLeadStatus").value,
            notes: document.getElementById("addLeadNotes").value
        };
        
        try {
            await apiCall("/crm/clients", "POST", payload);
            alert("Lead created successfully!");
            closeModal("addLeadModal");
            loadCRM();
            loadCRMDropdowns();
        } catch (err) {
            console.error(err);
        }
    });
}

// Handle edit client details form submit updates
const editLeadForm = document.getElementById("editLeadForm");
if (editLeadForm) {
    editLeadForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        const id = document.getElementById("editLeadId").value;
        const payload = {
            company_name: document.getElementById("editLeadCompany").value,
            contact_name: document.getElementById("editLeadContact").value,
            email: document.getElementById("editLeadEmail").value,
            phone_number: document.getElementById("editLeadPhone").value,
            deal_size: parseFloat(document.getElementById("editLeadDealSize").value) || 0,
            status: document.getElementById("editLeadStatus").value,
            notes: document.getElementById("editLeadNotes").value
        };
        
        try {
            await apiCall(`/crm/clients/${id}`, "PUT", payload);
            alert("Lead updated successfully!");
            closeModal("editLeadModal");
            loadCRM();
            loadCRMDropdowns();
        } catch (err) {
            console.error(err);
        }
    });
}

// Handle CRM interaction logs submissions
const logInteractionForm = document.getElementById("logInteractionForm");
if (logInteractionForm) {
    logInteractionForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        const clientId = document.getElementById("logInteractionClientId").value;
        const payload = {
            client_id: parseInt(clientId),
            interaction_type: document.getElementById("logInteractionType").value,
            notes: document.getElementById("logInteractionNotes").value
        };
        
        try {
            await apiCall("/crm/interactions", "POST", payload);
            document.getElementById("logInteractionForm").reset();
            await loadInteractions(clientId);
        } catch (err) {
            console.error(err);
        }
    });
}

// Handle portal credentials generation provisioning
const provisionForm = document.getElementById("provisionForm");
if (provisionForm) {
    provisionForm.addEventListener("submit", async function(e) {
        e.preventDefault();
        const id = document.getElementById("provisionClientId").value;
        const payload = {
            email: document.getElementById("provisionEmail").value,
            password: document.getElementById("provisionPassword").value
        };
        
        try {
            const res = await apiCall(`/crm/clients/${id}/provision`, "POST", payload);
            alert(`Access provisioned successfully! Client ID: ${res.client_id}`);
            closeModal("provisionModal");
            loadCRM();
        } catch (err) {
            console.error(err);
        }
    });
}

