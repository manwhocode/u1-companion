import { describe, expect, it } from 'vitest'
import { tagUrl, parseTag } from '../../src/utils/nfcFilament'
import { parseQr } from '../../src/utils/u1Filament'
import U1Nfc from '../../src/components/U1Nfc.vue'
describe('NFC filament data', () => {
  it('round trips name, manufacturer, material and color through a URL', () => {
    const p = { name: 'Мой салат', manufacturer: 'SUNLU', material: 'TPU', hex: '#39FF14' }
    expect(parseTag(tagUrl(p, 'https://192.168.1.100'))).toEqual(p)
  })
  it('fits NTAG216 even with long unicode names', () => {
    const url = tagUrl({ name: 'Я'.repeat(100), manufacturer: 'Ж'.repeat(80), material: 'PLA', hex: '#123ABC' }, 'https://192.168.1.100')
    expect(url.length).toBeLessThan(850)
    expect(parseTag(url).hex).toBe('#123ABC')
  })
  it('sends a physical spool from a phone link to the selected head exactly once', () => {
    const original = new U1Nfc()
    const openedByPhone = new U1Nfc()
    const preset = { material: 'PLA', hex: '#123ABC', spoolId: 'ab1f5c38-c805-4531-9135-957f57cbdf90' }
    const url = tagUrl(preset, 'https://192.168.1.100')
    const selections: unknown[] = []
    openedByPhone.$on('select', (value: unknown) => selections.push(value))
    try {
      original.readPreset(2)
      openedByPhone.accept(url, true)
      expect(selections).toEqual([{ slot: 2, preset: expect.objectContaining(preset) }])
      expect(openedByPhone.opened).toBe(false)
      openedByPhone.accept(url, true)
      expect(selections).toHaveLength(1)
      expect(openedByPhone.opened).toBe(true)
    } finally {
      original.close()
      openedByPhone.close()
      original.$destroy()
      openedByPhone.$destroy()
    }
  })
  it('rejects unrecognized links and injected materials', () => {
    expect(() => parseTag('https://example.com')).toThrow()
    expect(() => parseTag('https://example.com/#/u1-filaments?tag=1&m=G28&c=FFFFFF')).toThrow()
  })
  it('accepts legacy QR whitespace and case while retaining validation', () => {
    expect(parseQr('\uFEFF U1FILAMENT:{"material":"PLA","hex":"#ffffff"}').hex).toBe('#FFFFFF')
    expect(() => parseQr('u1filament:{"material":"G28","hex":"FFFFFF"}')).toThrow()
  })
})
