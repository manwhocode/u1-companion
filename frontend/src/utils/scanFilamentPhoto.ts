import QrScanner from './reliableQrScanner'
import { parseTag } from './nfcFilament'

// Screen photos contain a pixel-grid/moire pattern. Try several resolutions
// with filtered resampling, and overlapping crops for a small/off-centre code.
export async function scanFilamentPhoto (file: File, progress?: (text: string) => void, signal?: AbortSignal): Promise<string> {
  const url = URL.createObjectURL(file)
  const image = new Image()
  let engine: Awaited<ReturnType<typeof QrScanner.createQrEngine>> | undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  let abort: (() => void) | undefined
  let stopped = false
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error('Не удалось прочитать QR за 7 секунд. Обрежьте фото ближе к коду или выберите QR PNG.')), 7000)
    abort = () => reject(new Error('Сканирование отменено'))
    signal?.addEventListener('abort', abort, { once: true })
    if (signal?.aborted) abort()
  })
  const bounded = <T>(promise: Promise<T>) => Promise.race([promise, deadline])
  try {
    await bounded(new Promise<void>((resolve, reject) => {
      image.onload = () => resolve()
      image.onerror = () => reject(new Error('Не удалось открыть фото. Выберите JPEG или PNG.'))
      image.src = url
    }))
    const creatingEngine = QrScanner.createQrEngine()
    creatingEngine.then(candidate => { if (stopped && candidate instanceof Worker) candidate.terminate() }).catch(() => {})
    engine = await bounded(creatingEngine)
    if (engine instanceof Worker) engine.postMessage({ type: 'inversionMode', data: 'both' })
    const w = image.naturalWidth; const h = image.naturalHeight
    if (!w || !h) throw new Error('Пустое изображение')
    const regions = [{ x: 0, y: 0, width: w, height: h }]
    const side = Math.min(w, h) * 0.7
    for (const y of [(h - side) / 2, 0, h - side]) regions.push({ x: (w - side) / 2, y, width: side, height: side })
    const canvas = document.createElement('canvas')
    let formatError: unknown
    for (const [index, region] of regions.entries()) {
      for (const longest of [900, 600, 1200]) {
        if (signal?.aborted) throw new Error('Сканирование отменено')
        progress?.(`Читаю QR: область ${index + 1}/${regions.length}, ${longest} px`)
        const scale = Math.min(1, longest / Math.max(region.width, region.height))
        canvas.width = Math.round(region.width * scale)
        canvas.height = Math.round(region.height * scale)
        const ctx = canvas.getContext('2d', { willReadFrequently: true })!
        ctx.imageSmoothingEnabled = true
        ctx.imageSmoothingQuality = 'high'
        ctx.drawImage(image, region.x, region.y, region.width, region.height, 0, 0, canvas.width, canvas.height)
        try {
          const result = await bounded(QrScanner.scanImage(canvas, { qrEngine: engine, returnDetailedScanResult: true }))
          try { parseTag(result.data); return result.data } catch (error) { formatError = error }
        } catch (error) {
          if (error !== QrScanner.NO_QR_CODE_FOUND && !String(error).includes('No QR code found')) throw error
        }
      }
    }
    if (formatError) throw formatError
    throw new Error('QR не распознан. Снимите ближе, без бликов, захватив белое поле вокруг кода, или выберите скачанный QR PNG.')
  } finally {
    stopped = true
    clearTimeout(timer)
    if (abort) signal?.removeEventListener('abort', abort)
    if (engine instanceof Worker) engine.terminate()
    URL.revokeObjectURL(url)
  }
}
