<template>
<section class="alexa-settings">
  <u1-voice-control />
  <h3 class="mt-4">{{ $u1t("Уведомления Alexa") }}</h3>
  <p>{{ $u1t("Подключите свой Amazon, выберите устройства и проверьте звук. Home Assistant не требуется.") }}</p>
  <v-alert v-if="busy" dense type="info" role="status">{{ progress }} {{ $u1t("Запрос отправляется один раз; остальные разделы доступны.") }}</v-alert>
  <v-alert v-if="error" dense type="error">{{ error }}</v-alert>
  <v-alert v-if="state" dense :type="state.phase === 'connected' ? 'success' : 'info'">{{ state.message }}</v-alert>
  <v-alert v-if="!secure" dense type="warning">{{ $u1t("Для безопасного входа откройте U1 через HTTPS и установите доверие сертификату на этом устройстве. Кнопка сертификата находится вверху страницы филаментов.") }}</v-alert>
  <v-select v-model="region" :items="regions" :label="$u1t('Регион аккаунта Amazon')" outlined dense :disabled="busy" />
  <div class="alexa-actions">
    <v-btn color="primary" :disabled="busy || !secure || !available" @click="login">{{ $u1t("Подключить Amazon") }}</v-btn>
    <v-btn outlined color="primary" :disabled="busy || !secure || !available" @click="loginWithPasskey">{{ $u1t("Войти ключом через телефон") }}</v-btn>
    <v-btn outlined :disabled="busy" @click="refresh">{{ $u1t("Обновить") }}</v-btn>
    <v-btn v-if="state && state.phase !== 'offline' && state.phase !== 'disconnected'" outlined :disabled="busy" @click="disconnect">{{ $u1t("Отключить аккаунт") }}</v-btn>
  </div>
  <p class="mt-3">{{ $u1t("Откроется временное защищённое окно входа Amazon через локальный мост на вашем принтере. Введите данные только в этом окне; пароль в настройки U1 вводить не нужно. Подтверждение Amazon и двухфакторная проверка выполняются вами.") }}</p>
  <v-btn v-if="loginLink" outlined color="primary" :href="loginLink" target="_blank" rel="noopener noreferrer">{{ $u1t("Открыть окно входа") }}</v-btn>
  <v-alert v-if="externalLink" dense type="info" class="mt-3">
    <p><strong>{{ $u1t("Ссылка готова. Нажмите «Открыть настоящий Amazon» ниже.") }}</strong></p>
    <p>{{ $u1t("Откройте Amazon и выберите вход ключом доступа. На ПК выберите телефон и отсканируйте показанный Amazon QR-код. На телефоне подтвердите вход своим ключом.") }}</p>
    <p>{{ $u1t("Адрес входа:") }} {{ amazonLoginDomain }}{{ $u1t(". Регион Alexa:") }} {{ state && state.config ? state.config.region : region }}.</p>
    <v-btn outlined :href="externalLink" target="_blank" rel="noopener noreferrer">{{ $u1t("Открыть настоящий Amazon") }}</v-btn>
    <p class="mt-3">{{ $u1t("После входа скопируйте полный адрес страницы Amazon из адресной строки и вставьте ниже. Не отправляйте его в чат. Если открылась ошибка страницы, адрес всё равно может содержать нужный одноразовый код.") }}</p>
    <v-textarea v-model="returnUrl" :label="$u1t('Адрес страницы Amazon после входа')" outlined dense rows="3" autocomplete="off" spellcheck="false" />
    <v-btn color="primary" :disabled="busy || !returnUrl.trim()" @click="completePasskey">{{ $u1t("Завершить подключение") }}</v-btn>
    <p class="mt-2">{{ $u1t("Это новый способ подключения: реальный вход и получение доступа ещё требуют проверки с вашим аккаунтом. Одного открытия Amazon недостаточно для подключения Alexa.") }}</p>
  </v-alert>
  <p>{{ $u1t("Это неофициальное подключение. После изменений Amazon может потребоваться повторный вход. Сессия хранится на вашем принтере отдельно от библиотеки катушек и её экспорта.") }}</p>
  <template v-if="state && state.devices.length">
    <h4>{{ $u1t("Куда отправлять уведомления") }}</h4>
    <div v-for="device in state.devices" :key="device.id" class="alexa-device">
      <v-checkbox :input-value="targets.includes(device.id)" :label="device.name" :disabled="busy" hide-details @change="toggle(device.id, $event)" />
      <p>{{ device.family }} · {{ device.online ? $u1t("доступно по данным Amazon") : $u1t("не в сети") }} · {{ device.confirmed ? $u1t("звук подтверждён") : $u1t("нужна проверка звука") }}</p>
      <div class="alexa-actions">
        <v-btn small outlined :loading="busy && state.test?.id === device.id" :disabled="busy || state.phase !== 'connected'" @click="test(device.id)">{{ $u1t("Проверить звук") }}</v-btn>
        <v-btn v-if="state.test && state.test.id === device.id && state.test.phase === 'accepted' && !device.confirmed" small color="primary" :disabled="busy" @click="heard(device.id)">{{ $u1t("Да, слышу на этом устройстве") }}</v-btn>
      </div>
    </div>
    <p>{{ $u1t("Fire TV проверяется отдельно: принятие запроса Amazon ещё не означает, что звук прозвучал.") }}</p>
  </template>
  <p>{{ $u1t("Способ озвучивания: голосовое сообщение.") }}</p><v-select v-model="language" :items="speechLanguages" :label="$u1t('Язык озвучивания Alexa')" outlined dense :disabled="busy" @change="changeLanguage" /><p class="text-caption">{{ $u1t('Язык применяется к сообщениям Companion. После смены языка проверьте звук заново. Поддержка зависит от устройства и региона Amazon.') }}</p><p class="text-caption">{{ $u1t('Фразы сохраняются отдельно для каждого языка. При первом выборе используются готовые тексты; свои фразы можно изменить ниже.') }}</p>
  <p class="text-caption">{{ $u1t("Только кнопка «Да, слышу» подтверждает работу голосового сообщения.") }}</p>
  <v-switch v-model="enabled" :label="$u1t('Автоматические уведомления')" :disabled="busy || !canEnable" />
  <p v-if="!canEnable">{{ $u1t("Выберите устройства, выполните проверку и подтвердите звук на каждом из них.") }}</p>
  <v-expansion-panels flat>
    <v-expansion-panel><v-expansion-panel-header>{{ $u1t("Тексты уведомлений") }}</v-expansion-panel-header><v-expansion-panel-content><p>{{ $u1t("Задайте свои фразы для каждого события. Фразы калибровки K относятся к очереди калибровки Companion; напоминания о столе и обслуживании используют заданные периоды.") }}</p>
      <v-text-field v-for="(label, key) in labels" :key="key" v-model="phrases[key]" :label="label" outlined dense :maxlength="500" :disabled="busy" />
    </v-expansion-panel-content></v-expansion-panel>
  </v-expansion-panels>
  <div class="alexa-actions mt-3"><v-btn outlined color="primary" :disabled="busy || !available || (enabled && !canEnable)" @click="save">{{ $u1t("Сохранить Alexa") }}</v-btn></div>
  <p v-if="state && state.lastEvent" class="mt-2">{{ $u1t("Последнее уведомление:") }} {{ labels[state.lastEvent.kind] || state.lastEvent.kind }} · {{ state.lastEvent.phase === 'accepted' ? $u1t("запрос принят Amazon") : state.lastEvent.phase === 'sending' ? $u1t("отправка") : $u1t("отправка не подтверждена") }}</p>
  <v-divider class="my-4" />
