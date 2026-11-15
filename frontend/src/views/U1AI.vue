<template>
<div class="u1-ai-page">
  <v-alert v-if="settingsOnly && error" dense type="error">{{ error }}</v-alert>
  <template v-if="!settingsOnly">
  
  <v-alert v-if="error" dense type="error" dismissible @input="error = ''">{{ error }}</v-alert>
  <v-alert v-if="!config.enabled" dense type="info">{{ $u1t("Помощник отключён. Подключите аккаунт ChatGPT или API-ключ, выберите модель и разрешите передачу выбранных данных в OpenAI.") }}</v-alert>
  <div class="ai-chat-layout">
    <aside><v-btn outlined small :disabled="busy" @click="newChat">{{ $u1t("Новый диалог") }}</v-btn><details class="ai-history"><summary>{{ $u1t("Диалоги") }}</summary><v-list dense rounded><v-list-item v-for="item in chats" :key="item.id" :disabled="busy" :input-value="chat === item.id" @click="selectChat(item.id)"><v-list-item-content><v-list-item-title>{{ item.title || $u1t("Диалог") }}</v-list-item-title></v-list-item-content><v-btn icon small :disabled="busy" :aria-label="$u1t('Удалить диалог ') + item.title" :title="$u1t('Удалить диалог')" @click.stop="deleteTarget = item"><span aria-hidden="true">×</span></v-btn></v-list-item></v-list></details><v-checkbox class="ai-confirm-toggle" dense hide-details :input-value="config.requireConfirmation !== false" :label="$u1t('Требовать подтверждения действий в чате')" :disabled="busy || loading || saving" @change="setConfirmation" /></aside>
    <v-card outlined class="ai-chat-card">
      <div class="ai-messages" role="log" aria-live="polite">
        <p v-if="!messages.length" class="text--secondary">{{ $u1t("Чем помочь с U1?") }}</p>
        <article v-for="(message, i) in messages" :key="i" :class="['ai-message', message.role]">
          <strong>{{ message.role === 'user' ? $u1t("Вы") : 'GPT' }}</strong><div class="ai-message-text">{{ message.content }}</div>
          <small v-if="message.reads?.length" class="text--secondary">{{ $u1t("Проверено:") }} {{ message.reads.join(', ') }}</small>
          <v-card v-for="proposal in message.proposals || []" :key="proposal.actionId" outlined class="pa-3 mt-2">
            <strong>{{ proposal.summary }}</strong><p class="mb-2">{{ proposal.filename }}</p><p v-if="!decisions[proposal.actionId]" class="text-caption mb-2">{{ $u1t("Это предложение. Принтер ещё не получил команду.") }}</p>
            <p v-if="decisions[proposal.actionId]" role="status">{{ decisions[proposal.actionId] }}</p>
            <div v-else class="ai-actions"><v-btn color="primary" :disabled="busy || expired(proposal)" @click="ask(proposal)">{{ $u1t("Проверить и подтвердить") }}</v-btn><v-btn outlined :disabled="busy" @click="reject(proposal)">{{ $u1t("Отклонить") }}</v-btn></div>
            <small v-if="expired(proposal)">{{ $u1t("Срок подтверждения истёк. Запросите новое предложение.") }}</small>
          </v-card>
        </article>
        <p v-if="busy" role="status">{{ busyLabel }}</p>
      </div>
      <form class="ai-composer" @submit.prevent="send"><v-textarea v-model="draft" outlined dense auto-grow rows="1" max-rows="3" hide-details :label="$u1t('Сообщение GPT')" :disabled="busy || !config.enabled" maxlength="12000" @keydown="composerKey" /><v-btn color="primary" type="submit" :disabled="busy || !draft.trim() || !config.enabled" :loading="busy"><v-icon>{{ sendIcon }}</v-icon><span class="ml-2">{{ $u1t("Отправить") }}</span></v-btn></form>
    </v-card>
  </div>
  <v-btn small text @click="infoOpen = true">{{ $u1t("Дополнительная информация") }}</v-btn><v-dialog v-model="infoOpen" max-width="620" scrollable content-class="u1-dialog u1-unified-dialog"><v-card><u1-dialog-close @close="infoOpen = false" /><v-card-title>{{ $u1t("Дополнительная информация") }}</v-card-title><v-card-text style="max-height:55vh;overflow:auto">  <div class="ai-status"><span>{{ config.enabled ? config.model : $u1t("GPT отключён") }}</span><span>{{ config.access === 'control' ? $u1t("Управление с подтверждением") : $u1t("Только чтение") }}</span><span v-if="usage.requests">{{ $u1t("Запросов:") }} {{ usage.requests }} {{ $u1t("· Вход:") }} {{ usage.inputTokens }} {{ $u1t("· Выход:") }} {{ usage.outputTokens }} {{ $u1t("токенов") }}</span></div>
  <p class="text-caption mt-2">U1: {{ printer?.webhooks?.state || $u1t("неизвестно") }} · {{ printer?.print_stats?.state || $u1t("нет данных о задании") }}<span v-if="printer?.print_stats?.filename"> · {{ printer.print_stats.filename }}</span><v-btn x-small text :disabled="loading" @click="load">{{ $u1t("Обновить статус") }}</v-btn></p>
  <p class="text-caption">{{ $u1t("Стоимость не рассчитывается без подтверждённого тарифа. Использование OpenAI API учитывается отдельно.") }}</p>
