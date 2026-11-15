import { validatePreset, parseQr, type FilamentPreset } from './u1Filament'
export interface NfcPreset extends FilamentPreset { name?: string; spoolId?: string }
const spoolIdPattern = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i
export function tagUrl (preset: NfcPreset, origin: string) {
  const p = validatePreset(preset)
  const query = new URLSearchParams({ tag: '1', m: p.material, c: p.hex.slice(1) })
  if (preset.spoolId && spoolIdPattern.test(preset.spoolId)) query.set('s', preset.spoolId)
  if (preset.name) query.set('n', preset.name.slice(0, 100))
  if (preset.manufacturer) query.set('b', preset.manufacturer.slice(0, 80))
  // Keep URL NDEF well within NTAG216's 888-byte user memory.
  if (query.toString().length > 650) query.delete('n')
  if (query.toString().length > 650) query.delete('b')
  return new URL('/u1-filaments-ui/#/u1-filaments?' + query, origin).href
}
export function parseTag (raw: string): NfcPreset {
  const text = raw.trim()
  if (/^u1filament:|^\{/i.test(text)) return parseQr(text)
  const url = new URL(/^[^\s/]+\/u1-filaments-ui\//i.test(text) ? 'https://' + text : text)
  const query = new URLSearchParams(url.hash.split('?')[1] || url.search)
  if (query.get('tag') !== '1') throw new Error('На метке нет данных филамента U1')
  const spoolId = query.get('s')
  if (spoolId && !spoolIdPattern.test(spoolId)) throw new Error('Неверный ID катушки на метке')
  return { ...validatePreset({ material: query.get('m') || '', hex: query.get('c') || '' }), name: (query.get('n') || '').slice(0, 100), manufacturer: (query.get('b') || '').slice(0, 80), ...(spoolId ? { spoolId } : {}) }
}
export function tagAddress (url: string) { return url.replace(/^https?:\/\//i, '') }
export interface NfcEvent extends Event { message: { records: { recordType: string; data: DataView; encoding?: string }[] } }
export interface NfcReader extends EventTarget {
  scan(options: { signal: AbortSignal }): Promise<void>
  write(message: { records: { recordType: string; data: string }[] }, options: { signal: AbortSignal }): Promise<void>
}
export function readerConstructor () { return (window as unknown as { NDEFReader?: new() => NfcReader }).NDEFReader }
