(function (App) {
  'use strict';

  const { store, render, utils } = App;
  const $ = (sel) => document.querySelector(sel);

  const ui = { editingId: null };
  const TOAST_MS = 5000;
  let toastTimer = null;
  let dragId = null;

  function update() {
    render.render(store, ui);
  }

  // ----- 추가 -----

  function bindAddForm() {
    const form = $('#add-form');
    const input = $('#new-todo');
    const priority = $('#new-priority');

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!store.addTodo(input.value, priority.value)) {
        shake(input);
        input.focus();
        return;
      }
      input.value = '';
      priority.value = 'medium';
      // 완료 탭에서는 새 항목이 보이지 않으므로 전체로 전환
      if (store.getFilter() === 'done') store.setFilter('all');
      input.focus();
    });

    input.addEventListener('animationend', () => input.classList.remove('shake'));
  }

  function shake(node) {
    node.classList.remove('shake');
    void node.offsetWidth; // 애니메이션 재시작
    node.classList.add('shake');
  }

  // ----- 수정 -----

  function startEdit(id) {
    ui.editingId = id;
    update();
    const input = $('#todo-list .editing [data-role="edit-input"]');
    if (input) {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
  }

  function commitEdit(li) {
    const id = li.dataset.id;
    if (ui.editingId !== id) return;
    const text = li.querySelector('[data-role="edit-input"]').value.trim();
    const priority = li.querySelector('[data-role="edit-priority"]').value;
    ui.editingId = null;
    // 빈 값으로 저장하면 취소로 처리 (FR-14)
    if (!text || !store.updateTodo(id, { text, priority })) update();
  }

  function cancelEdit() {
    ui.editingId = null;
    update();
  }

  // ----- 삭제 / 실행 취소 -----

  function handleDelete(id) {
    const todo = store.deleteTodo(id);
    if (todo) showToast(`'${utils.truncate(todo.text, 20)}' 삭제됨`);
  }

  function showToast(message) {
    $('#toast-text').textContent = message;
    $('#toast').hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, TOAST_MS);
  }

  function hideToast() {
    clearTimeout(toastTimer);
    $('#toast').hidden = true;
  }

  // ----- 목록 이벤트 (위임) -----

  function bindList() {
    const list = $('#todo-list');

    list.addEventListener('change', (e) => {
      if (e.target.dataset.role !== 'toggle') return;
      store.toggleTodo(e.target.closest('li').dataset.id);
    });

    list.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-role]');
      if (!btn) return;
      const li = btn.closest('li');
      switch (btn.dataset.role) {
        case 'edit': startEdit(li.dataset.id); break;
        case 'delete': handleDelete(li.dataset.id); break;
        case 'save': commitEdit(li); break;
        case 'cancel': cancelEdit(); break;
      }
    });

    // 저장/취소 버튼을 누를 때 입력창 blur로 먼저 저장되지 않도록
    list.addEventListener('mousedown', (e) => {
      const role = e.target.closest('[data-role]')?.dataset.role;
      if (role === 'save' || role === 'cancel') e.preventDefault();
    });

    list.addEventListener('dblclick', (e) => {
      const text = e.target.closest('.todo-text');
      if (text) startEdit(text.closest('li').dataset.id);
    });

    list.addEventListener('keydown', (e) => {
      if (e.isComposing || e.keyCode === 229) return; // 한글 조합 중 입력 무시
      const li = e.target.closest('li');
      if (!li) return;
      const role = e.target.dataset.role;

      if (li.classList.contains('editing')) {
        if (e.key === 'Escape') {
          e.preventDefault();
          cancelEdit();
        } else if (e.key === 'Enter' && role === 'edit-input') {
          e.preventDefault();
          commitEdit(li);
        }
        return;
      }

      if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
        e.preventDefault();
        store.moveBy(li.dataset.id, e.key === 'ArrowUp' ? -1 : 1);
      }
    });

    // 편집 중인 항목 밖으로 포커스가 나가면 저장
    list.addEventListener('focusout', (e) => {
      const li = e.target.closest('li.editing');
      if (li && !li.contains(e.relatedTarget)) commitEdit(li);
    });

    bindDrag(list);
  }

  // ----- 드래그 정렬 -----

  function clearDropMarks(list) {
    list.querySelectorAll('.drop-target, .dragging').forEach((n) => {
      n.classList.remove('drop-target', 'dragging');
    });
  }

  function bindDrag(list) {
    list.addEventListener('dragstart', (e) => {
      const li = e.target.closest('li[draggable="true"]');
      if (!li || ui.editingId) {
        e.preventDefault();
        return;
      }
      dragId = li.dataset.id;
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', dragId);
      li.classList.add('dragging');
    });

    list.addEventListener('dragover', (e) => {
      const li = e.target.closest('li');
      list.querySelectorAll('.drop-target').forEach((n) => {
        if (n !== li) n.classList.remove('drop-target');
      });
      if (!dragId || !li || !store.canReorder(dragId, li.dataset.id)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      li.classList.add('drop-target');
    });

    list.addEventListener('drop', (e) => {
      const li = e.target.closest('li');
      e.preventDefault();
      if (dragId && li) store.reorder(dragId, li.dataset.id);
      clearDropMarks(list);
    });

    list.addEventListener('dragend', () => {
      dragId = null;
      clearDropMarks(list);
    });
  }

  // ----- 기타 컨트롤 -----

  function bindControls() {
    document.querySelectorAll('.filter').forEach((btn) => {
      btn.addEventListener('click', () => store.setFilter(btn.dataset.filter));
    });

    $('#clear-completed').addEventListener('click', () => {
      const { done } = store.getStats();
      if (done && window.confirm(`완료된 할일 ${done}개를 지울까요?`)) {
        store.clearCompleted();
        hideToast();
      }
    });

    $('#toast-undo').addEventListener('click', () => {
      store.undoDelete();
      hideToast();
    });

    $('#carryover-btn').addEventListener('click', () => store.carryOver());

    $('#theme-toggle').addEventListener('click', () => {
      const themes = store.THEMES;
      const next = themes[(themes.indexOf(store.getTheme()) + 1) % themes.length];
      store.setTheme(next);
    });
  }

  function bindWindow() {
    // 다른 탭에서 변경된 내용 반영
    window.addEventListener('storage', (e) => {
      if (e.key === null || e.key.startsWith('todolist.v1.')) store.reloadFromStorage();
    });
    // 자정이 지난 뒤 돌아왔을 때 날짜 갱신
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') store.checkDate();
    });
    window.addEventListener('focus', () => store.checkDate());
    setInterval(() => store.checkDate(), 60 * 1000);
  }

  function init() {
    store.load();
    render.init();
    store.subscribe(update);
    bindAddForm();
    bindList();
    bindControls();
    bindWindow();
    update();
  }

  init();
})(window.TodoApp = window.TodoApp || {});
