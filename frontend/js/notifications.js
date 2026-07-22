/**
 * @file notifications.js
 * @description Real-time notifications engine for ElevateIQ.
 * Aggregates announcements, chat messages, leave applications, and support tickets,
 * providing real-time toast banners, unread badge counts, dropdown history, and instant click redirection.
 */

let systemNotifications = [];
let initializedNotifs = false;

function getStorageKey() {
    return `elevateiq_notifs_${(typeof currentUser !== 'undefined' && currentUser) ? currentUser.id : 'guest'}`;
}

function loadSavedNotifications() {
    try {
        const raw = localStorage.getItem(getStorageKey());
        if (raw) {
            systemNotifications = JSON.parse(raw);
        }
    } catch(e) {
        systemNotifications = [];
    }
    renderNotificationsUI();
}

function saveNotifications() {
    try {
        localStorage.setItem(getStorageKey(), JSON.stringify(systemNotifications.slice(0, 50)));
    } catch(e) {}
}

function addNotification(notif, shouldToast = false) {
    notif.id = notif.id || 'notif_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
    notif.time = notif.time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (typeof notif.isRead === 'undefined') {
        notif.isRead = false;
    }

    // Check duplicate by ID or title & message
    const existingIndex = systemNotifications.findIndex(n => n.id === notif.id || (n.title === notif.title && n.message === notif.message));
    if (existingIndex !== -1) {
        return;
    }

    systemNotifications.unshift(notif);
    if (systemNotifications.length > 60) systemNotifications.pop();

    saveNotifications();
    renderNotificationsUI();

    if (shouldToast) {
        showToastNotification(notif);
    }
}

function renderNotificationsUI() {
    const badge = document.getElementById("navNotificationBadge");
    const container = document.getElementById("notificationItemsList");
    if (!badge || !container) return;

    const unreadCount = systemNotifications.filter(n => !n.isRead).length;

    if (unreadCount > 0) {
        badge.textContent = unreadCount > 99 ? '99+' : unreadCount;
        badge.style.display = "inline-block";
    } else {
        badge.style.display = "none";
    }

    container.innerHTML = "";
    if (systemNotifications.length === 0) {
        container.innerHTML = `<div style="text-align:center; color:var(--ink-soft); font-size:12.5px; padding:20px 10px;">No notifications yet</div>`;
        return;
    }

    systemNotifications.forEach(n => {
        const bg = n.isRead ? 'rgba(255,255,255,0.02)' : 'rgba(255,122,0,0.08)';
        const border = n.isRead ? 'var(--glass-border)' : 'rgba(255,122,0,0.3)';
        const unreadDot = n.isRead ? '' : `<span style="width:7px; height:7px; border-radius:50%; background:var(--orange); display:inline-block; margin-left:4px;"></span>`;

        container.innerHTML += `
            <div onclick="clickNotificationItem('${n.id}')" style="background:${bg}; border:1px solid ${border}; padding:10px 12px; border-radius:12px; cursor:pointer; transition:all 0.2s ease; display:flex; gap:10px; align-items:flex-start;" onmouseover="this.style.background='rgba(255,255,255,0.08)'" onmouseout="this.style.background='${bg}'">
                <div style="font-size:18px; line-height:1; flex-shrink:0;">${n.icon || '🔔'}</div>
                <div style="flex:1; min-width:0;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:12.5px; font-weight:700; color:#fff; display:flex; align-items:center;">${escapeHTML(n.title)} ${unreadDot}</span>
                        <span style="font-size:10px; color:var(--ink-soft); flex-shrink:0; margin-left:6px;">${n.time}</span>
                    </div>
                    <div style="font-size:11.5px; color:var(--ink-soft); margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHTML(n.message)}</div>
                </div>
            </div>
        `;
    });
}

function toggleNotificationsMenu(e) {
    if (e) e.stopPropagation();
    const dropdown = document.getElementById("notificationDropdown");
    if (!dropdown) return;

    if (dropdown.style.display === "none" || !dropdown.style.display) {
        dropdown.style.display = "block";
    } else {
        dropdown.style.display = "none";
    }
}

function markAllNotificationsRead() {
    systemNotifications.forEach(n => n.isRead = true);
    saveNotifications();
    renderNotificationsUI();
}

function clickNotificationItem(notifId) {
    const notif = systemNotifications.find(n => n.id === notifId);
    if (notif) {
        notif.isRead = true;
        saveNotifications();
        renderNotificationsUI();

        const dropdown = document.getElementById("notificationDropdown");
        if (dropdown) dropdown.style.display = "none";

        handleNotificationRedirect(notif);
    }
}

function handleNotificationRedirect(notif) {
    if (!notif) return;
    const target = notif.targetView || '';
    if (!target) return;

    // Map role-specific view panel IDs
    let targetView = target;
    if (typeof currentUser !== 'undefined' && currentUser) {
        if (currentUser.role === 'employee' || currentUser.role === 'team_leader') {
            if (target === 'announcements') targetView = 'emp_announcements';
            if (target === 'messages') targetView = 'messages';
            if (target === 'leaves') targetView = currentUser.can_approve_leaves ? 'leaves' : 'emp_leaves';
            if (target === 'overview') targetView = 'emp_overview';
            if (target === 'attendance') targetView = 'emp_attendance';
        } else if (currentUser.role === 'client') {
            if (target === 'meetings') targetView = 'client_meetings';
            if (target === 'overview') targetView = 'client_overview';
        }
    }

    if (typeof switchTab === 'function') {
        const links = document.querySelectorAll(".sidebar-link");
        let matchedElem = null;
        links.forEach(l => {
            if (l.onclick && l.onclick.toString().includes(`'${targetView}'`)) {
                matchedElem = l;
            }
        });
        switchTab(targetView, matchedElem);
    }

    // Direct message or group chat auto-open handler
    if (notif.extraData && notif.extraData.conversationId) {
        setTimeout(() => {
            if (notif.extraData.type === 'group' && typeof selectGroupConversation === 'function') {
                selectGroupConversation(notif.extraData.conversationId, notif.extraData.name || 'Group Chat');
            } else if (typeof selectDMConversation === 'function') {
                selectDMConversation(notif.extraData.conversationId, notif.extraData.name || 'Chat');
            }
        }, 250);
    }
}

