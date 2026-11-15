import qrcode from 'qrcode-generator'
qrcode.stringToBytes = qrcode.stringToBytesFuncs['UTF-8']
export async function renderPlainQr (payload: string, caption: string, manufacturer = '') {
  const qr = qrcode(0, 'H'); qr.addData(payload); qr.make()
  const n = qr.getModuleCount(); const unit = 16; const border = 4 * unit
  const size = (n + 8) * unit
  const canvas = document.createElement('canvas'); canvas.width = 827; canvas.height = 827
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, 827, 827)
  ctx.save(); ctx.translate((827 - 720) / 2, 12); ctx.scale(720 / size, 720 / size)
  ctx.fillStyle = '#000000'
  for (let row = 0; row < n; row++) for (let col = 0; col < n; col++) {
    if (qr.isDark(row, col)) ctx.fillRect(border + col * unit, border + row * unit, unit, unit)
  }
  ctx.restore(); ctx.fillStyle = '#111111'; ctx.textAlign = 'center'
  ctx.font = 'bold 26px sans-serif'; ctx.fillText(manufacturer || 'Производитель не указан', 413.5, 763, 770)
  ctx.font = 'bold 28px sans-serif'; ctx.fillText(caption, 413.5, 802, 770)
  ctx.strokeStyle = '#444444'; ctx.lineWidth = 1.5; ctx.setLineDash([8, 5]); ctx.strokeRect(5, 5, 817, 817)
  return canvas
}
