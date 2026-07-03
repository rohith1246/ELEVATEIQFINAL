let currentUser = user;
let chatEventSource = null;
let chatPollingInterval = null;
let activeConversationId = null;
let activeGroupConversationId = null;
let activeOversightConversationId = null;
let activeOversightType = null;
let allUsers = [];

let lastDMMessagesJson = "";
let lastDMListJson = "";
let lastGroupMessagesJson = "";
let lastGroupListJson = "";

function initChatSSE() {
    if (chatEventSource) {
        chatEventSource.close();
    }
    const sseUrl = token ? `${API_BASE}/chat/stream?token=${encodeURIComponent(token)}` : `${API_BASE}/chat/stream`;
    chatEventSource = new EventSource(sseUrl, { withCredentials: true });
    chatEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'message') {
                if (activeConversationId === data.conversation_id) {
                    refreshDMThread(false);
                }
                if (activeGroupConversationId === data.conversation_id) {
                    refreshGroupThread(false);
                }
                refreshDMList();
                refreshGroupList();
            } else if (data.type === 'conversation_update') {
                refreshDMList();
                refreshGroupList();
            }
        } catch (e) {
            console.error("SSE parsing error", e);
        }
    };
    chatEventSource.onerror = function(err) {
        console.error("SSE connection dropped, auto-reconnecting...", err);
    };
}

// Messages Panel (DMs)
async function loadMessagesPanel() {
    activeConversationId = null;
    lastDMMessagesJson = "";
    lastDMListJson = "";
    document.getElementById("dmMainArea").style.display = "none";
    document.getElementById("dmPlaceholder").style.display = "flex";
    await refreshDMList();
}

async function refreshDMList() {
    try {
        const res = await apiCall("/chat/conversations");
        const list = res.filter(c => c.type === 'dm');
        
        const listJson = JSON.stringify(list) + "||" + activeConversationId;
        if (listJson === lastDMListJson) {
            return;
        }
        lastDMListJson = listJson;

        const container = document.getElementById("dmList");
        container.innerHTML = "";
        
        if (list.length === 0) {
            container.innerHTML = `<div style="padding:20px; color:var(--ink-soft); font-size:12px; text-align:center;">No workspace chats yet. Click "+ New Chat" to start.</div>`;
            return;
        }
        
        list.forEach(c => {
            const isSelected = activeConversationId === c.id;
            const badgeHtml = c.unread_count > 0 ? `<span class="badge">${c.unread_count}</span>` : '';
            const lastMsg = c.last_message ? c.last_message : 'No messages yet';
            const name = c.dm_user ? c.dm_user.name : 'Unknown Employee';
            
            container.innerHTML += `
                <div class="chat-list-item ${isSelected ? 'active' : ''}" onclick="selectDMConversation(${c.id}, '${name.replace(/'/g, "\\'")}')">
                    <div>
                        <div class="title">${name}</div>
                        <div class="subtitle">${lastMsg}</div>
                    </div>
                    <div>${badgeHtml}</div>
                </div>
            `;
        });
    } catch (e) {
        console.error(e);
    }
}

async function pollMessages() {
    await refreshDMList();
    if (activeConversationId) {
        await refreshDMThread(false);
    }
}

async function selectDMConversation(id, partnerName) {
    activeConversationId = id;
    lastDMMessagesJson = "";
    document.getElementById("dmPlaceholder").style.display = "none";
    document.getElementById("dmMainArea").style.display = "flex";
    document.getElementById("dmActiveTitle").textContent = partnerName;
    
    document.querySelectorAll("#dmList .chat-list-item").forEach(item => {
        item.classList.remove("active");
    });
    
    try {
        await apiCall(`/chat/conversations/${id}/read`, "POST");
    } catch(e) {}
    
    await refreshDMThread(true);
    await refreshDMList();
}

