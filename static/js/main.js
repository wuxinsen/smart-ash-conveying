/* 智慧输灰 - JS 工具库 */

/** 更新时间显示 */
function updateClock() {
    const el = document.getElementById('clock');
    if (!el) return;
    const now = new Date();
    el.textContent = now.toLocaleString('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }).replace(/\//g, '-');
}
setInterval(updateClock, 1000);

document.addEventListener('DOMContentLoaded', function () {
    // 侧边栏切换
    const sidebar = document.getElementById('sidebar');
    const header = document.getElementById('header');
    const content = document.getElementById('content');
    const toggleBtn = document.getElementById('toggle-btn');
    const collapseBtn = document.getElementById('collapse-btn');

    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        sidebar?.classList.add('collapsed');
        header?.classList.add('collapsed');
        content?.classList.add('collapsed');
    }

    toggleBtn?.addEventListener('click', function () {
        sidebar?.classList.toggle('collapsed');
        header?.classList.toggle('collapsed');
        content?.classList.toggle('collapsed');
        localStorage.setItem('sidebarCollapsed', sidebar?.classList.contains('collapsed'));
    });
    collapseBtn?.addEventListener('click', function () {
        sidebar?.classList.add('collapsed');
        header?.classList.add('collapsed');
        content?.classList.add('collapsed');
        localStorage.setItem('sidebarCollapsed', 'true');
    });

    // 菜单点击导航
    document.querySelectorAll('.ics-menu-item[data-target]').forEach(function (el) {
        el.addEventListener('click', function () {
            window.location.href = this.getAttribute('data-target');
        });
    });
});

/** 通用 fetch 封装 */
function api(url) {
    return fetch(url).then(function (r) { return r.json(); });
}

/** 渲染加载状态 */
function loadingHtml() {
    return '<div class="loading"><i class="fas fa-spinner fa-pulse"></i> 加载中...</div>';
}
