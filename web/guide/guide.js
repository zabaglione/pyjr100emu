const language = document.documentElement.lang;
document.title = document.querySelector(`meta[name="title-${language}"]`).content;
document.querySelector('meta[name="description"]').content = document.querySelector(`meta[name="description-${language}"]`).content;
document.querySelectorAll('option[data-en]').forEach((option) => { option.textContent = option.dataset[language]; });
document.querySelectorAll('[data-language-switch]').forEach((link) => {
  if (link.hreflang === language) link.setAttribute('aria-current', 'true');
});
// Carry the choice between guide pages even if browser storage is disabled.
document.querySelectorAll('a[data-guide-link]').forEach((link) => {
  const url = new URL(link.href);
  url.searchParams.set('lang', language);
  link.href = url.href;
});
const search = document.querySelector('#search');
if (search) {
  const genre = document.querySelector('#genre');
  const cards = [...document.querySelectorAll('.game-card')];
  const count = document.querySelector('#match-count');
  function filterGames() {
    const query = search.value.trim().toLocaleLowerCase();
    let matches = 0;
    cards.forEach((card) => {
      const match = (!genre.value || card.dataset.genre === genre.value)
        && card.textContent.toLocaleLowerCase().includes(query);
      card.hidden = !match;
      if (match) matches += 1;
    });
    count.textContent = language === 'ja' ? `${matches} 作品` : `${matches} ${matches === 1 ? 'game' : 'games'}`;
    document.querySelector('#no-results').hidden = matches !== 0;
  }
  search.addEventListener('input', filterGames);
  genre.addEventListener('change', filterGames);
  document.querySelector('#clear-search').addEventListener('click', () => {
    search.value = ''; genre.value = ''; filterGames(); search.focus();
  });
  filterGames();
}
