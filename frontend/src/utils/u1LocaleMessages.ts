import type VueI18n from 'vue-i18n'
import keys from '@/locales/u1/keys.json'
import russian from '@/locales/u1/ru.json'

const sourceKeys = keys as Record<string, string>
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const patterns = Object.entries(russian).filter(([, text]) => /\{p\d+\}/.test(text) && /[А-Яа-яЁё]/.test(text)).map(([key, text]) => {
  const names: string[] = []
  const expression = text.split(/(\{p\d+\})/).map(part => {
    if (!/^\{p\d+\}$/.test(part)) return escape(part)
    names.push(part.slice(1, -1)); return '([\\s\\S]+?)'
  }).join('')
  return { key, names, expression: new RegExp('^' + expression + '$') }
}).sort((a, b) => b.expression.source.length - a.expression.source.length)

export function translateU1 (i18n: VueI18n, source: unknown, values: Record<string, unknown> = {}): string {
  if (typeof source !== 'string') return source == null ? '' : String(source)
  // Historical native events can contain an English envelope around a Russian reason.
  if (source.startsWith('Magnet pause: ')) return translateU1(i18n, 'Паузы для магнитов') + ': ' + translateU1(i18n, source.slice(14))
  let key = sourceKeys[source]
  if (!key && /[А-Яа-яЁё]/.test(source)) {
    for (const pattern of patterns) {
      const match = source.match(pattern.expression)
      if (match) { key = pattern.key; values = Object.fromEntries(pattern.names.map((name, i) => [name, match[i + 1]])); break }
    }
  }
  if (!key && /[А-Яа-яЁё]/.test(source)) {
    const prefix = Object.entries(russian).filter(([, text]) => text.length >= 16 && /[:：]\s*$/.test(text) && source.startsWith(text)).sort((a, b) => b[1].length - a[1].length)[0]
    if (prefix && source !== prefix[1]) return translateU1(i18n, prefix[1]) + translateU1(i18n, source.slice(prefix[1].length))
  }
  if (!key) return source
  const path = 'app.u1.' + key
  if (!i18n.te(path, i18n.locale) && !i18n.te(path, 'en')) return source
  return String(i18n.t(path, values))
}

// Translate status/error text only. Inventory names, notes, codes and addresses stay intact.
export function localizeU1Result<T> (value: T, translate: (source: unknown) => string): T {
  function walk (item: unknown, field = ''): unknown {
    if (/^(data|config|payload|inventory|records|library|exported|spools|colors|entries|notes|texts|templates)$/.test(field)) return item
    if (typeof item === 'string') return /^(message|error|reason|notice|warnings)$/.test(field) ? translate(item) : item
    if (Array.isArray(item)) return item.map(v => walk(v, field))
    if (item && typeof item === 'object') return Object.fromEntries(Object.entries(item).map(([k, v]) => [k, walk(v, k)]))
    return item
  }
  return walk(value) as T
}
