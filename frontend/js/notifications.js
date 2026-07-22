/**
 * @file notifications.js
 * @description Real-time notifications manager for ElevateIQ.
 * Handles notification badge counters, dropdown menus, toast banners, and click-to-redirect navigation.
 */

let systemNotifications = [];
let lastSeenAnnouncementId = 0;
let lastSeenLeaveCount = -1;
let knownMessageIds = new Set();

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
        localStorage.setItem(getStorageKey(), JSON.stringify(systemNotifications.slice(0, 30)));
    } catch(e) {}
}

function addNotification(notif) {
    // notif: { id, icon, title, message, category, targetView, extraData, time, isRead }
    notif.id = notif.id || 'notif_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
    notif.time = notif.time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    notif.isRead = false;

    // Check duplicate
    const exists = systemNotifications.some(n => n.title === notif.title && n.message === notif.message);
    if (exists) return;

    systemNotifications.unshift(notif);
    if (systemNotifications.length > 40) systemNotifications.pop();

    saveNotifications();
    renderNotificationsUI();
    showToastNotification(notif);
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
        const unreadDot = n.isRead ? '' : `<span style="width:7px; height:7px; border-radius:50%; background:var(--orange); display:inline-block;"></span>`;

        container.innerHTML += `
            <div onclick="clickNotificationItem('${n.id}')" style="background:${bg}; border:1px solid ${border}; padding:10px 12px; border-radius:12px; cursor:pointer; transition:all 0.2s ease; display:flex; gap:10px; align-items:flex-start;" onmouseover="this.style.background='rgba(255,255,255,0.06)'" onmouseout="this.style.background='${bg}'">
                <div style="font-size:18px; line-height:1;">${n.icon || '🔔'}</div>
                <div style="flex:1; min-width:0;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:12.5px; font-weight:700; color:#fff; display:flex; align-items:center; gap:4px;">${escapeHTML(n.title)} ${unreadDot}</span>
                        <span style="font-size:10px; color:var(--ink-soft);">${n.time}</span>
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

        // Target redirection logic
        const dropdown = document.getElementById("notificationDropdown");
        if (dropdown) dropdown.style.display = "none";

        handleNotificationRedirect(notif);
    }
}

function handleNotificationRedirect(notif) {
    if (!notif) return;
    const target = notif.targetView || '';

    // Map role-specific views
    let targetView = target;
    if (currentUser.role === 'employee' || currentUser.role === 'team_leader') {
        if (target === 'announcements') targetView = 'emp_announcements';
        if (target === 'messages') targetView = 'emp_messages';
        if (target === 'leaves') targetView = 'emp_leaves';
        if (target === 'meetings') targetView = 'emp_overview';
    }

    if (typeof switchView === 'function') {
        switchView(targetView);
    }

    // Direct message / group chat open handler
    if (notif.extraData && notif.extraData.conversationId) {
        setTimeout(() => {
            if (notif.extraData.type === 'group' && typeof selectGroupConversation === 'function') {
                selectGroupConversation(notif.extraData.conversationId, notif.extraData.name || 'Group Chat');
            } else if (typeof selectDMConversation === 'function') {
                selectDMConversation(notif.extraData.conversationId, notif.extraData.name || 'Chat');
            }
        }, 300);
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
        <div style="font-size:22px; line-height:1;">${notif.icon || '🔔'}</div>
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

    // Animate in
    setTimeout(() => {
        toast.style.opacity = "1";
        toast.style.transform = "translateY(0)";
    }, 50);

    // Auto dismiss after 4.5s
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

// Periodic real-time push polling for announcements, messages & leaves
async function pollRealtimeNotifications() {
    if (typeof currentUser === 'undefined' || !currentUser) return;

    try {
        // 1. Poll announcements
        const notices = await apiCall("/announcements");
        if (notices && notices.length > 0) {
            const latest = notices[0];
            if (lastSeenAnnouncementId > 0 && latest.id > lastSeenAnnouncementId) {
                addNotification({
                    icon: '📢',
                    title: 'New Announcement',
                    message: latest.title || latest.content,
                    category: 'announcement',
                    targetView: 'announcements'
                });
            }
            lastSeenAnnouncementId = latest.id;
        }

        // 2. Poll unread messages
        const convs = await apiCall("/chat/conversations");
        if (convs && Array.isArray(convs)) {
            convs.forEach(c => {
                if (c.unread_count > 0 && c.last_message) {
                    const label = c.type === 'group' ? (c.group_name || 'Group Chat') : (c.dm_user ? c.dm_user.name : 'Direct Message');
                    addNotification({
                        icon: '💬',
                        title: `Message in ${label}`,
                        message: c.last_message,
                        category: 'chat',
                        targetView: 'messages',
                        extraData: { conversationId: c.id, type: c.type, name: label }
                    });
                }
            });
        }

        // 3. Poll leave applications
        const leaves = await apiCall("/leaves");
        if (leaves && Array.isArray(leaves)) {
            if (lastSeenLeaveCount >= 0 && leaves.length > lastSeenLeaveCount) {
                const latestLeave = leaves[0];
                addNotification({
                    icon: '📝',
                    title: 'Leave Status Update',
                    message: `Leave request status: ${latestLeave.status}`,
                    category: 'leave',
                    targetView: 'leaves'
                });
            }
            lastSeenLeaveCount = leaves.length;
        }
    } catch(e) {}
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    setTimeout(() => {
        loadSavedNotifications();
        pollRealtimeNotifications();
        setInterval(pollRealtimeNotifications, 12000);
    }, 1000);
});
