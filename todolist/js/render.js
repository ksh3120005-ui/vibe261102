(function (App) {
  'use strict';

  const { formatDate } = App.utils;

  const PRIORITY_LABEL = { high: '높음', medium: '보통', low: '낮음' };
  const EMPTY_TEXT = {
    all: '오늘 할 일을 추가해보세요',
    active: '진행 중인 할일이 없어요',
    done: '아직 완료한 할일이 없어요',
  };
  const THEME_LABEL = { system: '시스템', light: '라이트', dark: '다크' };
  const EDIT_ROLES = ['edit-input', 'edit-priority', 'save', 'cancel'];

  // 고정된 아이콘 마크업 (사용자 입력은 절대 innerHTML로 넣지 않는다)
  const ICONS = {
    edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/></svg>',
    grip: '<svg viewBox="0 0 12 16" fill="currentColor" aria-hidden="true"><circle cx="3" cy="3" r="1.5"/><circle cx="9" cy="3" r="1.5"/><circle cx="3" cy="8" r="1.5"/><circle cx="9" cy="8" r="1.5"/><circle cx="3" cy="13" r="1.5"/><circle cx="9" cy="13" r="1.5"/></svg>',
    system: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
    light: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    dark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>',
  };

  let els = null;

  function init() {
    const $ = (sel) => document.querySelector(sel);
    els = {
      today: $('#today'),
      progress: $('#progress'),
      progressBar: $('#progress-bar'),
      progressText: $('#progress-text'),
      celebrate: $('#celebrate'),
      storageWarning: $('#storage-warning'),
      carryover: $('#carryover'),
      carryoverText: $('#carryover-text'),
      themeToggle: $('#theme-toggle'),
      filters: document.querySelectorAll('.filter'),
      counts: document.querySelectorAll('[data-count]'),
      list: $('#todo-list'),
      empty: $('#empty'),
      clearCompleted: $('#clear-completed'),
      newInput: $('#new-todo'),
    };
  }

  function el(tag, className, props) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (props) Object.assign(node, props);
    return node;
  }

  function iconButton(role, icon, label) {
    const btn = el('button', 'icon-btn', { type: 'button', innerHTML: ICONS[icon] });
    btn.dataset.role = role;
    btn.setAttribute('aria-label', label);
    btn.title = label;
    return btn;
  }

  function prioritySelect(value) {
    const select = el('select', 'select');
    select.dataset.role = 'edit-priority';
    select.setAttribute('aria-label', '우선순위');
    Object.keys(PRIORITY_LABEL).forEach((key) => {
      select.append(el('option', '', { value: key, textContent: PRIORITY_LABEL[key], selected: key === value }));
    });
    return select;
  }

  function createEditItem(todo) {
    const li = el('li', 'todo-item editing');
    li.dataset.id = todo.id;
    const input = el('input', 'input', { type: 'text', value: todo.text, maxLength: 100 });
    input.dataset.role = 'edit-input';
    input.setAttribute('aria-label', '할일 내용 수정');
    const save = el('button', 'btn-primary', { type: 'button', textContent: '저장' });
    save.dataset.role = 'save';
    const cancel = el('button', 'btn-ghost', { type: 'button', textContent: '취소' });
    cancel.dataset.role = 'cancel';
    li.append(input, prioritySelect(todo.priority), save, cancel);
    return li;
  }

  function createItem(todo) {
    const li = el('li', 'todo-item' + (todo.completed ? ' done' : ''));
    li.dataset.id = todo.id;
    li.draggable = !todo.completed;

    const grip = el('span', 'grip', { innerHTML: ICONS.grip });
    grip.setAttribute('aria-hidden', 'true');

    const wrap = el('label', 'check-wrap');
    const check = el('input', 'todo-check', { type: 'checkbox', checked: todo.completed });
    check.dataset.role = 'toggle';
    check.setAttribute('aria-label', `${todo.text} 완료`);
    wrap.append(check);

    const label = `우선순위 ${PRIORITY_LABEL[todo.priority]}`;
    const dot = el('span', `priority priority-${todo.priority}`, { title: label });
    dot.setAttribute('role', 'img');
    dot.setAttribute('aria-label', label);

    const text = el('span', 'todo-text', { textContent: todo.text, title: '더블클릭하여 수정' });

    li.append(
      grip,
      wrap,
      dot,
      text,
      iconButton('edit', 'edit', `${todo.text} 수정`),
      iconButton('delete', 'trash', `${todo.text} 삭제`)
    );
    return li;
  }

  function renderHeader(store, stats) {
    const today = store.getToday();
    els.today.textContent = formatDate(today);
    els.today.dateTime = today;

    const percent = stats.total ? Math.round((stats.done / stats.total) * 100) : 0;
    els.progressBar.style.width = `${percent}%`;
    els.progress.setAttribute('aria-valuenow', String(percent));
    els.progressText.textContent = stats.total
      ? `${stats.done} / ${stats.total} 완료`
      : '아직 할일이 없어요';
    els.celebrate.hidden = !(stats.total > 0 && stats.active === 0);
  }

  function renderNotices(store) {
    els.storageWarning.hidden = store.isStorageOk();
    const carry = store.getCarryOverCount();
    els.carryover.hidden = carry === 0;
    els.carryoverText.textContent = `지난날 못 끝낸 할일이 ${carry}개 있어요.`;
  }

  function renderFilters(filter, stats) {
    els.filters.forEach((btn) => {
      btn.setAttribute('aria-pressed', String(btn.dataset.filter === filter));
    });
    els.counts.forEach((node) => {
      node.textContent = stats[node.dataset.count === 'all' ? 'total' : node.dataset.count];
    });
  }

  function renderList(todos, ui, filter) {
    const frag = document.createDocumentFragment();
    todos.forEach((todo) => {
      frag.append(todo.id === ui.editingId ? createEditItem(todo) : createItem(todo));
    });
    els.list.replaceChildren(frag);
    els.empty.hidden = todos.length > 0;
    els.empty.textContent = EMPTY_TEXT[filter];
  }

  function renderTheme(theme) {
    const root = document.documentElement;
    if (theme === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', theme);
    els.themeToggle.innerHTML = ICONS[theme];
    const label = `테마: ${THEME_LABEL[theme]} (클릭하여 변경)`;
    els.themeToggle.setAttribute('aria-label', label);
    els.themeToggle.title = label;
  }

  // 목록을 다시 그려도 키보드 포커스가 같은 항목에 남도록 한다
  function captureFocus() {
    const active = document.activeElement;
    const li = active && active.closest ? active.closest('#todo-list > li') : null;
    if (!li) return null;
    return {
      id: li.dataset.id,
      role: active.dataset.role,
      index: Array.prototype.indexOf.call(els.list.children, li),
    };
  }

  function restoreFocus(focus) {
    if (!focus) return;
    const li = els.list.querySelector(`li[data-id="${CSS.escape(focus.id)}"]`);
    if (li) {
      const role = EDIT_ROLES.includes(focus.role) && !li.classList.contains('editing') ? 'edit' : focus.role;
      const target = li.querySelector(`[data-role="${role}"]`) || li.querySelector('[data-role]');
      if (target) target.focus();
      return;
    }
    // 항목이 사라졌으면(삭제 등) 같은 위치의 다음 항목, 없으면 입력창으로
    const items = els.list.children;
    const next = items[Math.min(focus.index, items.length - 1)];
    const target = next && next.querySelector(`[data-role="${focus.role}"]`);
    (target || els.newInput).focus();
  }

  function render(store, ui) {
    const stats = store.getStats();
    const filter = store.getFilter();
    const focus = captureFocus();
    renderHeader(store, stats);
    renderNotices(store);
    renderFilters(filter, stats);
    renderList(store.getVisibleTodos(), ui, filter);
    els.clearCompleted.disabled = stats.done === 0;
    renderTheme(store.getTheme());
    restoreFocus(focus);
  }

  App.render = { init, render };
})(window.TodoApp = window.TodoApp || {});
