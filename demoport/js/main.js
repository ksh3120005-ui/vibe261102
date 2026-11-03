(function () {
  const header = document.querySelector('.site-header');
  const toggle = document.querySelector('.nav__toggle');
  const menu = document.getElementById('nav-menu');
  const toast = document.querySelector('.toast');

  // 모바일 메뉴 열기/닫기
  function setMenu(open) {
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
    menu.classList.toggle('is-open', open);
  }

  toggle.addEventListener('click', function () {
    setMenu(toggle.getAttribute('aria-expanded') !== 'true');
  });

  menu.addEventListener('click', function (e) {
    if (e.target.closest('a')) setMenu(false);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') setMenu(false);
  });

  // 스크롤 시 헤더 경계선
  function onScroll() {
    header.classList.toggle('is-scrolled', window.scrollY > 8);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // 현재 보고 있는 섹션 메뉴 강조
  const links = Array.from(menu.querySelectorAll('a[href^="#"]'));
  const sections = links
    .map(function (a) { return document.querySelector(a.getAttribute('href')); })
    .filter(Boolean);

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        const id = '#' + entry.target.id;
        links.forEach(function (a) {
          a.classList.toggle('is-active', a.getAttribute('href') === id);
        });
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    sections.forEach(function (s) { observer.observe(s); });
  }

  // 토스트
  let toastTimer;
  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toast.classList.remove('is-visible');
    }, 2000);
  }

  // 이메일 복사
  function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  document.querySelectorAll('[data-copy]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const text = btn.getAttribute('data-copy');
      const done = function () { showToast('이메일 주소가 복사되었습니다'); };
      const fail = function () {
        if (fallbackCopy(text)) done();
        else showToast('복사에 실패했습니다. 직접 선택해 주세요');
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done, fail);
      } else {
        fail();
      }
    });
  });

  // 푸터 연도
  const year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();
})();
