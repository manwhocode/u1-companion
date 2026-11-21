import { describe, expect, it } from 'vitest'
import Vue from 'vue'
import VueI18n from 'vue-i18n'
import { translateU1, localizeU1Result } from '@/utils/u1LocaleMessages'
import en from '@/locales/u1/en.json'
import ru from '@/locales/u1/ru.json'
import de from '@/locales/u1/de.json'
Vue.use(VueI18n)
const instance = (locale: string) => new VueI18n({ locale, fallbackLocale: 'en', messages: { en: { app: { u1: en } }, ru: { app: { u1: ru } }, de: { app: { u1: de } } } })
describe('independent U1 Companion catalogs', () => {
  it('uses the selected Fluidd locale but owns its messages', () => {
    const i18n = instance('en')
    expect(translateU1(i18n, 'Закрыть')).toBe('Close')
    i18n.locale = 'de'; expect(translateU1(i18n, 'Закрыть')).toBe('Schließen')
    i18n.locale = 'ru'; expect(translateU1(i18n, 'Закрыть')).toBe('Закрыть')
  })
  it('preserves head numbers, measurements, names and native identifiers', () => {
    const i18n = instance('en')
    expect(translateU1(i18n, 'Головка {p0}: {p1}', { p0: 3, p1: 'NTAG216 #FFAABB' })).toBe('Head 3: NTAG216 #FFAABB')
    expect(translateU1(i18n, 'U1_MAGNET_PAUSE CONFIRM=1')).toBe('U1_MAGNET_PAUSE CONFIRM=1')
    expect(translateU1(i18n, 'https://192.168.1.100/#tag=12')).toBe('https://192.168.1.100/#tag=12')
  })
  it('can translate a formatted native status without sending printer commands', () => {
    const i18n = instance('en')
    expect(translateU1(i18n, 'Пауза перед слоем 12: установка магнитов.')).toBe('Pause before layer 12: insert magnets.')
  })
  it('translates the nested reason in historical mixed-language magnet events', () => {
    expect(translateU1(instance('en'), 'Magnet pause: Нет активной печати.')).toBe('Pauses for magnets: No active print.')
  })
  it('does not translate or mutate inventory, exported data or Alexa message templates', () => {
    const value = { message: 'Нет активной печати.', filename: 'Закрыть.gcode', name: 'Закрыть', hex: '#FFFFFF', data: { message: 'Закрыть' }, config: { message: 'Печать завершена' }, records: [{ message: 'Ошибка' }] }
    const before = JSON.stringify(value); const i18n = instance('en')
    const result = localizeU1Result(value, source => translateU1(i18n, source))
    expect(result.message).toBe('No active print.')
    expect(result.name).toBe('Закрыть'); expect(result.filename).toBe('Закрыть.gcode'); expect(result.hex).toBe('#FFFFFF')
    expect(result.data.message).toBe('Закрыть'); expect(result.config.message).toBe('Печать завершена'); expect(result.records[0].message).toBe('Ошибка')
    expect(JSON.stringify(value)).toBe(before)
  })
  it('retains every interpolation parameter in completed catalogs', () => {
    const tokens = (s: string) => (s.match(/\{p\d+\}/g) || []).sort()
    expect(Object.keys(en).sort()).toEqual(Object.keys(ru).sort())
    expect(Object.keys(de).sort()).toEqual(Object.keys(ru).sort())
    for (const key of Object.keys(ru) as (keyof typeof ru)[]) {
      expect(tokens(en[key]), key).toEqual(tokens(ru[key])); expect(tokens(de[key]), key).toEqual(tokens(ru[key]))
    }
  })
})