</section>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import U1VoiceControl from '@/components/U1VoiceControl.vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
interface Device { id: string; name: string; family: string; online: boolean; confirmed: boolean }
interface Config { language?: string; phraseLanguages?: Record<string, Record<string,string>>; region: string; method: string; enabled: boolean; targets: string[]; phrases: Record<string, string> }
interface State { speechLocales?: {value:string;text:string}[]; speechCatalogs?: Record<string,Record<string,string>>; phase: string; message: string; devices: Device[]; loginUrl: string | null; externalLoginUrl?: string | null; config?: Config; test?: {id: string; phase: string}; operation?: {id: string; ok: boolean; error?: string}; lastEvent?: {kind: string; phase: string} }
@Component({ components: { U1VoiceControl } })
export default class U1Alexa extends Vue {
  state: State | null = null
  progress = ''
  busy = false
  reading = false
  initialized = false
  error = ''
  region = 'amazon.de'
  method = 'speak'
  language = 'auto'
  editingLanguage = 'auto'
  languageDrafts: Record<string,Record<string,string>> = {}
  get speechLanguages () { return [{value:'auto',text:u1t('По умолчанию Alexa')},...(this.state?.speechLocales || [])] }
  changeLanguage () { this.languageDrafts[this.editingLanguage] = {...this.phrases}; this.phrases = {...(this.languageDrafts[this.language] || this.state?.config?.phraseLanguages?.[this.language] || this.state?.speechCatalogs?.[this.language.split('-')[0]] || this.state?.speechCatalogs?.en || {})}; this.editingLanguage = this.language; this.enabled = false }
  enabled = false
  targets: string[] = []
  phrases: Record<string, string> = {}
  returnUrl = ''
  timer: number | null = null
  disposed = false
  regions = ['amazon.de', 'amazon.com', 'amazon.co.uk', 'amazon.fr', 'amazon.it', 'amazon.es', 'amazon.co.jp', 'amazon.com.au', 'amazon.ca'].map(value => ({ value, text: value }))
  get labels (): Record<string,string> { return { companionUpdate: u1t("Доступна новая версия"), started: u1t("Печать началась"), calibrationStarted: u1t("Калибровка K началась"), calibrationCompleted: u1t("Калибровка K завершена"), calibrationStopped: u1t("Калибровка K остановлена или не завершена"), finished: u1t("Печать завершена"), stopped: u1t("Печать остановлена"), paused: u1t("Печать на паузе"), resumed: u1t("Печать продолжена"), error: u1t("Ошибка принтера"), repeat: u1t("Напоминание об ошибке"), recovered: u1t("Ошибка устранена"), shortage: u1t("Филамент заканчивается"), maintenance: u1t("Напоминание об обслуживании"), bed: u1t("Напоминание о калибровке стола"), dryerDone: u1t("Сушка завершена"), dryerPaused: u1t("Сушка приостановлена"), scheduleFailed: u1t("Отложенный запуск не выполнен") } }
  get secure () { return window.isSecureContext && window.location.protocol === 'https:' }
  get available () { return !!this.state && this.state.phase !== 'offline' }
  get canEnable () { return this.state?.phase === 'connected' && this.targets.length > 0 && this.targets.every(id => this.state?.devices.some(d => d.id === id && d.confirmed)) && this.method === this.state?.config?.method && this.language === (this.state?.config?.language || 'auto') }
  get loginLink () {
    const value = this.state?.loginUrl
    if (!value || !this.secure) return ''
    try { const url = new URL(value); return url.protocol === 'https:' && url.hostname === window.location.hostname && url.port === '3443' && /^\/connect\/[a-f0-9]{64}$/.test(url.pathname) ? url.href : '' } catch { return '' }
  }
  get externalLink () {
    const value = this.state?.externalLoginUrl
    if (!value || !this.secure) return ''
    try { const url = new URL(value); return url.protocol === 'https:' && url.hostname === 'www.' + this.amazonLoginDomain && !url.username && !url.password && !url.port && url.pathname === '/ap/signin' ? url.href : '' } catch { return '' }
  }
  get amazonLoginDomain () { return this.state?.config?.region === 'amazon.co.jp' ? 'amazon.co.jp' : 'amazon.com' }
  sync () {
    const c = this.state?.config
    if (c) { this.region = c.region; this.method = 'speak'; this.language=c.language || 'auto'; this.editingLanguage=this.language; this.enabled = c.enabled; this.targets = [...c.targets]; this.phrases = { ...c.phrases }; this.initialized = true }
  }
  async refresh () {
    if (this.reading || this.disposed) return
    this.reading = true
    try { this.state = await u1DataRequest<State>('alexa_state', {}, 8000); if (!this.initialized) this.sync() } catch (error) { this.error = (error as Error).message } finally { this.reading = false }
  }
  async command (action: string, payload: unknown) {
    this.progress = action === 'test' ? u1t("Проверка звука: ожидаю ответ Amazon…") : u1t("Сохраняю настройки Alexa…")
    const result = await u1DataRequest<{id: string}>('alexa_command', { action, payload }, 10000)
    const end = Date.now() + 25000
    while (!this.disposed && Date.now() < end) {
      const state = await u1DataRequest<State>('alexa_state', {}, 8000); this.state = state
      if (state.operation?.id === result.id) { if (!state.operation.ok) throw new Error(({ test_required: u1t("Сначала подтвердите звук на выбранных устройствах."), invalid_return_url: u1t("Нужен полный адрес www.Amazon после входа, без изменения домена."), missing_authorization_code: u1t("В адресе нет одноразового кода. Скопируйте адрес страницы, открывшейся после входа по кнопке программы."), login_expired: u1t("Время входа истекло. Начните вход ключом заново.") } as Record<string,string>)[state.operation.error || ''] || u1t("Операция Alexa не выполнена. Обновите состояние и повторите.")); return }
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
    throw new Error(u1t("Ответ моста не получен. Проверьте состояние перед повторной отправкой."))
  }
  config () { return { language:this.language, region: this.region, method: this.method, enabled: this.enabled, targets: this.targets, phrases: this.phrases } }
  toggle (id: string, selected: boolean) { this.targets = selected ? [...new Set([...this.targets, id])] : this.targets.filter(value => value !== id) }
  async run (fn: () => Promise<void>) {
    if (this.busy) return
    this.busy = true; this.error = ''
    try { await fn() } catch (error) { this.error = (error as Error).message } finally { this.busy = false; this.progress = '' }
  }
  async login () {
    await this.run(async () => {
      await this.command('save', { ...this.config(), enabled: false, targets: [] })
      await this.command('login', { host: window.location.hostname })
      await this.waitForLink(false)
      this.sync()
    })
  }
  async disconnect () { await this.run(async () => { await this.command('logout', {}); this.sync() }) }
  async loginWithPasskey () {
    this.returnUrl = ''
    await this.run(async () => {
      await this.command('save', { ...this.config(), enabled: false, targets: [] })
      await this.command('passkey', { host: window.location.hostname })
      await this.waitForLink(true)
      this.sync()
    })
  }
  async waitForLink (external: boolean) {
    const end = Date.now() + 20000
    while (!this.disposed && Date.now() < end) {
      if ((external ? this.externalLink : this.loginLink) || this.state?.phase === 'connected') return
      await new Promise(resolve => setTimeout(resolve, 750))
      this.state = await u1DataRequest<State>('alexa_state', {}, 8000)
      if (this.state.phase === 'offline' || this.state.phase === 'login_required') throw new Error(this.state.message)
    }
    throw new Error(u1t("Ссылка Amazon пока не готова. Нажмите «Обновить»: как только она появится, откройте её отдельной кнопкой. Окна автоматически не закрываются."))
  }
  async completePasskey () { await this.run(async () => { const url = this.returnUrl.trim(); this.returnUrl = ''; await this.command('complete_passkey', { url }) }) }
  async save () { await this.run(async () => { await this.command('save', this.config()); this.sync() }) }
  async test (id: string) { await this.run(async () => { await this.command('save', { ...this.config(), enabled: false }); await this.command('test', { id }); this.enabled = false }) }
  async heard (id: string) { await this.run(async () => { await this.command('heard', { id, confirmed: true }) }) }
  mounted () { this.refresh(); this.timer = window.setInterval(() => { if (!this.busy) this.refresh() }, 5000) }
  beforeDestroy () { this.disposed = true; if (this.timer !== null) window.clearInterval(this.timer) }
}
</script>
<style scoped>
.alexa-actions { display: flex; flex-wrap: wrap; gap: 8px }
.alexa-actions .v-btn { margin: 0 !important; max-width: 100%; height: auto; min-height: 36px; padding: 8px 12px }
.alexa-actions .v-btn >>> .v-btn__content { white-space: normal; line-height: 1.3 }
.alexa-device { padding: 6px 0 12px; border-bottom: 1px solid #8884; margin-bottom: 12px }
</style>
