(function (App) {
  'use strict';

  const { todayKey, uid } = App.utils;

  const KEYS = {
    todos: 'todolist.v1.todos',
    filter: 'todolist.v1.filter',
    theme: 'todolist.v1.theme',
  };
  const MAX_LENGTH = 100;
  const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };
  const FILTERS = ['all', 'active', 'done'];
  const THEMES = ['system', 'light', 'dark'];
  const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

  const state = {
    todos: [],
    filter: 'all',
    theme: 'system',
    today: todayKey(),
    storageOk: true,
  };
  let lastDeleted = null;
  const listeners = [];

  // ----- localStorage 입출력 -----

  function checkStorage() {
    try {
      const key = 'todolist.v1.__test';
      localStorage.setItem(key, '1');
      localStorage.removeItem(key);
      return true;
    } catch (e) {
      return false;
    }
  }

  function readJSON(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch (e) {
      return fallback;
    }
  }

  function writeJSON(key, value) {
    if (!state.storageOk) return;
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      state.storageOk = false;
    }
  }

  // 손상되었거나 형식이 다른 항목은 보정하거나 버린다
  function sanitize(raw) {
    if (!raw || typeof raw !== 'object' || typeof raw.text !== 'string') return null;
    const text = raw.text.trim().slice(0, MAX_LENGTH);
    if (!text) return null;
    const completed = raw.completed === true;
    const createdAt = Number.isFinite(raw.createdAt) ? raw.createdAt : Date.now();
    return {
      id: typeof raw.id === 'string' && raw.id ? raw.id : uid(),
      text,
      completed,
      priority: PRIORITY_RANK[raw.priority] !== undefined ? raw.priority : 'medium',
      date: typeof raw.date === 'string' && DATE_RE.test(raw.date) ? raw.date : state.today,
      createdAt,
      completedAt: completed ? (Number.isFinite(raw.completedAt) ? raw.completedAt : createdAt) : null,
      order: Number.isFinite(raw.order) ? raw.order : createdAt,
    };
  }

  function load() {
    state.storageOk = checkStorage();
    state.today = todayKey();
    const raw = state.storageOk ? readJSON(KEYS.todos, []) : [];
    state.todos = Array.isArray(raw) ? raw.map(sanitize).filter(Boolean) : [];
    const filter = state.storageOk ? readJSON(KEYS.filter, 'all') : 'all';
    state.filter = FILTERS.includes(filter) ? filter : 'all';
    const theme = state.storageOk ? readJSON(KEYS.theme, 'system') : 'system';
    state.theme = THEMES.includes(theme) ? theme : 'system';
  }

  function save() {
    writeJSON(KEYS.todos, state.todos);
  }

  // ----- 구독 -----

  function subscribe(fn) {
    listeners.push(fn);
  }

  function emit() {
    listeners.forEach((fn) => fn());
  }

  function commit() {
    save();
    emit();
  }

  // ----- 조회 -----

  function find(id) {
    return state.todos.find((t) => t.id === id);
  }

  function todayTodos() {
    return state.todos.filter((t) => t.date === state.today);
  }

  function byPriorityThenOrder(a, b) {
    return PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] || a.order - b.order;
  }

  function getVisibleTodos() {
    const list = todayTodos();
    const active = list.filter((t) => !t.completed).sort(byPriorityThenOrder);
    const done = list.filter((t) => t.completed).sort((a, b) => a.completedAt - b.completedAt);
    if (state.filter === 'active') return active;
    if (state.filter === 'done') return done;
    return active.concat(done);
  }

  function getStats() {
    const list = todayTodos();
    const done = list.filter((t) => t.completed).length;
    return { total: list.length, active: list.length - done, done };
  }

  function getCarryOverCount() {
    return state.todos.filter((t) => !t.completed && t.date < state.today).length;
  }

  function nextOrder() {
    return state.todos.reduce((max, t) => Math.max(max, t.order), 0) + 1;
  }

  // ----- 변경 -----

  function addTodo(text, priority) {
    const value = String(text).trim();
    if (!value || value.length > MAX_LENGTH) return false;
    state.todos.push({
      id: uid(),
      text: value,
      completed: false,
      priority: PRIORITY_RANK[priority] !== undefined ? priority : 'medium',
      date: state.today,
      createdAt: Date.now(),
      completedAt: null,
      order: nextOrder(),
    });
    commit();
    return true;
  }

  function toggleTodo(id) {
    const todo = find(id);
    if (!todo) return;
    todo.completed = !todo.completed;
    todo.completedAt = todo.completed ? Date.now() : null;
    commit();
  }

  function updateTodo(id, patch) {
    const todo = find(id);
    if (!todo) return false;
    if ('text' in patch) {
      const value = String(patch.text).trim();
      if (!value || value.length > MAX_LENGTH) return false;
      todo.text = value;
    }
    if (PRIORITY_RANK[patch.priority] !== undefined) todo.priority = patch.priority;
    commit();
    return true;
  }

  function deleteTodo(id) {
    const index = state.todos.findIndex((t) => t.id === id);
    if (index === -1) return null;
    const [todo] = state.todos.splice(index, 1);
    lastDeleted = { todo, index };
    commit();
    return todo;
  }

  function undoDelete() {
    if (!lastDeleted) return;
    const { todo, index } = lastDeleted;
    state.todos.splice(Math.min(index, state.todos.length), 0, todo);
    lastDeleted = null;
    commit();
  }

  function clearCompleted() {
    const before = state.todos.length;
    state.todos = state.todos.filter((t) => !(t.completed && t.date === state.today));
    lastDeleted = null;
    commit();
    return before - state.todos.length;
  }

  function carryOver() {
    const targets = state.todos
      .filter((t) => !t.completed && t.date < state.today)
      .sort((a, b) => a.order - b.order);
    let order = nextOrder();
    targets.forEach((t) => {
      t.date = state.today;
      t.order = order++;
    });
    commit();
    return targets.length;
  }

  // 순서 변경은 같은 날짜·같은 우선순위의 미완료 항목끼리만 허용한다
  function canReorder(id, targetId) {
    const a = find(id);
    const b = find(targetId);
    return Boolean(a && b && a !== b && !a.completed && !b.completed &&
      a.priority === b.priority && a.date === b.date);
  }

  function reorderGroup(todo) {
    return state.todos
      .filter((t) => t.date === todo.date && !t.completed && t.priority === todo.priority)
      .sort((a, b) => a.order - b.order);
  }

  function reorder(id, targetId) {
    if (!canReorder(id, targetId)) return false;
    const todo = find(id);
    const group = reorderGroup(todo);
    const orders = group.map((t) => t.order);
    const from = group.indexOf(todo);
    const to = group.findIndex((t) => t.id === targetId);
    group.splice(from, 1);
    group.splice(to, 0, todo);
    group.forEach((t, i) => { t.order = orders[i]; });
    commit();
    return true;
  }

  function moveBy(id, step) {
    const todo = find(id);
    if (!todo || todo.completed) return false;
    const group = reorderGroup(todo);
    const neighbor = group[group.indexOf(todo) + step];
    return neighbor ? reorder(id, neighbor.id) : false;
  }

  function setFilter(filter) {
    if (!FILTERS.includes(filter)) return;
    state.filter = filter;
    writeJSON(KEYS.filter, filter);
    emit();
  }

  function setTheme(theme) {
    if (!THEMES.includes(theme)) return;
    state.theme = theme;
    writeJSON(KEYS.theme, theme);
    emit();
  }

  // 자정이 지나면 오늘 날짜를 갱신한다
  function checkDate() {
    const key = todayKey();
    if (key === state.today) return false;
    state.today = key;
    emit();
    return true;
  }

  // 다른 탭에서 바뀐 내용을 다시 읽는다
  function reloadFromStorage() {
    load();
    emit();
  }

  App.store = {
    THEMES,
    load,
    subscribe,
    getVisibleTodos,
    getStats,
    getCarryOverCount,
    getFilter: () => state.filter,
    getTheme: () => state.theme,
    getToday: () => state.today,
    isStorageOk: () => state.storageOk,
    addTodo,
    toggleTodo,
    updateTodo,
    deleteTodo,
    undoDelete,
    clearCompleted,
    carryOver,
    canReorder,
    reorder,
    moveBy,
    setFilter,
    setTheme,
    checkDate,
    reloadFromStorage,
  };
})(window.TodoApp = window.TodoApp || {});
