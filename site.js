/* Daddy Trader — shared header/footer behaviour (Option A master theme).
   Used by Fundamental, Privacy and Terms (index keeps its own script).
   Mobile menu toggle for the shared .dt-top header + footer year. */
(function(){
  var btn = document.getElementById('dtMenuBtn');
  var nav = document.getElementById('dtSiteNav');
  function closeMenu(){
    if (!nav || !btn) return;
    nav.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  }
  if (btn && nav) {
    btn.addEventListener('click', function(){
      var open = nav.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.addEventListener('click', function(e){
      if (e.target.closest('a')) closeMenu();
    });
    document.addEventListener('keydown', function(e){
      if (e.key === 'Escape') closeMenu();
    });
  }
  var year = new Date().getFullYear();
  Array.prototype.forEach.call(document.querySelectorAll('.dt-yr'), function(el){
    el.textContent = year;
  });
})();
