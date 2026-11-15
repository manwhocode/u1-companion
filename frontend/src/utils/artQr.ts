import qrcode from 'qrcode-generator'
export const artThemes = [
  { text: 'Обычный QR', value: 'plain' },
  { text: 'Аниме · Бирюзовая', value: 'teal' },
  { text: 'Аниме · Розовая кошечка', value: 'pink-cat' },
  { text: 'Аниме · Фиолетовая лисичка', value: 'violet-fox' }
]
export async function renderArtQr (payload: string, theme: string, caption: string, aperture = 0.24) {
  const qr = qrcode(0, 'H'); qr.addData(payload); qr.make()
  const n = qr.getModuleCount(); const unit = 16; const border = 4 * unit
  const core = n * unit; const size = core + border * 2
  const canvas = document.createElement('canvas'); canvas.width = 827; canvas.height = 827
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = 'white'; ctx.fillRect(0, 0, 827, 827)
  // Exactly 70 mm when printed at 300 DPI (827 px rounded).
  const scale = 780 / size; ctx.save(); ctx.translate((827 - 780) / 2, 10); ctx.scale(scale, scale)
  const artistic = theme !== 'plain'
  if (artistic) {
    if (!['teal', 'pink-cat', 'violet-fox'].includes(theme)) throw new Error('Неизвестный фон')
    const image = new Image(); image.src = `${import.meta.env.BASE_URL}anime-backgrounds/${theme}.jpg`; await image.decode()
    ctx.drawImage(image, border, border, core, core)
  }
  for (let row = 0; row < n; row++) for (let col = 0; col < n; col++) {
    const fixed = (row < 9 && col < 9) || (row < 9 && col > n - 10) || (row > n - 10 && col < 9) || row === 6 || col === 6 || row === 8 || col === 8 || (Math.abs(row - (n - 7)) <= 2 && Math.abs(col - (n - 7)) <= 2)
    const face = artistic && !fixed && Math.abs(col + 0.5 - n * 0.5) < n * aperture / 2 && Math.abs(row + 0.5 - n * 0.40) < n * aperture / 2
    if (face) continue
    const dark = qr.isDark(row, col)
    ctx.fillStyle = dark ? '#090909' : 'rgba(255,255,255,0.96)'
    const inset = artistic && !fixed ? unit * 0.10 : 0
    ctx.fillRect(border + col * unit + inset, border + row * unit + inset, unit - inset * 2, unit - inset * 2)
  }
  ctx.restore(); ctx.fillStyle = '#111'; ctx.font = 'bold 24px sans-serif'; ctx.textAlign = 'center'; ctx.fillText(caption, 827 / 2, 815)
  return canvas
}