async function refreshDMThread(forceScroll = false) {
    if (!activeConversationId) return;
    try {
        const res = await apiCall(`/chat/conversations/${activeConversationId}/messages`);
        
        const messagesJson = JSON.stringify(res.messages);
        if (messagesJson === lastDMMessagesJson && !forceScroll) {
            return;
        }
        lastDMMessagesJson = messagesJson;

        const messagesDiv = document.getElementById("dmMessages");
        const isAtBottom = messagesDiv.scrollHeight - messagesDiv.clientHeight <= messagesDiv.scrollTop + 40;
        
        messagesDiv.innerHTML = "";
        
        if (res.messages.length === 0) {
            messagesDiv.innerHTML = `<div style="text-align:center; color:var(--ink-faint); margin-top:20px; font-size:13px;">No messages in this chat yet. Say hello!</div>`;
        } else {
            res.messages.forEach(m => {
                const isMine = m.sender_id === currentUser.id;
                const bubbleClass = isMine ? 'outgoing' : 'incoming';
                const senderHtml = isMine ? '' : `<div class="sender">${m.sender_name}</div>`;
                const timeStr = m.sent_at ? new Date(m.sent_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
                
                messagesDiv.innerHTML += `
                    <div class="msg-bubble ${bubbleClass}">
                        ${senderHtml}
                        <div>${m.content}</div>
                        <div class="time">${timeStr}</div>
                    </div>
                `;
            });
        }
        
        if (forceScroll || isAtBottom) {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
    } catch(e) {
        console.error(e);
    }
}

async function sendChatMessage(type) {
    if (type === 'dm') {
        const input = document.getElementById("dmInput");
        const val = input.value.trim();
        if (!val || !activeConversationId) return;
        
        const messagesDiv = document.getElementById("dmMessages");
        const timeStr = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        const tempId = "temp_" + Date.now();
        messagesDiv.innerHTML += `
            <div class="msg-bubble outgoing" id="${tempId}" style="opacity: 0.7;">
                <div>${escapeHTML(val)}</div>
                <div class="time">${timeStr} (sending...)</div>
            </div>
        `;
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
        input.value = "";
        try {
            await apiCall(`/chat/conversations/${activeConversationId}/messages`, "POST", { content: val });
            const tempElem = document.getElementById(tempId);
            if (tempElem) tempElem.remove();
            await refreshDMThread(true);
        } catch(e) {
            const tempElem = document.getElementById(tempId);
            if (tempElem) {
                tempElem.style.opacity = "1";
                tempElem.style.background = "rgba(230, 75, 75, 0.2)";
                tempElem.querySelector(".time").textContent = "failed to send";
            }
        }
    } else {
        const input = document.getElementById("groupInput");
        const val = input.value.trim();
        if (!val || !activeGroupConversationId) return;
        
        const messagesDiv = document.getElementById("groupMessages");
        const timeStr = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        const tempId = "temp_" + Date.now();
        messagesDiv.innerHTML += `
            <div class="msg-bubble outgoing" id="${tempId}" style="opacity: 0.7;">
                <div>${escapeHTML(val)}</div>
                <div class="time">${timeStr} (sending...)</div>
            </div>
        `;
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
        input.value = "";
        try {
            await apiCall(`/chat/conversations/${activeGroupConversationId}/messages`, "POST", { content: val });
            const tempElem = document.getElementById(tempId);
            if (tempElem) tempElem.remove();
            await refreshGroupThread(true);
        } catch(e) {
            const tempElem = document.getElementById(tempId);
            if (tempElem) {
                tempElem.style.opacity = "1";
                tempElem.style.background = "rgba(230, 75, 75, 0.2)";
                tempElem.querySelector(".time").textContent = "failed to send";
            }
        }
    }
}

function handleChatKey(e, type) {
    if (e.key === 'Enter') {
        sendChatMessage(type);
    }
}

async function openNewDMModal() {
    document.getElementById("dmUserSearch").value = "";
    openModal("newDMModal");
    await loadDMUsersList();
}

async function loadDMUsersList() {
    try {
        const users = await apiCall("/chat/users");
        allUsers = users;
        renderDMUsersList(users);
    } catch(e) {}
}

function renderDMUsersList(list) {
    const container = document.getElementById("dmUsersList");
    container.innerHTML = "";
    if (list.length === 0) {
        container.innerHTML = `<div style="text-align:center; color:var(--ink-soft); font-size:13px; padding:10px;">No employees found.</div>`;
        return;
    }
    list.forEach(u => {
        container.innerHTML += `
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:10px 14px; border-radius:10px;">
                <div>
                    <div style="font-weight:600; font-size:13.5px; color:#fff;">${u.name}</div>
                    <div style="font-size:11px; color:var(--ink-soft);">${u.email}</div>
                </div>
                <button onclick="startDMWithUser(${u.id}, '${u.name.replace(/'/g, "\\'")}')" class="btn-primary" style="padding:6px 12px; font-size:11px;">Chat</button>
            </div>
        `;
    });
}

function filterDMUsersList() {
    const q = document.getElementById("dmUserSearch").value.toLowerCase();
    const filtered = allUsers.filter(u => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q));
    renderDMUsersList(filtered);
}

async function startDMWithUser(userId, userName) {
    try {
        const res = await apiCall("/chat/conversations", "POST", { type: "dm", members: [userId] });
        closeModal("newDMModal");
        await refreshDMList();
        selectDMConversation(res.id, userName);
    } catch(e) {}
}

// Groups Panel (DMs)
async function loadGroupsPanel() {
    activeGroupConversationId = null;
    lastGroupMessagesJson = "";
    lastGroupListJson = "";
    document.getElementById("groupMainArea").style.display = "none";
    document.getElementById("groupPlaceholder").style.display = "flex";
    
    const isTLOrAdmin = currentUser.role === 'admin' || currentUser.is_team_leader;
    document.getElementById("btnCreateGroupSidebar").style.display = isTLOrAdmin ? "block" : "none";
    
    await refreshGroupList();
}

async function refreshGroupList() {
    try {
        const res = await apiCall("/chat/conversations");
        const list = res.filter(c => c.type === 'group');
        
        const listJson = JSON.stringify(list) + "||" + activeGroupConversationId;
        if (listJson === lastGroupListJson) {
            return;
        }
        lastGroupListJson = listJson;

        const container = document.getElementById("groupList");
        container.innerHTML = "";
        
        if (list.length === 0) {
            container.innerHTML = `<div style="padding:20px; color:var(--ink-soft); font-size:12px; text-align:center;">No groups yet.</div>`;
            return;
        }
        
        list.forEach(c => {
            const isSelected = activeGroupConversationId === c.id;
            const badgeHtml = c.unread_count > 0 ? `<span class="badge">${c.unread_count}</span>` : '';
            const lastMsg = c.last_message ? c.last_message : 'No activity';
            
            container.innerHTML += `
                <div class="chat-list-item ${isSelected ? 'active' : ''}" onclick="selectGroupConversation(${c.id}, '${c.group_name.replace(/'/g, "\\'")}')">
                    <div>
                        <div class="title">👥 ${c.group_name}</div>
                        <div class="subtitle">${lastMsg}</div>
                    </div>
                    <div>${badgeHtml}</div>
                </div>
            `;
        });
    } catch(e) {
        console.error(e);
    }
}

async function pollGroups() {
    await refreshGroupList();
    if (activeGroupConversationId) {
        await refreshGroupThread(false);
    }
}

async function selectGroupConversation(id, name) {
    activeGroupConversationId = id;
    lastGroupMessagesJson = "";
    document.getElementById("groupPlaceholder").style.display = "none";
    document.getElementById("groupMainArea").style.display = "flex";
    document.getElementById("groupActiveTitle").textContent = name;
    
    try {
        await apiCall(`/chat/conversations/${id}/read`, "POST");
    } catch(e) {}
    
    const actions = document.getElementById("groupActionsArea");
    actions.innerHTML = "";
    if (currentUser.role === 'admin' || currentUser.is_team_leader) {
        actions.innerHTML = `<button onclick="openAddMemberModal(${id})" class="btn-primary" style="padding: 6px 12px; font-size:12px;">+ Add Employee</button>`;
    }
    
    await refreshGroupThread(true);
    await refreshGroupList();
}

async function refreshGroupThread(forceScroll = false) {
    if (!activeGroupConversationId) return;
    try {
        const res = await apiCall(`/chat/conversations/${activeGroupConversationId}/messages`);
        
        const messagesJson = JSON.stringify(res.messages);
        const membersJson = JSON.stringify(res.members);
        const cacheKey = messagesJson + "||" + membersJson;
        if (cacheKey === lastGroupMessagesJson && !forceScroll) {
            return;
        }
        lastGroupMessagesJson = cacheKey;

        // Update Title & Simulated Online count
        const membersCount = res.members ? res.members.length : 0;
        const onlineCount = Math.max(1, Math.ceil(membersCount * 0.45));
        const groupTitleElem = document.getElementById("groupActiveTitle");
        
        groupTitleElem.innerHTML = `
            <div class="title-area">
                <h3 style="margin: 0; font-size: 18px; font-weight: 700; color: #fff;">${res.conversation.group_name || 'Group Chat'}</h3>
                <div class="meta" style="font-size: 12px; color: var(--ink-soft); margin-top: 4px;">${membersCount} Members &bull; ${onlineCount} Online</div>
            </div>
        `;
        
        const messagesDiv = document.getElementById("groupMessages");
        const isAtBottom = messagesDiv.scrollHeight - messagesDiv.clientHeight <= messagesDiv.scrollTop + 40;
        
        messagesDiv.innerHTML = "";
        
        res.messages.forEach(m => {
            const isMine = m.sender_id === currentUser.id;
            const bubbleClass = isMine ? 'outgoing' : 'incoming';
            const senderHtml = isMine ? '' : `<div class="sender">${m.sender_name}</div>`;
            const timeStr = m.sent_at ? new Date(m.sent_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
            
            messagesDiv.innerHTML += `
                <div class="msg-bubble ${bubbleClass}">
                    ${senderHtml}
                    <div>${m.content}</div>
                    <div class="time">${timeStr}</div>
                </div>
            `;
        });
        
        if (forceScroll || isAtBottom) {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        const membersList = document.getElementById("groupMembersList");
        membersList.innerHTML = "";
        res.members.forEach(m => {
            const roleBadge = m.role === 'admin' ? '<span style="color:var(--orange); font-size:9px; font-weight:700; margin-left:4px;">ADMIN</span>' : '';
            membersList.innerHTML += `
                <div class="member-card">
                    <div class="name">${m.name} ${roleBadge}</div>
                    <div class="status"><span style="width:6px; height:6px; border-radius:50%; background:#00e676; display:inline-block;"></span> Online</div>
                </div>
            `;
        });
    } catch(e) {
        console.error(e);
    }
}

async function openCreateGroupModal() {
    document.getElementById("newGroupName").value = "";
    openModal("createGroupModal");
    
    try {
        const users = await apiCall("/chat/users");
        const listDiv = document.getElementById("groupSelectMembersList");
        listDiv.innerHTML = "";
        users.forEach(u => {
            listDiv.innerHTML += `
                <label style="display:flex; align-items:center; gap:10px; background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:8px 12px; border-radius:8px; cursor:pointer;">
                    <input type="checkbox" name="group_select_user" value="${u.id}" style="cursor:pointer;">
                    <div>
                        <div style="font-size:12px; font-weight:600; color:#fff;">${u.name}</div>
                        <div style="font-size:10px; color:var(--ink-soft);">${u.role.toUpperCase()}</div>
                    </div>
                </label>
            `;
        });
    } catch(e) {}
}

async function submitCreateGroup(e) {
    e.preventDefault();
    const groupName = document.getElementById("newGroupName").value.trim();
    if (!groupName) return;
    
    const checked = document.querySelectorAll('input[name="group_select_user"]:checked');
    const selectedIds = [];
    checked.forEach(chk => {
        selectedIds.push(parseInt(chk.value));
    });
    
    try {
        const res = await apiCall("/chat/conversations", "POST", {
            type: "group",
            name: groupName,
            members: selectedIds
        });
        closeModal("createGroupModal");
        await refreshGroupList();
        selectGroupConversation(res.id, groupName);
    } catch(e) {}
}

async function openAddMemberModal(groupId) {
    openModal("addGroupMemberModal");
    const container = document.getElementById("addGroupMembersList");
    container.innerHTML = `<div style="text-align:center; color:var(--ink-soft);">Loading...</div>`;
    
    try {
        const users = await apiCall("/chat/users");
        const res = await apiCall(`/chat/conversations/${groupId}/messages`);
        const memberIds = res.members.map(m => m.id);
        
        const eligibleUsers = users.filter(u => !memberIds.includes(u.id));
        container.innerHTML = "";
        
        if (eligibleUsers.length === 0) {
            container.innerHTML = `<div style="text-align:center; color:var(--ink-faint); font-size:13px; padding:15px;">All employees are members of this group.</div>`;
            return;
        }
        
        eligibleUsers.forEach(u => {
            container.innerHTML += `
                <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); padding:8px 12px; border-radius:10px;">
                    <div>
                        <div style="font-weight:600; font-size:13px; color:#fff;">${u.name}</div>
                        <div style="font-size:10px; color:var(--ink-soft);">${u.email}</div>
                    </div>
                    <button onclick="addGroupMember(${groupId}, ${u.id})" class="btn-primary" style="padding:6px 12px; font-size:11px;">Add</button>
                </div>
            `;
        });
    } catch(e) {}
}

async function addGroupMember(groupId, userId) {
    try {
        await apiCall(`/chat/groups/${groupId}/members`, "POST", { user_id: userId });
        closeModal("addGroupMemberModal");
        await refreshGroupThread(true);
    } catch(e) {}
}

// Oversight Panel (Admin & TL Only)
async function loadOversightPanel() {
    activeOversightConversationId = null;
    document.getElementById("oversightMainArea").style.display = "none";
    document.getElementById("oversightPlaceholder").style.display = "flex";
    await refreshOversightList();
    chatPollingInterval = setInterval(pollOversight, 3000);
}

async function refreshOversightList() {
    try {
        let list = [];
        if (currentUser.role === 'admin') {
            list = await apiCall("/chat/admin/all");
        } else {
            list = await apiCall("/chat/team-leader/groups");
        }
        
        const container = document.getElementById("oversightList");
        container.innerHTML = "";
        
        if (list.length === 0) {
            container.innerHTML = `<div style="padding:20px; color:var(--ink-soft); font-size:12px; text-align:center;">No conversations active in the system.</div>`;
            return;
        }
        
        list.forEach(c => {
            const isSelected = activeOversightConversationId === c.id;
            let displayTitle = "";
            let displaySub = c.last_message ? c.last_message : 'No activity';
            
            if (c.type === 'dm') {
                const names = c.dm_members ? c.dm_members.map(m => m.name).join(' & ') : 'Direct Message';
                displayTitle = `👤 DM: ${names}`;
            } else {
                displayTitle = `👥 Group: ${c.group_name}`;
            }
            
            container.innerHTML += `
                <div class="chat-list-item ${isSelected ? 'active' : ''}" onclick="selectOversightConversation(${c.id}, '${c.type}', '${displayTitle.replace(/'/g, "\\'")}')">
                    <div>
                        <div class="title">${displayTitle}</div>
                        <div class="subtitle">${displaySub}</div>
                    </div>
                </div>
            `;
        });
    } catch(e) {
        console.error(e);
    }
}

async function pollOversight() {
    await refreshOversightList();
    if (activeOversightConversationId) {
        await refreshOversightThread();
    }
}

async function selectOversightConversation(id, type, title) {
    activeOversightConversationId = id;
    activeOversightType = type;
    document.getElementById("oversightPlaceholder").style.display = "none";
    document.getElementById("oversightMainArea").style.display = "flex";
    document.getElementById("oversightActiveTitle").textContent = title;
    
    await refreshOversightThread();
}

async function refreshOversightThread() {
    if (!activeOversightConversationId) return;
    try {
        const res = await apiCall(`/chat/conversations/${activeOversightConversationId}/messages`);
        const messagesDiv = document.getElementById("oversightMessages");
        messagesDiv.innerHTML = "";
        
        res.messages.forEach(m => {
            const timeStr = m.sent_at ? new Date(m.sent_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
            messagesDiv.innerHTML += `
                <div class="msg-bubble incoming" style="align-self: flex-start; max-width: 80%;">
                    <div class="sender" style="color: var(--orange);">${m.sender_name}</div>
                    <div>${m.content}</div>
                    <div class="time">${timeStr}</div>
                </div>
            `;
        });
        
        const membersPane = document.getElementById("oversightMembersPane");
        if (activeOversightType === 'group' && res.members && res.members.length > 0) {
            membersPane.style.display = "flex";
            const membersList = document.getElementById("oversightMembersList");
            membersList.innerHTML = "";
            res.members.forEach(m => {
                const roleBadge = m.role === 'admin' ? '<span style="color:var(--orange); font-size:9px; font-weight:700; margin-left:4px;">ADMIN</span>' : '';
                membersList.innerHTML += `
                    <div class="member-card">
                        <div class="name">${m.name} ${roleBadge}</div>
                        <div class="status"><span style="width:6px; height:6px; border-radius:50%; background:#00e676; display:inline-block;"></span> Online</div>
                    </div>
                `;
            });
        } else {
            membersPane.style.display = "none";
        }
    } catch(e) {
        console.error(e);
    }
}