function showToastNotification(notif) {
    let container = document.getElementById("toastNotificationContainer");
    if (!container) {
        container = document.createElement("div");
        container.id = "toastNotificationContainer";
        container.style.cssText = "position:fixed; bottom:24px; right:24px; z-index:999999; display:flex; flex-direction:column; gap:10px; max-width:340px; width:90%; pointer-events:none;";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.style.cssText = "background:#0c1222; border:1px solid rgba(255, 122, 0, 0.5); border-radius:14px; padding:12px 16px; box-shadow:0 10px 25px rgba(0,0,0,0.6); display:flex; gap:12px; align-items:center; cursor:pointer; pointer-events:auto; transform:translateY(20px); opacity:0; transition:all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);";
    
    toast.innerHTML = `
        <div style="font-size:22px; line-height:1; flex-shrink:0;">${notif.icon || '🔔'}</div>
        <div style="flex:1; min-width:0;">
            <div style="font-size:13px; font-weight:700; color:#fff;">${escapeHTML(notif.title)}</div>
            <div style="font-size:11.5px; color:var(--ink-soft); margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHTML(notif.message)}</div>
        </div>
    `;

    toast.onclick = () => {
        handleNotificationRedirect(notif);
        toast.style.opacity = "0";
        toast.style.transform = "translateY(20px)";
        setTimeout(() => toast.remove(), 300);
    };

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "1";
        toast.style.transform = "translateY(0)";
    }, 50);

    setTimeout(() => {
        if (toast.parentNode) {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(20px)";
            setTimeout(() => toast.remove(), 300);
        }
    }, 4500);
}

// Global click outside listener to close dropdown
document.addEventListener("click", (e) => {
    const wrapper = document.getElementById("navNotificationWrapper");
    const dropdown = document.getElementById("notificationDropdown");
    if (wrapper && dropdown && !wrapper.contains(e.target)) {
        dropdown.style.display = "none";
    }
});

// Periodic real-time push polling for announcements, messages, leaves, and tickets
async function pollRealtimeNotifications() {
    if (typeof currentUser === 'undefined' || !currentUser) return;

    try {
        const isFirstRun = !initializedNotifs;

        // 1. Announcements
        const notices = await apiCall("/announcements");
        if (notices && Array.isArray(notices)) {
            notices.forEach((n, idx) => {
                const notifId = `announcement_${n.id}`;
                const timeStr = n.created_at ? new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Recently';
                addNotification({
                    id: notifId,
                    icon: '📢',
                    title: `Announcement: ${n.title}`,
                    message: n.content,
                    category: 'announcement',
                    targetView: 'announcements',
                    time: timeStr
                }, !isFirstRun && idx === 0);
            });
        }

        // 2. Chat Conversations / Messages
        const convs = await apiCall("/chat/conversations");
        if (convs && Array.isArray(convs)) {
            convs.forEach(c => {
                if (c.last_message) {
                    const label = c.type === 'group' ? (c.group_name || 'Group Chat') : (c.dm_user ? c.dm_user.name : 'Direct Message');
                    const notifId = `chat_${c.id}_${c.last_message_id || Date.now()}`;
                    const timeStr = c.last_message_at ? new Date(c.last_message_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Recently';
                    addNotification({
                        id: notifId,
                        icon: '💬',
                        title: `Message in ${label}`,
                        message: c.last_message,
                        category: 'chat',
                        targetView: 'messages',
                        extraData: { conversationId: c.id, type: c.type, name: label },
                        time: timeStr
                    }, !isFirstRun && c.unread_count > 0);
                }
            });
        }

        // 3. Leave Requests
        const leaves = await apiCall(currentUser.role === 'admin' ? "/leaves?scope=all" : "/leaves");
        if (leaves && Array.isArray(leaves)) {
            leaves.forEach(l => {
                const notifId = `leave_${l.id}_${l.status}`;
                const titleStr = currentUser.role === 'admin' ? `Leave Request: ${l.name || l.employee_id}` : `Leave Request Status`;
                const msgStr = `${l.leave_type} Leave (${l.start_date} to ${l.end_date}): ${l.status}`;
                addNotification({
                    id: notifId,
                    icon: '📝',
                    title: titleStr,
                    message: msgStr,
                    category: 'leave',
                    targetView: 'leaves',
                    time: 'Today'
                }, false);
            });
        }

        // 4. Support Tickets
        try {
            const tickets = await apiCall("/api/tickets?portal=elevateiq");
            if (tickets && Array.isArray(tickets)) {
                tickets.forEach(t => {
                    const notifId = `ticket_${t.id}_${t.status}`;
                    addNotification({
                        id: notifId,
                        icon: '🎫',
                        title: `Ticket #${t.id}: ${t.subject}`,
                        message: `Status: ${t.status} | Category: ${t.category}`,
                        category: 'tickets',
                        targetView: 'tickets',
                        time: 'Today'
                    }, false);
                });
            }
        } catch(e) {}

        initializedNotifs = true;
    } catch(e) {
        console.error("Error polling notifications:", e);
    }
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    setTimeout(() => {
        loadSavedNotifications();
        pollRealtimeNotifications();
        setInterval(pollRealtimeNotifications, 10000);
    }, 800);
});