<h3>{{ $u1t("История AI-действий") }}</h3><p v-for="(item, i) in audit.slice().reverse()" :key="i" class="text-caption mb-1">{{ date(item.time) }} · {{ item.kind }}<span v-if="item.tool"> · {{ item.tool }}</span></p><p v-if="!audit.length">{{ $u1t("Действий пока нет.") }}</p></v-card-text></v-card></v-dialog>
  <v-dialog :value="!!deleteTarget" max-width="440" content-class="u1-dialog u1-unified-dialog" @input="!$event && (deleteTarget = null)"><v-card><u1-dialog-close @close="deleteTarget = null" /><v-card-title>{{ $u1t("Удалить диалог?") }}</v-card-title><v-card-text>{{ deleteTarget?.title }}<p>{{ $u1t("Сообщения и неподтверждённые предложения этого диалога будут удалены.") }}</p><v-btn color="error" :disabled="busy" @click="deleteChat">{{ $u1t("Удалить диалог") }}</v-btn></v-card-text></v-card></v-dialog>
  </template>
  <div v-if="settingsOnly" class="ai-settings-only"><v-card :flat="settingsOnly"><u1-dialog-close v-if="!settingsOnly" @close="settingsOpen = false" /><v-card-title>{{ $u1t("Настройки GPT") }}</v-card-title><v-card-text>
    <v-alert v-if="settingsError" dense type="error">{{ settingsError }}</v-alert>
    <v-alert v-if="!secure" dense type="info">{{ $u1t("Для ввода API-ключа откройте доверенный HTTPS.") }}<v-btn text color="primary" :href="httpsUrl">{{ $u1t("Открыть HTTPS") }}</v-btn></v-alert>
    <v-select v-model="edit.provider" outlined dense :label="$u1t('Способ подключения')" :items="[{text:$u1t('ChatGPT / Codex · вход по коду без API-ключа'),value:'codex'},{text:$u1t('Аккаунт ChatGPT · вход с помощником'),value:'chatgpt'},{text:$u1t('OpenAI API · ключ'),value:'api'}]" />
    <section v-if="edit.provider === 'codex'">
      <p>{{ $u1t("Вход по одноразовому коду на странице OpenAI. Можно войти в свой аккаунт через Google. Ничего скачивать на ПК не требуется. Используется доступ и лимиты Codex вашей подписки; доступны чтение и управление с отдельным подтверждением каждого действия.") }}</p>
      <v-alert v-if="codex.connected" type="success" dense>{{ $u1t("Аккаунт подключён. Сохраните способ подключения, загрузите модели и включите GPT.") }}</v-alert>
      <v-btn outlined :loading="busy" :disabled="busy || !secure" @click="beginCodex">{{ $u1t("Войти через OpenAI · получить код") }}</v-btn>
      <div v-if="deviceLogin?.pending" class="my-3">
        <p>{{ $u1t("Код входа:") }} <strong style="font-size:24px;user-select:all">{{ deviceLogin.code }}</strong></p>
        <QrcodeVue :value="deviceLogin.url" :size="160" level="M" />
        <v-btn outlined :href="deviceLogin.url" target="_blank" rel="noopener noreferrer">{{ $u1t("Открыть страницу OpenAI") }}</v-btn>
        <p>{{ $u1t("Отсканируйте QR или откройте ссылку, войдите и введите код. После подтверждения статус обновится автоматически. Если OpenAI требует разрешить вход по коду, включите его в настройках безопасности ChatGPT.") }}</p>
      </div>
      <v-alert v-if="codex.login?.error" type="error" dense>{{ codex.login.error }}</v-alert>
    </section>
    <section v-if="edit.provider === 'chatgpt'">
      <p>{{ $u1t("Первый вход выполняется с Windows-ПК. Скачайте помощник, распакуйте ZIP и откройте Start.cmd. Входите только на странице OpenAI. Код подключения действует 10 минут. Пароль и токены в ZIP не записываются.") }}</p>
      <v-btn outlined :disabled="!secure || saving" @click="pairAccount()">Continue with ChatGPT</v-btn>
      <p v-if="loginNotice" role="status">{{ loginNotice }}</p>
      <v-btn v-if="loginUrl" :href="loginUrl" download="U1-ChatGPT-Login.zip" outlined>{{ $u1t("Скачать помощник входа") }}</v-btn>
      <v-select v-if="accounts.profiles.length" :value="accounts.active" :items="accounts.profiles" item-text="label" item-value="id" outlined dense :label="$u1t('Аккаунт ChatGPT')" @change="selectAccount" />
      <v-btn v-for="p in accounts.profiles.filter(p => !p.connected)" :key="p.id" small outlined @click="pairAccount(p.id)">{{ $u1t("Повторить вход ·") }} {{ p.label }}</v-btn>
      <p>{{ $u1t("Используется лимит вашего аккаунта ChatGPT. Максимум токенов ниже для этого способа подключения не применяется.") }}</p>
      <a href="https://chatgpt.com/settings/usage" target="_blank" rel="noopener noreferrer">{{ $u1t("Лимиты и отключение доступа в ChatGPT") }}</a>
    </section>
    <v-alert v-if="config.hasKey && edit.provider === 'api'" type="success" dense outlined>{{ $u1t("Ключ сохранён на принтере. Пустое поле ниже не означает удаление ключа. Для замены введите новый ключ и сохраните.") }}</v-alert>
    <p v-if="config.hasKey && !config.model" class="text-caption">{{ $u1t("Далее нажмите «Загрузить доступные модели», выберите модель, включите разрешение передачи данных и GPT, затем сохраните настройки.") }}</p>
    <v-text-field v-if="edit.provider === 'api'" v-model="key" type="password" autocomplete="new-password" outlined dense :label="$u1t('API-ключ OpenAI')" :placeholder="config.hasKey ? $u1t('Ключ сохранён на принтере') : $u1t('Введите ключ')" :disabled="!secure || saving" :hint="$u1t('Сохранённый ключ никогда не возвращается в браузер и не входит в экспорт филаментов.')" persistent-hint />
    <v-btn small text href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer">{{ $u1t("Создать ключ в OpenAI") }}</v-btn>
    <v-checkbox v-model="clearKey" :label="$u1t('Удалить сохранённый ключ')" :disabled="!secure || saving || !config.hasKey" />
    <v-combobox v-model="edit.model" :items="models" outlined dense :label="$u1t('Модель OpenAI')" :disabled="saving || busy" :hint="$u1t('Выберите доступную модель или введите её точное имя. Нужна поддержка Responses API и инструментов.')" persistent-hint />
    <div class="ai-actions mb-4"><v-btn outlined :disabled="saving" :loading="saving" @click="save(false)">{{ $u1t("Сохранить настройки") }}</v-btn><v-btn outlined :disabled="saving || busy || !(config.provider === 'codex' ? codex.connected : config.provider === 'chatgpt' ? accounts.profiles.some(p => p.id === accounts.active && p.connected) : config.hasKey)" :loading="modelsLoading" @click="loadModels">{{ $u1t("Загрузить доступные модели") }}</v-btn></div>
    <v-alert v-if="modelError" dense type="error" role="alert" class="mb-3">{{ modelError }}<span v-if="modelError.includes($u1t('отклонил API-ключ'))"> {{ $u1t("Замените его в поле «API-ключ OpenAI», сохраните настройки и повторите загрузку. Ключ создаётся на OpenAI Platform; пароль от ChatGPT сюда не подходит.") }}</span></v-alert>
    <p v-if="modelNotice" role="status" class="mb-3">{{ modelNotice }}</p>
    <v-select v-model="edit.access" outlined dense :label="$u1t('Разрешения')" :items="accessLevels" :disabled="saving" />
    <v-checkbox v-model="edit.consent" :label="$u1t('Разрешаю отправлять сообщения и выбранные данные U1 в OpenAI')" :disabled="saving" />
    <v-switch v-model="edit.enabled" :label="$u1t('Включить GPT')" :disabled="saving" />
    <v-switch v-model="edit.keepHistory" :label="$u1t('Сохранять диалоги на принтере')" :disabled="saving" />
    <v-textarea v-model="edit.instructions" outlined dense rows="3" :label="$u1t('Дополнительные инструкции')" maxlength="6000" :disabled="saving" :hint="$u1t('Не могут расширять разрешения или отключать защиты шлюза.')" persistent-hint />
    <v-row dense><v-col cols="12" sm="6"><v-text-field v-model.number="edit.contextChars" type="number" outlined dense :label="$u1t('История в контексте, символов')" min="4000" max="100000" :hint="$u1t('Инструкции и результаты инструментов добавляются отдельно.')" persistent-hint /></v-col><v-col cols="12" sm="6"><v-text-field v-model.number="edit.maxOutputTokens" type="number" outlined dense :label="$u1t('Максимум токенов ответа')" min="256" max="8000" /></v-col></v-row>
    <v-btn color="primary" block :disabled="saving" :loading="saving" @click="save(true)">{{ $u1t("Сохранить") }}</v-btn>
  </v-card-text></v-card></div>
  <v-dialog v-model="confirmOpen" content-class="u1-dialog u1-unified-dialog" max-width="520"><v-card><u1-dialog-close @close="confirmOpen = false" /><v-card-title>{{ $u1t("Подтверждение действия") }}</v-card-title><v-card-text><h3>{{ selected?.summary }}</h3><p>{{ selected?.filename }}</p><p>{{ $u1t("Приложение повторно проверит текущее задание и ограничения U1. Закрытие чата после отправки не отменяет команду.") }}</p><v-checkbox v-model="confirmed" :label="$u1t('Подтверждаю это действие; зона движения свободна')" /><v-btn color="primary" :disabled="!confirmed || busy || !selected || expired(selected)" @click="confirm">{{ $u1t("Выполнить один раз") }}</v-btn></v-card-text></v-card></v-dialog>
