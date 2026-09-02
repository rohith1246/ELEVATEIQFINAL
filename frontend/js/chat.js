/**
 * @file chat.js
 * @description Real-time chat workspace controller. Integrates SSE streams for message push notifications,
 * manages DMs/Group threads state, dynamic user query filters, group provisioning, file/image sharing,
 * member management, and admin auditing/oversight portals.
 */

let currentUser = user;
let chatEventSource = null;
let chatPollingInterval = null;
let activeConversationId = null;
let activeGroupConversationId = null;
let activeOversightConversationId = null;
let activeOversightType = null;
let allUsers = [];

// Periodic presence heartbeat ping (updates last_seen when tab is active)
setInterval(() => {
    if (currentUser && !document.hidden) {
        apiCall('/chat/heartbeat', 'POST').catch(() => {});
    }
}, 30000);

document.addEventListener("visibilitychange", () => {
    if (!document.hidden && currentUser) {
        apiCall('/chat/heartbeat', 'POST').catch(() => {});
    }
});

function formatToIST(dateStr) {
    if (!dateStr) return '';
    let cleanStr = dateStr;
    if (typeof cleanStr === 'string' && !cleanStr.endsWith('Z') && !cleanStr.includes('+') && !cleanStr.includes('GMT')) {
        cleanStr = cleanStr + 'Z';
    }
    const d = new Date(cleanStr);
    if (isNaN(d.getTime())) return '';
    const datePart = d.toLocaleDateString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
    const timePart = d.toLocaleTimeString('en-US', {
        timeZone: 'Asia/Kolkata',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
    return `${datePart}, ${timePart}`;
}

function formatMessageBody(text) {
    if (!text) return '';
    let escaped = escapeHTML(text);
    const urlRegex = /(https?:\/\/[^\s<]+)/gi;
    return escaped.replace(urlRegex, function(url) {
        return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="chat-link" onclick="event.stopPropagation();">${url}</a>`;
    });
}

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function renderMessageAttachment(m) {
    if (!m.file_url) return '';
    const url = m.file_url;
    const name = escapeHTML(m.file_name || 'Attachment');
    const type = (m.file_type || '').toLowerCase();
    const sizeStr = formatFileSize(m.file_size);
    
    const isImg = type.startsWith('image/') || /\.(png|jpg|jpeg|gif|webp|svg)$/i.test(url);
    if (isImg) {
        return `
            <div class="chat-file-image" style="margin-top: 8px; margin-bottom: 4px;">
                <a href="${url}" target="_blank" rel="noopener noreferrer" style="display: block; max-width: 280px; border-radius: 8px; overflow: hidden; border: 1px solid rgba(255,255,255,0.15);">
                    <img src="${url}" alt="${name}" style="width: 100%; max-height: 220px; object-fit: cover; display: block; cursor: pointer; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'" />
                </a>
                <div style="font-size: 11px; color: rgba(255,255,255,0.7); margin-top: 4px; display: flex; justify-content: space-between; align-items: center;">
                    <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px;">📷 ${name}</span>
                    <span style="font-size: 10px; color: rgba(255,255,255,0.5);">${sizeStr}</span>
                </div>
            </div>
        `;
    }
    
    let icon = '📄';
    if (type.includes('pdf') || /\.pdf$/i.test(name)) icon = '📕';
    else if (type.includes('sheet') || type.includes('excel') || type.includes('csv') || /\.(xls|xlsx|csv)$/i.test(name)) icon = '📊';
    else if (type.includes('word') || type.includes('document') || /\.(doc|docx)$/i.test(name)) icon = '📝';
    else if (type.includes('zip') || type.includes('compressed') || /\.(zip|rar|7z|tar|gz)$/i.test(name)) icon = '📦';
    else if (type.startsWith('video/') || /\.(mp4|mov|webm)$/i.test(name)) icon = '🎬';

    return `
        <div class="chat-file-card" style="margin-top: 8px; margin-bottom: 4px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; padding: 10px 12px; display: flex; align-items: center; justify-content: space-between; gap: 10px; max-width: 320px;">
            <div style="display: flex; align-items: center; gap: 8px; min-width: 0;">
                <span style="font-size: 22px;">${icon}</span>
                <div style="min-width: 0;">
                    <div style="font-weight: 600; font-size: 12px; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${name}</div>
                    <div style="font-size: 10.5px; color: rgba(255,255,255,0.6);">${sizeStr}</div>
                </div>
            </div>
            <a href="${url}" download="${name}" target="_blank" rel="noopener noreferrer" class="btn-download-file" style="background: rgba(255, 122, 0, 0.2); border: 1px solid rgba(255, 122, 0, 0.4); color: var(--orange, #ff7a00); padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; text-decoration: none; display: flex; align-items: center; gap: 4px; white-space: nowrap;">
                ⬇ Download
            </a>
        </div>
    `;
}

let lastDMMessagesJson = "";
let lastDMListJson = "";
let lastGroupMessagesJson = "";
let lastGroupListJson = "";

/**
 * Initializes Server-Sent Events (SSE) stream for real-time notification dispatching.
 */
function initChatSSE() {
    if (chatEventSource) {
        try { chatEventSource.close(); } catch(e) {}
    }
    
    const curToken = localStorage.getItem('token') || (typeof token !== 'undefined' ? token : '');
    const apiPrefix = (typeof API_BASE !== 'undefined' && API_BASE) ? API_BASE : '';
    const sseUrl = curToken ? `${apiPrefix}/chat/stream?token=${encodeURIComponent(curToken)}` : `${apiPrefix}/chat/stream`;
    
    try {
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
            console.warn("SSE connection dropped, falling back to smart poller...", err);
        };
    } catch (err) {
        console.error("Could not initialize SSE:", err);
    }

    if (!chatPollingInterval) {
        chatPollingInterval = setInterval(() => {
            const isSSEActive = (chatEventSource && chatEventSource.readyState === 1);
            if (!isSSEActive) {
                if (activeConversationId) refreshDMThread(false);
                if (activeGroupConversationId) refreshGroupThread(false);
            }
        }, 8000);
    }
}

/**
 * Initializes the Direct Messages (DMs) user interface workspace.
 */
async function loadMessagesPanel() {
    activeConversationId = null;
    lastDMMessagesJson = "";
    lastDMListJson = "";
    document.getElementById("dmMainArea").style.display = "none";
    document.getElementById("dmPlaceholder").style.display = "flex";
    initChatSSE();
    await refreshDMList();
}

/**
 * Fetches and renders active 1-on-1 DM conversations list from backend.
 */
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
            const badgeHtml = c.unread_count > 0 ? `<span class="badge" style="background:var(--orange); color:#fff; font-size:10px; font-weight:700; border-radius:100px; padding:2px 7px; min-width:18px; text-align:center;">${c.unread_count}</span>` : '';
            const lastMsg = c.last_message ? c.last_message : 'No messages yet';
            const name = c.dm_user ? c.dm_user.name : 'Colleague';
            const isOnline = c.dm_user && (c.dm_user.is_online === true || c.dm_user.is_online === 'true' || c.dm_user.is_online === 1);
            const avatarHtml = getUserAvatarHtml(name, 36, isOnline);
            
            container.innerHTML += `
                <div class="chat-list-item ${isSelected ? 'active' : ''}" onclick="selectDMConversation(${c.id}, '${name.replace(/'/g, "\\'")}')" style="display:flex; align-items:center; gap:12px; padding:12px 14px; border-radius:12px; margin-bottom:4px; cursor:pointer; transition:all 0.2s ease;">
                    ${avatarHtml}
                    <div style="flex:1; min-width:0;">
                        <div class="title" style="font-weight:600; font-size:13.5px; color:#fff; margin-bottom:2px; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${escapeHTML(name)}</div>
                        <div class="subtitle" style="font-size:11.5px; color:var(--ink-soft); text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${escapeHTML(lastMsg)}</div>
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

/**
 * Selects and activates a DM thread.
 */
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
    
    if (typeof clearConversationNotifications === "function") {
        clearConversationNotifications(id);
    }
    
    await refreshDMThread(true);
    await refreshDMList();
}

/**
 * Queries conversation message list from backend and populates the message thread view.
 */
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
                const senderHtml = isMine ? '' : `<div class="sender">${escapeHTML(m.sender_name)}</div>`;
                const timeStr = formatToIST(m.sent_at);
                const attachmentHtml = renderMessageAttachment(m);
                const bodyHtml = m.content ? `<div>${formatMessageBody(m.content)}</div>` : '';
                
                messagesDiv.innerHTML += `
                    <div class="msg-bubble ${bubbleClass}">
                        ${senderHtml}
                        ${bodyHtml}
                        ${attachmentHtml}
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

/**
 * Sends a message in the active thread (DM or Group).
 */
async function sendChatMessage(type) {
    if (type === 'dm') {
        const input = document.getElementById("dmInput");
        const val = input.value.trim();
        if (!val) return;
        if (!activeConversationId) {
            alert("Please select or start a direct message conversation first.");
            return;
        }
        
        const messagesDiv = document.getElementById("dmMessages");
        const timeStr = formatToIST(new Date());
        const tempId = "temp_" + Date.now();
        messagesDiv.innerHTML += `
            <div class="msg-bubble outgoing" id="${tempId}" style="opacity: 0.7;">
                <div>${formatMessageBody(val)}</div>
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
        if (!val) return;
        if (!activeGroupConversationId) {
            alert("Please select a group conversation first.");
            return;
        }
        
        const messagesDiv = document.getElementById("groupMessages");
        const timeStr = formatToIST(new Date());
        const tempId = "temp_" + Date.now();
        messagesDiv.innerHTML += `
            <div class="msg-bubble outgoing" id="${tempId}" style="opacity: 0.7;">
                <div>${formatMessageBody(val)}</div>
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

/**
 * Handles uploading files and images in chat conversations.
 */
async function handleChatFileUpload(type, input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    const convId = type === 'group' ? activeGroupConversationId : activeConversationId;
    if (!convId) {
        alert("Please select a conversation first.");
        input.value = "";
        return;
    }
    
    if (file.size > 25 * 1024 * 1024) {
        alert("File size exceeds the 25MB limit. Please select a smaller file.");
        input.value = "";
        return;
    }
    
    const textInput = document.getElementById(type === 'group' ? "groupInput" : "dmInput");
    const caption = textInput ? textInput.value.trim() : "";
    
    const formData = new FormData();
    formData.append("file", file);
    if (caption) formData.append("content", caption);
    
    const messagesDiv = document.getElementById(type === 'group' ? "groupMessages" : "dmMessages");
    if (messagesDiv) {
        messagesDiv.innerHTML += `
            <div class="msg-bubble outgoing sending-bubble" style="opacity: 0.75;">
                <div style="font-size:12px; font-style:italic; display:flex; align-items:center; gap:6px;">
                    <span style="display:inline-block; animation:spin 1s linear infinite;">⏳</span> Uploading ${escapeHTML(file.name)} (${formatFileSize(file.size)})...
                </div>
            </div>
        `;
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
    
    try {
        const token = localStorage.getItem("token") || (currentUser && currentUser.token);
        const headers = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        
        const response = await fetch(`/chat/conversations/${convId}/upload`, {
            method: "POST",
            headers: headers,
            body: formData
        });
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || "File upload failed");
        }
        
        if (textInput) textInput.value = "";
        input.value = "";
        
        if (type === 'group') {
            await refreshGroupThread(true);
            await refreshGroupList();
        } else {
            await refreshDMThread(true);
            await refreshDMList();
        }
    } catch (err) {
        console.error("Upload error:", err);
        alert(`Error uploading file: ${err.message}`);
        if (type === 'group') await refreshGroupThread(true);
        else await refreshDMThread(true);
    }
}

function handleChatKey(e, type) {
    if (e.key === 'Enter') {
        e.preventDefault();
        sendChatMessage(type);
    }
}

/**
 * Opens modal dialog for starting a new direct message conversation.
 */
async function openNewDMModal() {
    document.getElementById("dmUserSearch").value = "";
    openModal("newDMModal");
    await loadUsersForDM();
}

/**
 * Queries active directory users list for starting new direct messages.
 */
async function loadUsersForDM() {
    const listContainer = document.getElementById("dmUsersList");
    listContainer.innerHTML = '<div style="padding:20px; text-align:center; color:var(--ink-soft);">Loading directory...</div>';
    try {
        allUsers = await apiCall("/chat/users");
        renderDMUsersList(allUsers);
    } catch(e) {
        listContainer.innerHTML = '<div style="padding:20px; text-align:center; color:red;">Failed to load user directory.</div>';
    }
}

function renderDMUsersList(users) {
    const listContainer = document.getElementById("dmUsersList");
    if (!listContainer) return;
    listContainer.innerHTML = "";
    if (!users || users.length === 0) {
        listContainer.innerHTML = '<div style="padding:24px; text-align:center; color:var(--ink-soft); font-size:13px;">No colleagues found.</div>';
        return;
    }
    users.forEach(u => {
        const isOnline = u.is_online === true || u.is_online === 'true' || u.is_online === 1;
        const statusBadge = isOnline 
            ? '<span style="color:#10b981; font-size:11px; display:inline-flex; align-items:center; gap:3px;"><span style="width:6px; height:6px; border-radius:50%; background:#10b981;"></span> Online</span>' 
            : '<span style="color:var(--ink-soft); font-size:11px; display:inline-flex; align-items:center; gap:3px;"><span style="width:6px; height:6px; border-radius:50%; background:#64748b;"></span> Offline</span>';
        
        const roleLabel = (u.role === 'admin' || u.role === 'team_leader') ? `<span style="background:rgba(255, 122, 0, 0.15); border:1px solid rgba(255, 122, 0, 0.3); color:var(--orange); font-size:9.5px; font-weight:700; padding:1px 6px; border-radius:100px; margin-left:6px;">${u.role.toUpperCase()}</span>` : '';
        const avatarHtml = getUserAvatarHtml(u.name, 36, isOnline);

        listContainer.innerHTML += `
            <div class="user-select-row" onclick="startDMWithUser(${u.id}, '${u.name.replace(/'/g, "\\'")}')" style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); border-radius:12px; cursor:pointer; transition:all 0.2s ease;" onmouseover="this.style.background='rgba(255,255,255,0.07)'" onmouseout="this.style.background='rgba(255,255,255,0.03)'">
                <div style="display:flex; align-items:center; gap:12px; min-width:0;">
                    ${avatarHtml}
                    <div style="min-width:0;">
                        <div style="font-weight:600; font-size:13.5px; color:#fff; display:flex; align-items:center; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">
                            ${escapeHTML(u.name)} ${roleLabel}
                        </div>
                        <div style="font-size:11.5px; color:var(--ink-soft); text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${escapeHTML(u.email)}</div>
                    </div>
                </div>
                <div>${statusBadge}</div>
            </div>
        `;
    });
}

function filterDMUsers() {
    const q = (document.getElementById("dmUserSearch") ? document.getElementById("dmUserSearch").value : "").toLowerCase();
    const filtered = (allUsers || []).filter(u => 
        (u.name || '').toLowerCase().includes(q) || 
        (u.email || '').toLowerCase().includes(q) ||
        (u.role || '').toLowerCase().includes(q)
    );
    renderDMUsersList(filtered);
}

async function startDMWithUser(targetUserId, targetUserName) {
    try {
        const res = await apiCall("/chat/conversations", "POST", {
            type: "dm",
            member_ids: [targetUserId]
        });
        closeModal("newDMModal");
        await refreshDMList();
        await selectDMConversation(res.id, targetUserName);
    } catch (e) {
        alert(e.message || "Failed to create conversation");
    }
}

/**
 * Initializes the Group Chats interface panel.
 */
async function loadGroupsPanel() {
    activeGroupConversationId = null;
    lastGroupMessagesJson = "";
    lastGroupListJson = "";
    document.getElementById("groupMainArea").style.display = "none";
    document.getElementById("groupPlaceholder").style.display = "flex";
    initChatSSE();
    
    const btnCreate = document.getElementById("btnCreateGroupSidebar");
    if (btnCreate) {
        btnCreate.style.display = (currentUser && currentUser.role !== 'client') ? "inline-flex" : "none";
    }
    
    await refreshGroupList();
}

/**
 * Pulls active group chats list and dynamically injects them into the sidebar.
 */
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
            const badgeHtml = c.unread_count > 0 ? `<span class="badge" style="background:var(--orange); color:#fff; font-size:10px; font-weight:700; border-radius:100px; padding:2px 7px; min-width:18px; text-align:center;">${c.unread_count}</span>` : '';
            const lastMsg = c.last_message ? c.last_message : 'No messages yet';
            const groupName = c.group_name || 'Group Chat';
            const avatarHtml = `
                <div style="width:36px; height:36px; border-radius:12px; background:linear-gradient(135deg, rgba(255, 122, 0, 0.2), rgba(255, 122, 0, 0.4)); border:1px solid rgba(255, 122, 0, 0.35); display:flex; align-items:center; justify-content:center; color:var(--orange); font-size:16px; flex-shrink:0;">
                    👥
                </div>
            `;
            
            container.innerHTML += `
                <div class="chat-list-item ${isSelected ? 'active' : ''}" onclick="selectGroupConversation(${c.id}, '${groupName.replace(/'/g, "\\'")}')" style="display:flex; align-items:center; gap:12px; padding:12px 14px; border-radius:12px; margin-bottom:4px; cursor:pointer; transition:all 0.2s ease;">
                    ${avatarHtml}
                    <div style="flex:1; min-width:0;">
                        <div class="title" style="font-weight:600; font-size:13.5px; color:#fff; margin-bottom:2px; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${escapeHTML(groupName)}</div>
                        <div class="subtitle" style="font-size:11.5px; color:var(--ink-soft); text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${escapeHTML(lastMsg)}</div>
                    </div>
                    <div>${badgeHtml}</div>
                </div>
            `;
        });
    } catch (e) {
        console.error(e);
    }
}

async function pollGroups() {
    await refreshGroupList();
    if (activeGroupConversationId) {
        await refreshGroupThread(false);
    }
}

/**
 * Sets selected active group chat, marks it read, and renders control buttons.
 */
async function selectGroupConversation(id, name) {
    activeGroupConversationId = id;
    lastGroupMessagesJson = "";
    document.getElementById("groupPlaceholder").style.display = "none";
    document.getElementById("groupMainArea").style.display = "flex";
    
    document.querySelectorAll("#groupList .chat-list-item").forEach(item => {
        item.classList.remove("active");
    });
    
    try {
        await apiCall(`/chat/conversations/${id}/read`, "POST");
    } catch(e) {}
    
    if (typeof clearConversationNotifications === "function") {
        clearConversationNotifications(id);
    }
    
    const actionsArea = document.getElementById("groupActionsArea");
    if (actionsArea) {
        actionsArea.innerHTML = `
            <button type="button" onclick="openAddMemberModal(${id})" class="btn-primary" style="padding:7px 14px; font-size:12px; font-weight:700; height:auto; border-radius:8px; display:inline-flex; align-items:center; gap:6px; margin:0; background:linear-gradient(135deg, #10b981 0%, #059669 100%); border:none; box-shadow:0 2px 8px rgba(16,185,129,0.25);" title="Add Team Members">
                <span style="font-size:14px;">+</span> Add Member
            </button>
        `;
    }
    
    await refreshGroupThread(true);
    await refreshGroupList();
}

/**
 * Queries group chat messages and renders messages with file attachments + member management.
 */
async function refreshGroupThread(forceScroll = false) {
    if (!activeGroupConversationId) return;
    try {
        const res = await apiCall(`/chat/conversations/${activeGroupConversationId}/messages`);
        
        const messagesJson = JSON.stringify(res.messages) + "||" + JSON.stringify(res.members);
        if (messagesJson === lastGroupMessagesJson && !forceScroll) {
            return;
        }
        lastGroupMessagesJson = messagesJson;

        const membersToRender = res.members || [];
        const membersCount = membersToRender.length;
        const onlineCount = membersToRender.filter(m => m.is_online === true || m.is_online === 'true' || m.is_online === 1).length;
        const groupTitleElem = document.getElementById("groupActiveTitle") || document.getElementById("groupTitleHeader");
        const isCanDelete = currentUser.role === 'admin' || currentUser.role === 'team_leader' || currentUser.is_team_leader || (res.conversation && res.conversation.created_by === currentUser.id);
        
        const deleteBtnHtml = isCanDelete ? `
            <button type="button" onclick="deleteCurrentGroup(${activeGroupConversationId})" class="btn-action btn-reject" style="padding:6px 12px; font-size:11.5px; height:auto; border-radius:8px; display:inline-flex; align-items:center; gap:4px; margin:0;" title="Delete Group">
                🗑️ Delete
            </button>
        ` : '';

        if (groupTitleElem) {
            groupTitleElem.innerHTML = `
                <div class="title-area" style="display:flex; justify-content:space-between; align-items:center; width:100%; gap:12px;">
                    <div>
                        <h3 style="margin: 0; font-size: 17px; font-weight: 700; color: #fff; display:flex; align-items:center; gap:8px;">
                            <span>👥</span> ${escapeHTML((res.conversation && res.conversation.group_name) || 'Group Chat')}
                        </h3>
                        <div class="meta" style="font-size: 11.5px; color: var(--ink-soft); margin-top: 3px;">
                            ${membersCount} ${membersCount === 1 ? 'member' : 'members'} &bull; <span style="color:#10b981;">● ${onlineCount} online</span>
                        </div>
                    </div>
                    ${deleteBtnHtml}
                </div>
            `;
        }
        
        const messagesDiv = document.getElementById("groupMessages");
        const isAtBottom = messagesDiv.scrollHeight - messagesDiv.clientHeight <= messagesDiv.scrollTop + 40;
        
        messagesDiv.innerHTML = "";
        
        if (res.messages.length === 0) {
            messagesDiv.innerHTML = `
                <div style="padding:40px 20px; text-align:center; color:var(--ink-soft); margin:auto;">
                    <div style="font-size:36px; margin-bottom:10px;">👋</div>
                    <div style="font-size:15px; font-weight:600; color:#fff;">Welcome to ${(res.conversation && res.conversation.group_name) || 'Group Chat'}!</div>
                    <div style="font-size:12px; margin-top:4px;">Start collaborating by sending a message or sharing files below.</div>
                </div>
            `;
        } else {
            res.messages.forEach(m => {
                const isMine = m.sender_id === currentUser.id;
                const bubbleClass = isMine ? 'outgoing' : 'incoming';
                const senderHtml = isMine ? '' : `<div class="sender" style="font-weight:700; color:#60a5fa; margin-bottom:4px; font-size:12px;">${escapeHTML(m.sender_name)}</div>`;
                const timeStr = formatToIST(m.sent_at);
                const attachmentHtml = renderMessageAttachment(m);
                const bodyHtml = m.content ? `<div>${formatMessageBody(m.content)}</div>` : '';
                
                messagesDiv.innerHTML += `
                    <div class="msg-bubble ${bubbleClass}">
                        ${senderHtml}
                        ${bodyHtml}
                        ${attachmentHtml}
                        <div class="time">${timeStr}</div>
                    </div>
                `;
            });
        }
        
        if (forceScroll || isAtBottom) {
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        const membersList = document.getElementById("groupMembersList");
        if (membersList) {
            membersList.innerHTML = "";
            
            // Add top quick Add Member button in pane
            membersList.innerHTML += `
                <button type="button" onclick="openAddMemberModal(${activeGroupConversationId})" style="background:rgba(16,185,129,0.12); border:1px dashed rgba(16,185,129,0.4); color:#34d399; font-weight:600; font-size:12px; padding:8px 12px; border-radius:10px; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:6px; margin-bottom:6px; transition:all 0.2s;" onmouseover="this.style.background='rgba(16,185,129,0.2)'" onmouseout="this.style.background='rgba(16,185,129,0.12)'">
                    <span>+</span> Add Team Member
                </button>
            `;

            if (membersToRender.length === 0) {
                membersList.innerHTML += `<div style="padding:12px; color:var(--ink-soft); font-size:12px; text-align:center;">No members listed.</div>`;
            } else {
                membersToRender.forEach(m => {
                    const roleBadge = (m.role === 'admin' || m.role === 'team_leader') 
                        ? `<span style="font-size:9.5px; background:rgba(255,122,0,0.15); color:var(--orange); border:1px solid rgba(255,122,0,0.3); padding:1px 5px; border-radius:4px; margin-left:4px; font-weight:700;">${m.role === 'team_leader' ? 'TL' : 'ADMIN'}</span>` 
                        : '';
                    const isOnline = m.is_online === true || m.is_online === 'true' || m.is_online === 1;
                    const statusDot = isOnline 
                        ? '<span style="color:#10b981; font-size:10.5px; display:inline-flex; align-items:center; gap:3px;"><span style="width:6px; height:6px; border-radius:50%; background:#10b981;"></span> Online</span>' 
                        : '<span style="color:var(--ink-soft); font-size:10.5px; display:inline-flex; align-items:center; gap:3px;"><span style="width:6px; height:6px; border-radius:50%; background:#64748b;"></span> Offline</span>';

                    const canRemoveMember = isCanDelete && m.id !== currentUser.id;
                    const removeBtnHtml = canRemoveMember ? `
                        <button type="button" onclick="removeGroupMember(${activeGroupConversationId}, ${m.id}, '${escapeHTML(m.name).replace(/'/g, "\\'")}')" style="background:none; border:none; color:#ef4444; font-size:13px; cursor:pointer; padding:2px 6px; border-radius:4px; opacity:0.7; transition:opacity 0.2s;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.7'" title="Remove from group">
                            ✕
                        </button>
                    ` : '';

                    const avatarHtml = getUserAvatarHtml(m.name, 28, isOnline);

                    membersList.innerHTML += `
                        <div class="member-card" style="display:flex; justify-content:space-between; align-items:center; padding:8px 10px; background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); border-radius:10px;">
                            <div style="display:flex; align-items:center; gap:8px; min-width:0;">
                                ${avatarHtml}
                                <div style="min-width:0;">
                                    <div class="name" style="font-weight:600; font-size:12px; color:#fff; display:flex; align-items:center; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">
                                        ${escapeHTML(m.name)} ${roleBadge}
                                    </div>
                                    <div class="status" style="margin-top:2px;">${statusDot}</div>
                                </div>
                            </div>
                            <div>${removeBtnHtml}</div>
                        </div>
                    `;
                });
            }
        }
    } catch(e) {
        console.error(e);
    }
}

async function removeGroupMember(groupId, userId, name) {
    if (!confirm(`Are you sure you want to remove ${name} from this group?`)) return;
    try {
        await apiCall(`/chat/groups/${groupId}/members/${userId}`, "DELETE");
        await refreshGroupThread(false);
    } catch(err) {
        alert(err.message || "Failed to remove member.");
    }
}

// Helper to generate consistent avatar initials & gradient background
function getUserAvatarHtml(name, size = 36, isOnline = false) {
    const initials = (name || '?')
        .split(' ')
        .filter(Boolean)
        .map(w => w[0])
        .slice(0, 2)
        .join('')
        .toUpperCase();

    // Deterministic gradient based on name hash
    const colors = [
        ['#3b82f6', '#1d4ed8'],
        ['#10b981', '#047857'],
        ['#f59e0b', '#b45309'],
        ['#8b5cf6', '#6d28d9'],
        ['#ec4899', '#be185d'],
        ['#06b6d4', '#0e7490']
    ];
    let hash = 0;
    for (let i = 0; i < (name || '').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    const pair = colors[Math.abs(hash) % colors.length];

    const onlineDot = isOnline 
        ? `<span style="position:absolute; bottom:0; right:0; width:10px; height:10px; border-radius:50%; background:#10b981; border:2px solid #0c1222;"></span>` 
        : '';

    return `
        <div style="position:relative; width:${size}px; height:${size}px; flex-shrink:0;">
            <div style="width:${size}px; height:${size}px; border-radius:50%; background:linear-gradient(135deg, ${pair[0]}, ${pair[1]}); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:${size * 0.38}px; letter-spacing:0.5px; box-shadow:0 2px 8px rgba(0,0,0,0.3);">
                ${initials}
            </div>
            ${onlineDot}
        </div>
    `;
}

/**
 * Launches modal dialog for creating a new workspace group channel.
 */
let createGroupUsersList = [];

async function openCreateGroupModal() {
    if (document.getElementById("newGroupName")) document.getElementById("newGroupName").value = "";
    if (document.getElementById("createGroupSearchInput")) document.getElementById("createGroupSearchInput").value = "";
    if (document.getElementById("selectedMemberCount")) document.getElementById("selectedMemberCount").textContent = "0 selected";
    
    openModal("createGroupModal");
    
    const container = document.getElementById("createGroupMembersList");
    if (!container) return;
    container.innerHTML = '<div style="padding:20px; text-align:center; color:var(--ink-soft); font-size:13px;">Loading colleagues directory...</div>';
    
    try {
        allUsers = await apiCall("/chat/users");
        createGroupUsersList = allUsers || [];
        renderCreateGroupMembersList(createGroupUsersList);
    } catch(e) {
        container.innerHTML = '<div style="padding:20px; text-align:center; color:#ef4444; font-size:13px;">Failed to load users list.</div>';
    }
}

function filterCreateGroupMembers() {
    const q = (document.getElementById("createGroupSearchInput") ? document.getElementById("createGroupSearchInput").value : "").toLowerCase();
    const filtered = createGroupUsersList.filter(u => 
        (u.name || '').toLowerCase().includes(q) || 
        (u.email || '').toLowerCase().includes(q) ||
        (u.role || '').toLowerCase().includes(q)
    );
    renderCreateGroupMembersList(filtered);
}

function renderCreateGroupMembersList(list) {
    const container = document.getElementById("createGroupMembersList");
    if (!container) return;
    container.innerHTML = "";

    if (list.length === 0) {
        container.innerHTML = '<div style="padding:20px; text-align:center; color:var(--ink-soft); font-size:12.5px;">No colleagues found.</div>';
        return;
    }

    list.forEach(u => {
        const isOnline = u.is_online === true || u.is_online === 'true' || u.is_online === 1;
        const roleLabel = (u.role === 'admin' || u.role === 'team_leader') ? `<span style="font-size:10px; background:rgba(255,122,0,0.15); color:var(--orange); border:1px solid rgba(255,122,0,0.3); padding:1px 6px; border-radius:100px; margin-left:6px; font-weight:700;">${u.role.toUpperCase()}</span>` : '';
        const avatarHtml = getUserAvatarHtml(u.name, 32, isOnline);

        container.innerHTML += `
            <label style="display:flex; align-items:center; justify-content:space-between; padding:8px 12px; background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); border-radius:10px; cursor:pointer; gap:10px; transition:all 0.2s ease;" onmouseover="this.style.background='rgba(255,255,255,0.07)'" onmouseout="this.style.background='rgba(255,255,255,0.03)'">
                <div style="display:flex; align-items:center; gap:10px; flex:1; min-width:0;">
                    ${avatarHtml}
                    <div style="flex:1; min-width:0; text-align:left;">
                        <div style="font-weight:600; font-size:13px; color:#fff; display:flex; align-items:center; gap:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                            <span>${escapeHTML(u.name)}</span>
                            ${roleLabel}
                        </div>
                        <div style="font-size:11px; color:var(--ink-soft); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px;">${escapeHTML(u.email)}</div>
                    </div>
                </div>
                <input type="checkbox" name="groupMember" value="${u.id}" onchange="updateCreateGroupSelectedCount()" style="width:16px; height:16px; accent-color:var(--orange); cursor:pointer; flex-shrink:0;" />
            </label>
        `;
    });
}

function updateCreateGroupSelectedCount() {
    const checked = document.querySelectorAll('#createGroupMembersList input[type="checkbox"]:checked');
    const badge = document.getElementById("selectedMemberCount");
    if (badge) badge.textContent = `${checked.length} selected`;
}

async function submitCreateGroup(e) {
    if (e) e.preventDefault();
    const name = document.getElementById("newGroupName").value.trim();
    if (!name) {
        alert("Please enter a group name");
        return;
    }
    const checkboxes = document.querySelectorAll('#createGroupMembersList input[type="checkbox"]:checked');
    const memberIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    try {
        const res = await apiCall("/chat/conversations", "POST", {
            type: "group",
            name: name,
            member_ids: memberIds
        });
        closeModal("createGroupModal");
        await refreshGroupList();
        await selectGroupConversation(res.id, name);
    } catch(err) {
        alert(err.message || "Failed to create group.");
    }
}

// =========================================================================
// ADD MEMBERS TO EXISTING GROUP MODAL
// =========================================================================

let activeAddGroupMembersList = [];

async function openAddMemberModal(groupId) {
    if (!groupId) groupId = activeGroupConversationId;
    if (!groupId) {
        alert("Please select a group first.");
        return;
    }
    
    openModal("addGroupMemberModal");
    
    const container = document.getElementById("addGroupMembersList");
    if (container) {
        container.innerHTML = '<div style="padding:24px; text-align:center; color:var(--ink-soft); font-size:13px;"><span style="display:inline-block; animation:spin 1s linear infinite;">⏳</span> Loading colleagues directory...</div>';
    }
    if (document.getElementById("addMemberSearchInput")) {
        document.getElementById("addMemberSearchInput").value = "";
    }
    
    try {
        const res = await apiCall(`/chat/conversations/${groupId}/messages`);
        const existingMemberIds = new Set((res.members || []).map(m => m.id));
        
        allUsers = await apiCall("/chat/users");
        activeAddGroupMembersList = (allUsers || []).filter(u => !existingMemberIds.has(u.id));
        
        renderAddGroupMembersList(activeAddGroupMembersList);
    } catch(e) {
        console.error("Error loading colleagues for group:", e);
        if (container) {
            container.innerHTML = '<div style="padding:24px; text-align:center; color:#ef4444; font-size:13px;">Failed to load employees. Please try again.</div>';
        }
    }
}

function filterAddGroupMembers() {
    const q = (document.getElementById("addMemberSearchInput") ? document.getElementById("addMemberSearchInput").value : "").toLowerCase();
    const filtered = activeAddGroupMembersList.filter(u => 
        (u.name || '').toLowerCase().includes(q) || 
        (u.email || '').toLowerCase().includes(q) ||
        (u.role || '').toLowerCase().includes(q)
    );
    renderAddGroupMembersList(filtered);
}

function renderAddGroupMembersList(list) {
    const container = document.getElementById("addGroupMembersList");
    if (!container) return;
    container.innerHTML = "";

    if (list.length === 0) {
        container.innerHTML = `
            <div style="padding:30px 15px; text-align:center; color:var(--ink-soft);">
                <div style="font-size:28px; margin-bottom:8px;">✨</div>
                <div style="font-size:13px; font-weight:600; color:#fff;">All eligible colleagues are already in this group!</div>
                <div style="font-size:11.5px; color:var(--ink-soft); margin-top:4px;">Everyone on your team has been added.</div>
            </div>
        `;
        return;
    }

    list.forEach(u => {
        const isOnline = u.is_online === true || u.is_online === 'true' || u.is_online === 1;
        const roleLabel = (u.role === 'admin' || u.role === 'team_leader') ? `<span style="font-size:9.5px; background:rgba(255,122,0,0.15); color:var(--orange); border:1px solid rgba(255,122,0,0.3); padding:1px 5px; border-radius:4px; margin-left:6px; font-weight:700;">${u.role.toUpperCase()}</span>` : '';
        const avatarHtml = getUserAvatarHtml(u.name, 36, isOnline);

        container.innerHTML += `
            <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:rgba(255,255,255,0.03); border:1px solid var(--glass-border); border-radius:12px; margin-bottom:6px; gap:12px; transition:all 0.2s ease;" onmouseover="this.style.background='rgba(255,255,255,0.07)'" onmouseout="this.style.background='rgba(255,255,255,0.03)'">
                <div style="display:flex; align-items:center; gap:12px; flex:1; min-width:0;">
                    ${avatarHtml}
                    <div style="flex:1; min-width:0; text-align:left;">
                        <div style="font-weight:600; font-size:13.5px; color:#ffffff; line-height:1.3; display:flex; align-items:center; gap:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                            <span>${escapeHTML(u.name)}</span>
                            ${roleLabel}
                        </div>
                        <div style="font-size:11.5px; color:#94a3b8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px;">
                            ${escapeHTML(u.email)}
                        </div>
                    </div>
                </div>
                <button type="button" onclick="addGroupMember(${activeGroupConversationId}, ${u.id}, this)" style="width:auto !important; min-width:76px; height:32px; padding:0 14px !important; font-size:12px !important; font-weight:700 !important; border-radius:8px !important; background:linear-gradient(135deg, #10b981 0%, #059669 100%) !important; color:#ffffff !important; border:none !important; display:inline-flex !important; align-items:center !important; justify-content:center !important; gap:4px; flex-shrink:0 !important; cursor:pointer !important; box-shadow:0 2px 8px rgba(16,185,129,0.25);">
                    <span style="font-size:14px; font-weight:bold;">+</span> Add
                </button>
            </div>
        `;
    });
}

async function addGroupMember(groupId, userId, btn) {
    if (!groupId) groupId = activeGroupConversationId;
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span>⏳</span> Adding...`;
    }
    try {
        await apiCall(`/chat/groups/${groupId}/members`, "POST", { user_id: userId });
        activeAddGroupMembersList = activeAddGroupMembersList.filter(u => u.id !== userId);
        renderAddGroupMembersList(activeAddGroupMembersList);
        await refreshGroupThread(false);
        if (typeof showGlobalAlert === "function") {
            showGlobalAlert("Member Added", "Team member joined the group successfully!", "success");
        }
    } catch(e) {
        alert(e.message || "Failed to add member.");
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<span>+</span> Add`;
        }
    }
}

/**
 * Initializes the Oversight (Team Leader & Admin Audit) interface panel.
 */
async function loadOversightPanel() {
    activeOversightConversationId = null;
    activeOversightType = null;
    document.getElementById("oversightMainArea").style.display = "none";
    document.getElementById("oversightPlaceholder").style.display = "flex";
    
    await refreshOversightList();
}

/**
 * Pulls all workspace conversations for oversight review.
 */
async function refreshOversightList() {
    try {
        const res = currentUser.role === 'admin' 
            ? await apiCall("/chat/admin/all")
            : await apiCall("/chat/team-leader/groups");
            
        const container = document.getElementById("oversightList");
        container.innerHTML = "";
        
        if (!res || res.length === 0) {
            container.innerHTML = `<div style="padding:20px; color:var(--ink-soft); font-size:12px; text-align:center;">No monitored conversations available.</div>`;
            return;
        }
        
        res.forEach(c => {
            const isSelected = activeOversightConversationId === c.id;
            const lastMsg = c.last_message ? c.last_message : 'No messages yet';
            const icon = c.type === 'group' ? '👥' : '💬';
            
            container.innerHTML += `
                <div class="chat-list-item ${isSelected ? 'active' : ''}" onclick="selectOversightConversation(${c.id}, '${c.type}', '${c.name.replace(/'/g, "\\'")}')">
                    <div>
                        <div class="title">${icon} ${escapeHTML(c.name)}</div>
                        <div class="subtitle">${escapeHTML(lastMsg)}</div>
                    </div>
                </div>
            `;
        });
    } catch (e) {
        console.error("Oversight list error", e);
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
            const timeStr = formatToIST(m.sent_at);
            const attachmentHtml = renderMessageAttachment(m);
            const bodyHtml = m.content ? `<div>${formatMessageBody(m.content)}</div>` : '';
            messagesDiv.innerHTML += `
                <div class="msg-bubble incoming" style="align-self: flex-start; max-width: 80%;">
                    <div class="sender" style="color: var(--orange);">${escapeHTML(m.sender_name)}</div>
                    ${bodyHtml}
                    ${attachmentHtml}
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
                        <div class="name">${escapeHTML(m.name)} ${roleBadge}</div>
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

async function deleteCurrentGroup(convId) {
    if (!convId) return;
    if (!confirm("Are you sure you want to delete this group chat? All messages and members will be removed.")) return;
    
    try {
        await apiCall(`/chat/conversations/${convId}`, "DELETE");
        activeGroupConversationId = null;
        lastGroupMessagesJson = "";
        const activeGroupHeader = document.getElementById("groupActiveTitle");
        if (activeGroupHeader) activeGroupHeader.innerHTML = "<h3 style='margin:0; font-size:16px; color:var(--ink-soft);'>Select a group to start chatting</h3>";
        const groupMsgs = document.getElementById("groupMessages");
        if (groupMsgs) groupMsgs.innerHTML = "";
        await refreshGroupList();
    } catch (err) {
        alert(err.message || "Failed to delete group.");
    }
}
