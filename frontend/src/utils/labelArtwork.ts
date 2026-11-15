export const labelThemes = [
  { text: 'Обычная', value: 'plain' }, { text: 'Аниме', value: 'anime' },
  { text: 'Котик', value: 'cat' }, { text: 'Фурри-лисичка', value: 'fox' }, { text: 'Космос', value: 'space' }
]
export function labelArtwork (theme: string, color: string): string {
  const c = /^#[0-9a-f]{6}$/i.test(color) ? color : '#805AD5'
  const eyes = '<ellipse cx="70" cy="111" rx="11" ry="16" fill="#27213C"/><ellipse cx="130" cy="111" rx="11" ry="16" fill="#27213C"/><circle cx="73" cy="106" r="4" fill="white"/><circle cx="133" cy="106" r="4" fill="white"/>'
  const blush = '<ellipse cx="51" cy="133" rx="14" ry="7" fill="#FFADC5"/><ellipse cx="149" cy="133" rx="14" ry="7" fill="#FFADC5"/>'
  let art = ''
  if (theme === 'anime') art = `<path d="M25 180Q7 28 100 22Q195 28 175 180Z" fill="${c}"/><ellipse cx="100" cy="113" rx="66" ry="70" fill="#FFE1CE"/><path d="M33 100Q20 20 99 23Q178 13 173 102L138 57L113 92L90 54L61 88L67 52Z" fill="${c}"/>${eyes}${blush}<path d="M88 144Q100 157 112 144" fill="none" stroke="#7A4356" stroke-width="4"/><path d="M40 200Q43 165 100 168Q157 165 160 200" fill="${c}"/><path d="M80 168L100 187L120 168" fill="white"/>`
  else if (theme === 'cat' || theme === 'fox') art = `<path d="M32 83L24 16L78 53M122 53L176 16L168 83" fill="${theme === 'fox' ? '#F59B49' : c}" stroke="#49334E" stroke-width="5"/><path d="M38 63L35 34L62 56M138 56L165 34L162 63" fill="#FFC0D0"/><ellipse cx="100" cy="115" rx="78" ry="70" fill="${theme === 'fox' ? '#F59B49' : '#F5E9FC'}"/><path d="M27 125Q52 185 100 185Q148 185 173 125L118 139L100 128L82 139Z" fill="white"/>${eyes}${blush}<path d="M92 136Q100 129 108 136L100 143Z" fill="#49334E"/><path d="M100 143Q86 159 80 146M100 143Q114 159 120 146M50 140L10 132M50 150L10 153M150 140L190 132M150 150L190 153" fill="none" stroke="#49334E" stroke-width="3"/>`
  else if (theme === 'space') art = `<circle cx="100" cy="100" r="67" fill="${c}"/><ellipse cx="100" cy="110" rx="96" ry="24" fill="none" stroke="#E5B5FF" stroke-width="13" transform="rotate(-25 100 110)"/><path d="M24 21L29 34L43 39L29 44L24 57L19 44L5 39L19 34ZM165 152L171 169L188 175L171 181L165 198L159 181L142 175L159 169Z" fill="#FFD76F"/><circle cx="160" cy="32" r="7" fill="#FFB0D0"/>`
  return `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">${art}</svg>`
}