</div>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import QrcodeVue from 'qrcode.vue'
import { Component, Prop } from 'vue-property-decorator'
import { v4 as uuid } from 'uuid'
import { mdiCog, mdiSend } from '@mdi/js'
import { aiRequest } from '@/utils/u1AIClient'
interface Proposal { actionId: string; summary: string; filename?: string; expires: number }
interface Message { role: string; content: string; reads?: string[]; proposals?: Proposal[] }
interface Config { requireConfirmation?: boolean; provider?: string; revision: string; enabled: boolean; consent: boolean; model: string; access: string; instructions: string; keepHistory: boolean; contextChars: number; maxOutputTokens: number; hasKey?: boolean }
interface Job { state: string; message?: string; result?: { chat?: string; message?: Message; models?: string[]; pending?: boolean; code?: string; url?: string } }
interface Accounts { active: string | null; profiles: {id: string; label: string; connected: boolean}[] }
interface DeviceLogin { pending?: boolean; code?: string; url?: string; error?: string }
interface CodexState { connected: boolean; login?: DeviceLogin }
interface State { codex?: CodexState; accounts?: Accounts; settings: Config; busy: boolean; chats: { id: string; title: string }[]; usage: Record<string, number>; audit: { time: number; kind: string; tool?: string }[]; printer: {webhooks?: {state?: string}; print_stats?: {state?: string; filename?: string}}; actions?: {id: string; state: string; sameSession: boolean}[] }
@Component({components:{QrcodeVue}})
export default class U1AI extends Vue {
  @Prop({ default: false, type: Boolean }) readonly settingsOnly!: boolean
  codex: CodexState = {connected:false}
  deviceLogin: DeviceLogin | null = null
  async beginCodex () {
    if (this.busy) return
    this.busy=true; this.settingsError=''; this.busyLabel=u1t("Подготавливаю одноразовый код OpenAI…")
    try { const r=await aiRequest<{job:string}>('codex/login',{}); const result=await this.wait(r.job); this.deviceLogin=result } catch(e) {this.settingsError=(e as Error).message} finally {this.busy=false}
  }
  accounts: Accounts = {active:null, profiles:[]}
  loginNotice = ''
  loginUrl = ''
  async pairAccount (profile?: string) {
    this.settingsError = ''; this.saving = true
    try {
      const r = await aiRequest<{zip:string}>('account/pair', profile ? {profile} : {})
      if (this.loginUrl) URL.revokeObjectURL(this.loginUrl)
      this.loginUrl = URL.createObjectURL(new Blob([Uint8Array.from(atob(r.zip), c => c.charCodeAt(0))], {type:'application/zip'}))
      this.loginNotice = u1t("Помощник готов. После успешного входа нажмите «Обновить статус», сохраните способ подключения и загрузите модели.")
    } catch (e) { this.settingsError = (e as Error).message } finally { this.saving = false }
  }
  async selectAccount (profile: string) { try { this.accounts = await aiRequest<Accounts>('account/select',{profile}); this.models=[] } catch(e) { this.settingsError=(e as Error).message } }
  settingsIcon = mdiCog
  sendIcon = mdiSend
  config: Config = { provider: 'api', revision: '', enabled: false, consent: false, model: '', access: 'read', instructions: '', keepHistory: true, contextChars: 24000, maxOutputTokens: 2000 }
  edit = { ...this.config }
  settingsOpen = false
  settingsError = ''
  key = ''
  clearKey = false
  models: string[] = []
  modelsLoading = false
  modelError = ''
  modelNotice = ''
  error = ''
  busy = false
  busyLabel = u1t("GPT отвечает…")
  loading = false
  saving = false
  alive = true
  timer: number | null = null
  draft = ''
  chat = uuid()
  chats: State['chats'] = []
  deleteTarget: {id: string; title: string} | null = null
  messages: Message[] = []
  usage: Record<string, number> = {}
  audit: State['audit'] = []
  printer: State['printer'] | null = null
  decisions: Record<string, string> = {}
  selected: Proposal | null = null
  confirmOpen = false
  confirmed = false
  get accessLevels () { return [{ text: u1t("Только чтение"), value: 'read' }, { text: u1t("Управление · каждое действие подтверждается"), value: 'control' }] }
  get secure () { return window.isSecureContext && window.location.protocol === 'https:' }
  get httpsUrl () { const url = new URL(window.location.href); url.protocol = 'https:'; return url.href }
  date (seconds: number) { return new Date(seconds * 1000).toLocaleString(this.$i18n.locale) }
  expired (p: Proposal) { return Date.now() / 1000 >= p.expires }
  async load () {
    if (this.loading) return
    this.loading = true
    try {
      const s = await aiRequest<State>('state'); this.config = s.settings; this.codex=s.codex || {connected:false}; if (this.codex.connected) this.deviceLogin=null; this.accounts = s.accounts || {active:null,profiles:[]}; this.chats = s.chats; this.usage = s.usage; this.audit = s.audit; this.printer = s.printer
      for (const a of s.actions || []) {
        if (a.state !== 'pending') this.$set(this.decisions, a.id, ({ completed: u1t("Выполнено приложением."), rejected: u1t("Отклонено."), sent: u1t("Отправлено; проверьте результат на U1."), needs_review: u1t("Нет подтверждённого результата. Повтор запрещён.") } as Record<string, string>)[a.state] || a.state)
        else if (!a.sameSession) this.$set(this.decisions, a.id, u1t("Предложение из другой сессии. Запросите новое для подтверждения."))
      }
    } catch (e) { this.error = (e as Error).message } finally { this.loading = false }
  }
  openSettings () { this.edit = { ...this.config }; this.settingsError = ''; this.clearKey = false; this.settingsOpen = true }
  async save (close: boolean) {
    this.saving = true; this.settingsError = ''
    const { hasKey, ...edit } = this.edit
    try { this.config = await aiRequest<Config>('settings', { ...edit, ...(this.key ? { apiKey: this.key.trim() } : {}), ...(this.clearKey ? { clearKey: true } : {}) }); this.edit = { ...this.config }; if (close) this.settingsOpen = false } catch (e) { this.settingsError = (e as Error).message } finally { this.key = ''; this.clearKey = false; this.saving = false }
  }
  async wait (job: string): Promise<NonNullable<Job['result']>> {
    const deadline = Date.now() + 900000
    while (this.alive && Date.now() < deadline) {
      const value = await aiRequest<Job>('jobs/' + job)
      if (value.state === 'completed') return value.result || {}
      if (['failed', 'needs_review'].includes(value.state)) throw new Error(value.message || u1t("Запрос не выполнен."))
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
    throw new Error(u1t("Ожидание прекращено. Проверьте историю; повторного запроса нет."))
  }
  async loadModels () {
    if (this.busy || this.modelsLoading) return
    this.busy = true; this.modelsLoading = true; this.modelError = ''; this.modelNotice = u1t("Загружаю список моделей OpenAI…"); this.busyLabel = u1t("Проверяю модели OpenAI…")
    try {
      const r = await aiRequest<{job: string}>('models', {})
      this.models = (await this.wait(r.job)).models || []
      this.modelNotice = this.models.length ? u1t("Загружено моделей: ") + this.models.length + u1t(". Откройте поле «Модель OpenAI» и выберите модель.") : u1t("OpenAI вернул пустой список моделей. Проверьте доступ проекта или аккаунта.")
    } catch (e) { this.modelError = (e as Error).message; this.modelNotice = '' } finally { this.busy = false; this.modelsLoading = false }
  }
  async deleteChat () { if (!this.deleteTarget || this.busy) return; const id = this.deleteTarget.id; try { await aiRequest('chats/delete', { id, confirmed: true }); if (this.chat === id) this.newChat(); this.deleteTarget = null; await this.load() } catch (e) { this.error = (e as Error).message } }
  newChat () { this.chat = uuid(); this.messages = []; this.decisions = {}; this.error = '' }
  async selectChat (id: string) { if (this.busy) return; try { const h = await aiRequest<{messages: Message[]}>('chats/' + id); this.chat = id; this.messages = h.messages; await this.load() } catch (e) { this.error = (e as Error).message } }
  async setConfirmation (value: boolean) { this.saving = true; this.error = ''; try { this.config = await aiRequest<Config>('settings', { revision: this.config.revision, requireConfirmation: value }); this.edit = { ...this.config } } catch (e) { this.error = (e as Error).message } finally { this.saving = false } }
  infoOpen = false
  composerKey (event: KeyboardEvent) { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); if (!this.busy && this.config.enabled && this.draft.trim()) this.send() } }
  async send () {
    if (this.busy || !this.draft.trim()) return
    const text = this.draft.trim(); this.draft = ''; this.busy = true; this.error = ''; this.busyLabel = u1t("GPT готовит ответ…")
    this.messages.push({ role: 'user', content: text })
    try { const job = await aiRequest<{job: string}>('chat', { text, chat: this.chat }); const r = await this.wait(job.job); if (r.message) this.messages.push(r.message) } catch (e) { this.error = (e as Error).message } finally { this.busy = false; await this.load() }
  }
  ask (p: Proposal) { this.selected = p; this.confirmed = false; this.confirmOpen = true }
  async reject (p: Proposal) { try { await aiRequest('actions/reject', { id: p.actionId }); this.$set(this.decisions, p.actionId, u1t("Отклонено")) } catch (e) { this.error = (e as Error).message } }
  async confirm () {
    if (!this.selected || !this.confirmed || this.busy) return
    const id = this.selected.actionId; this.confirmOpen = false; this.busy = true; this.busyLabel = u1t("Ожидаю подтверждения от U1…")
    this.$set(this.decisions, id, u1t("Отправляется. Повтор запрещён."))
    try { const j = await aiRequest<{job: string}>('actions/confirm', { id, confirmed: true }); await this.wait(j.job); this.$set(this.decisions, id, u1t("Приложение подтвердило выполнение. Проверьте принтер.")) } catch (e) { this.$set(this.decisions, id, (e as Error).message) } finally { this.busy = false; await this.load() }
  }
  async mounted () { await this.load(); if (this.settingsOnly) this.openSettings();  }
  beforeDestroy () { if (this.loginUrl) URL.revokeObjectURL(this.loginUrl); this.alive = false; this.key = ''; if (this.timer !== null) window.clearInterval(this.timer) }
}
</script>
<style scoped>
.u1-ai-page { max-width:1300px;margin:auto }.ai-header { display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px }.ai-header h1 { font-size:28px }.ai-header p { margin-bottom:0;opacity:.65 }.ai-status { display:flex;gap:12px;flex-wrap:wrap;font-size:12px }.ai-chat-layout { display:grid;grid-template-columns:220px minmax(0,1fr);gap:14px }.ai-chat-card { height:clamp(320px,55vh,560px);min-height:0;display:flex;flex-direction:column;border-radius:14px }.ai-chat-layout aside { max-height:560px;overflow:auto }.ai-messages { flex:1;min-height:0;overflow:auto;padding:16px }.ai-message { padding:12px;margin-bottom:12px;border-radius:10px;background:rgba(127,127,127,.08) }.ai-message.user { margin-left:20px;background:rgba(130,180,60,.1) }.ai-message-text { white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55;margin-top:5px }.ai-composer { flex-shrink:0;display:flex;align-items:flex-end;gap:8px;padding:12px;border-top:1px solid rgba(127,127,127,.2) }.ai-actions { display:flex;gap:8px;flex-wrap:wrap }.ai-actions .v-btn { letter-spacing:0;text-transform:none }
@media(max-width:700px) { .ai-chat-layout { grid-template-columns:1fr }.ai-chat-layout aside .v-list { max-height:120px;overflow:auto }.ai-header h1 { font-size:24px }.ai-composer { flex-wrap:wrap }.ai-composer .v-input { flex-basis:100% }.ai-composer .v-btn { width:100% }.ai-messages { padding:8px;max-height:55vh }.ai-message { padding:9px }.ai-message.user { margin-left:12px } }
</style>

