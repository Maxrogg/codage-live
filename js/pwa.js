/* PWA : fonctionnement hors ligne + bouton « Installer l'application ». Ne fait rien dans un simple fichier local. */
(function () {
  if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
    navigator.serviceWorker.register('sw.js').catch(function () { /* hors ligne impossible : l'outil marche quand même en ligne */ });
  }
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    const b = document.createElement('button'); b.textContent = 'Installer l\'application'; b.style.marginLeft = '8px';
    b.onclick = function () { e.prompt(); b.remove(); };
    const nav = document.querySelector('header nav'); if (nav) nav.appendChild(b);
  });
})();
