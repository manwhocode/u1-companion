import Vue from 'vue'
import VueI18n, { type Locale } from 'vue-i18n'
import { SupportedLocales } from '@/globals'
import messages from '@/locales/en.yaml'
import { I18nLocales } from '@/dynamicImports'
import u1English from '@/locales/u1/en.json'
import u1Russian from '@/locales/u1/ru.json'
import { translateU1 } from '@/utils/u1LocaleMessages'

const u1Locales = import.meta.glob('../locales/u1/*.json', { import: 'default' })

Vue.use(VueI18n)

export const getNavigatorLocales = () => {
  return navigator.languages ?? [navigator.language]
}

export const getAllLocales = (): Intl.LocalesArgument => {
  return [
    i18n.locale,
    ...getNavigatorLocales()
  ]
}

/**
 * Loads the starting locale for the user.
 */
export const getStartingLocale = () => {
  const navigatorLocale = getNavigatorLocales()[0]
  const countryCode = navigatorLocale.split(/-|_/)[0]

  if (
    countryCode &&
    SupportedLocales.some(locale => locale.code === countryCode)
  ) {
    return countryCode
  } else {
    return import.meta.env.VUE_APP_I18N_LOCALE || 'en'
  }
}

const startingLocale = getStartingLocale()

const i18n = new VueI18n({
  locale: startingLocale,
  fallbackLocale: import.meta.env.VUE_APP_I18N_FALLBACK_LOCALE || 'en',
  messages: {}
})

// Pre apply the en language for fallback.
i18n.setLocaleMessage('en', { ...messages, app: { ...(messages.app as VueI18n.LocaleMessages), u1: u1English } })
i18n.setLocaleMessage('ru', { app: { u1: u1Russian } })

export const u1t = (source: unknown, values: Record<string, unknown> = {}) => translateU1(i18n, source, values)
Vue.prototype.$u1t = u1t
declare module 'vue/types/vue' {
  interface Vue { $u1t: typeof u1t }
}

const loadedLanguages: Locale[] = []

export const loadLocaleMessagesAsync = async (locale: Locale) => {
  // If already loaded, and currently selected.
  if (loadedLanguages.length > 0 && i18n.locale === locale) {
    return locale
  }

  // If already loaded, but not the currently selected.
  if (loadedLanguages.includes(locale)) {
    i18n.locale = locale
    return locale
  }

  // Not loaded
  try {
    const messages = await I18nLocales[locale]()
    const loadU1 = u1Locales[`../locales/u1/${locale}.json`]
    if (loadU1) {
      const addon = await loadU1()
      messages.app = { ...(messages.app as VueI18n.LocaleMessages), u1: addon as VueI18n.LocaleMessages }
    }

    i18n.setLocaleMessage(locale, messages)
    loadedLanguages.push(locale)
    i18n.locale = locale
    return locale
  } catch {
    return i18n.locale
  }
}

loadLocaleMessagesAsync(startingLocale)

export default i18n
