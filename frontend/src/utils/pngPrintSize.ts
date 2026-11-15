// Embed print resolution, so 827 px exports open at approximately 70 mm.
export function printPng (canvas: HTMLCanvasElement): string {
  const raw = atob(canvas.toDataURL('image/png').split(',')[1])
  const original = Uint8Array.from(raw, c => c.charCodeAt(0))
  const chunk = new Uint8Array(21); const view = new DataView(chunk.buffer)
  view.setUint32(0, 9)
  chunk.set([112, 72, 89, 115], 4) // pHYs
  view.setUint32(8, 11811); view.setUint32(12, 11811); chunk[16] = 1
  let crc = 0xFFFFFFFF
  for (const byte of chunk.slice(4, 17)) {
    crc ^= byte
    for (let bit = 0; bit < 8; bit++) crc = crc & 1 ? (crc >>> 1) ^ 0xEDB88320 : crc >>> 1
  }
  view.setUint32(17, (crc ^ 0xFFFFFFFF) >>> 0)
  const result = new Uint8Array(original.length + chunk.length)
  result.set(original.slice(0, 33)); result.set(chunk, 33); result.set(original.slice(33), 54)
  let binary = ''
  for (const byte of result) binary += String.fromCharCode(byte)
  return 'data:image/png;base64,' + btoa(binary)
}
