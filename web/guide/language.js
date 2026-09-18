/* English is the static fallback, including when JavaScript is unavailable. */
function chooseGuideLanguage(requested, saved, preferred) {
  if (requested === 'en' || requested === 'ja') return requested;
  if (saved === 'en' || saved === 'ja') return saved;
  return typeof preferred === 'string' && /^ja(?:-|$)/i.test(preferred) ? 'ja' : 'en';
}

(() => {
  const requested = new URLSearchParams(location.search).get('lang');
  let saved;
  try { saved = localStorage.getItem('jr100-guide-language'); } catch { /* Storage is optional. */ }
  const language = chooseGuideLanguage(requested, saved, navigator.language);
  document.documentElement.lang = language;
  if (requested === 'en' || requested === 'ja') {
    try { localStorage.setItem('jr100-guide-language', language); } catch { /* Keep URL choice. */ }
  }
})();