<style scoped>
.ai-chat-layout { display:block }
.ai-chat-layout aside { display:flex;gap:8px;align-items:center;overflow:visible;max-height:none;margin-bottom:8px }
.ai-history { position:relative }.ai-history summary { cursor:pointer;padding:6px 10px;border:1px solid #8886;border-radius:4px;font-size:12px }
.ai-history .v-list { position:absolute;left:0;top:100%;width:260px;max-height:200px;overflow:auto;z-index:10;box-shadow:0 5px 16px #0008 }
.ai-chat-card { height:auto;min-height:0;max-height:320px }
.ai-messages { min-height:64px;max-height:200px;padding:8px;flex:1 1 auto }
.ai-messages > p { margin-bottom:4px }.ai-header { margin-bottom:6px }.ai-header h2 { font-size:16px }
.ai-composer { padding:6px;gap:6px;flex-wrap:nowrap }.ai-composer .v-input { flex:1;min-width:0 }.ai-composer .v-btn { width:auto;min-width:40px;font-size:12px }
.ai-message { padding:8px;margin-bottom:6px }.ai-message-text { line-height:1.4 }
@media(max-width:700px) { .ai-composer .v-input { flex-basis:auto }.ai-history .v-list { max-height:180px }.ai-chat-card { max-height:300px } }
</style>

<style scoped>
.ai-chat-layout aside { flex-wrap:wrap }.ai-chat-layout aside > .v-btn,.ai-history summary { height:32px;min-height:32px;box-sizing:border-box;display:flex;align-items:center;margin:0 }.ai-confirm-toggle { margin:0 0 0 auto;padding:0 }.ai-confirm-toggle >>> label { font-size:12px;line-height:1.25 }
@media(max-width:600px) { .ai-confirm-toggle { margin-left:0;flex-basis:100% } }
</style>
