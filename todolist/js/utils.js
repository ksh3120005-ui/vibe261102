(function (App) {
  'use strict';

  const DAYS = ['일', '월', '화', '수', '목', '금', '토'];

  // 로컬 시간 기준 'YYYY-MM-DD'
  function todayKey(date = new Date()) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  // 'YYYY-MM-DD' → '2026년 11월 2일 (월)'
  function formatDate(key) {
    const [y, m, d] = key.split('-').map(Number);
    const day = new Date(y, m - 1, d).getDay();
    return `${y}년 ${m}월 ${d}일 (${DAYS[day]})`;
  }

  function uid() {
    if (window.crypto && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  function truncate(text, max) {
    return text.length > max ? text.slice(0, max) + '…' : text;
  }

  App.utils = { todayKey, formatDate, uid, truncate };
})(window.TodoApp = window.TodoApp || {});
