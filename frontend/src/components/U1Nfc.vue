<template>
<v-dialog content-class="u1-dialog u1-unified-dialog" v-model="opened" max-width="600" @input="onDialog">
  <v-card class="pa-5 nfc-card">
      <u1-dialog-close @close="opened = false; close()" />
    <h2>{{ mode === 'write' ? $u1t("Записать NFC-метку NTAG216") : $u1t("Считать NFC-метку") }}</h2>
    <v-alert v-if="status" type="info">{{ status }}</v-alert>
    <div v-if="mode === 'write' && preset">
      <p>{{ preset.name }} · {{ preset.manufacturer }} {{ preset.material }} {{ preset.hex }}</p>
      <v-btn v-if="webNfc" block color="primary" class="mb-2" :disabled="working" @click="writeAndroid">{{ $u1t("Записать метку · Android") }}</v-btn>
      <p><strong>Android.</strong> {{ $u1t("Включите NFC и откройте страницу по доверенному HTTPS в Chrome для записи прямо из браузера.") }}</p>
      <p><strong>{{ $u1t("iPhone и Android через приложение.") }}</strong> {{ $u1t("В NFC Tools выберите Write → Add a record → URL, вставьте полную ссылку, нажмите Write и поднесите NTAG216 к телефону.") }}</p>
      <v-textarea ref="tagField" :value="url" readonly outlined dense rows="3" :label="$u1t('Ссылка для NFC-метки')" />
      <div class="nfc-copy-actions">
        <v-btn outlined :disabled="working" @click="copy">{{ $u1t("Копировать ссылку") }}</v-btn>
        <v-btn outlined :disabled="working" @click="copyAddress">{{ $u1t("Без протокола") }}</v-btn>
      </div>
      <v-btn v-if="nfcToolsUrl" block color="primary" class="mb-2" :disabled="working" @click="copyAndOpenTools">
        {{ isiOS ? $u1t("Скопировать и открыть NFC Tools") : $u1t("Скопировать и перейти в Google Play") }}
      </v-btn>
      <details v-if="isiOS" class="mb-2">
        <summary>{{ $u1t("Настройка запуска NFC Tools на iPhone") }}</summary>
        <p>{{ $u1t("Один раз создайте в «Командах» команду «NFC Tools U1» с действием «Открыть приложение» и выберите NFC Tools.") }}</p>
      </details>
      <p v-else-if="nfcToolsUrl">{{ $u1t("В Google Play нажмите «Открыть», если NFC Tools уже установлено.") }}</p>
      <p>{{ $u1t("Записывается перезаписываемая NDEF-ссылка с материалом, HEX и производителем. Блокировка метки не включается.") }}</p>
    </div>
    <div v-if="mode === 'read' && !preset">
      <p v-if="target !== null">{{ $u1t("Чтение для головки") }} {{ target + 1 }}</p>
      <v-btn v-if="webNfc" color="primary" :disabled="working" @click="readAndroid">{{ $u1t("Считать метку · Android") }}</v-btn>
      <p v-else>{{ $u1t("На iPhone поднесите NTAG216 к верхней части разблокированного телефона и откройте уведомление. На Android включите NFC и поднесите метку к задней панели либо прочитайте её через NFC Tools.") }}</p>
      <p>{{ $u1t("Прочитанную ссылку можно вставить сюда вручную.") }}</p>
      <p>{{ $u1t("Если запись делалась через NFC Tools, выберите именно URL, а не обычный текст. Для работы нужна домашняя сеть принтера.") }}</p>
      <v-textarea v-model="manual" :label="$u1t('Или вставьте прочитанную NFC-ссылку')" />
      <v-btn @click="accept(manual)">{{ $u1t("Прочитать ссылку") }}</v-btn>
    </div>
    <div v-if="mode === 'read' && preset">
      <h3>{{ preset.name || $u1t("Филамент с метки") }}</h3><p>{{ preset.manufacturer }} · {{ preset.material }} · {{ preset.hex }}</p>
      <p aria-live="polite">{{ remainingLabel }}</p>
      <v-btn class="ma-1" @click="add">{{ $u1t("Добавить как новый филамент") }}</v-btn>
      <v-select v-model="slot" :items="slots" :label="$u1t('Номер головки')" />
      <v-btn class="ma-1" color="primary" @click="select">{{ $u1t("Установить в головку") }} {{ slot + 1 }}</v-btn>
    </div>
    <v-btn v-if="working" @click="cancelScan">{{ $u1t("Отменить ожидание метки") }}</v-btn>
    
  </v-card>
</v-dialog>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import { Component, Prop } from 'vue-property-decorator'
import { tagUrl, tagAddress, parseTag, readerConstructor, type NfcPreset, type NfcEvent } from '@/utils/nfcFilament'
import clipboardCopy from '@/util/clipboard-copy'
const targetKey = 'u1-nfc-head-target'
const shortcutName = 'NFC Tools U1'
@Component
export default class U1Nfc extends Vue {
  @Prop({ required: true }) readonly lookupRemaining!: (spoolId: string) => Promise<number | null>
  opened = false
  mode = 'read'
  preset: NfcPreset | null = null
  status = ''
  manual = ''
  slot = 0
  target: number | null = null
  slots = [0, 1, 2, 3].map(value => ({ value, text: u1t("Головка {p0}", { p0: value + 1 }) }))
  working = false
  remainingLabel = ''
  controller: AbortController | null = null
  get webNfc () { return window.isSecureContext && !!readerConstructor() }
  get isiOS () { return /iPhone|iPad|iPod/i.test(navigator.userAgent) || (/Macintosh/i.test(navigator.userAgent) && navigator.maxTouchPoints > 1) }
  get nfcToolsUrl () {
    if (this.isiOS) return 'shortcuts://run-shortcut?name=' + encodeURIComponent(shortcutName)
    if (/Android/i.test(navigator.userAgent)) return 'https://play.google.com/store/apps/details?id=com.wakdev.wdnfc'
    return ''
  }
  get url () { return this.preset ? tagUrl(this.preset, window.location.origin) : '' }
  beforeDestroy () { this.cancelScan() }
  writePreset (preset: NfcPreset) {
    this.close()
    this.preset = { ...preset }; this.mode = 'write'; this.status = ''; this.opened = true
  }

  readPreset (slot: number | null = null) {
    this.cancelScan()
    this.preset = null; this.mode = 'read'; this.slot = 0; this.target = slot
    this.status = ''; this.manual = ''; this.opened = true
    try {
      if (slot === null) localStorage.removeItem(targetKey)
      else localStorage.setItem(targetKey, `${slot}:${Date.now() + 120000}`)
    } catch { /* Pasting the link still works in the open dialog. */ }
    if (slot !== null && this.webNfc) this.readAndroid()
  }

  accept (raw: string, fromLink = false) {
    try {
      const preset = parseTag(raw)
      let target = this.opened && this.mode === 'read' ? this.target : null
      if (fromLink && target === null) {
        const [slot, expires] = (localStorage.getItem(targetKey) || '').split(':').map(Number)
        if (Number.isInteger(slot) && slot >= 0 && slot < 4 && expires > Date.now()) target = slot
      }
      if (target !== null) {
        this.close()
        this.$emit('select', { slot: target, preset })
      } else {
        this.cancelScan()
        this.preset = preset; this.mode = 'read'; this.opened = true
        this.status = u1t("Метка прочитана. Выберите действие.")
        this.loadRemaining(preset)
      }
    } catch (e) { this.status = String(e) }
  }
  async loadRemaining (preset: NfcPreset) {
    if (!preset.spoolId) {
      this.remainingLabel = u1t("На метке нет ID катушки. Остаток доступен для меток из «Моих катушек».")
      return
    }
    this.remainingLabel = u1t("Загружаю остаток филамента…")
    try {
      const grams = await this.lookupRemaining(preset.spoolId)
      if (this.opened && this.mode === 'read' && this.preset === preset) {
        this.remainingLabel = grams === null ? u1t("Катушка отсутствует в «Моих катушках».") : u1t("Остаток филамента: {p0} г", { p0: grams })
      }
    } catch {
      if (this.opened && this.mode === 'read' && this.preset === preset) this.remainingLabel = u1t("Не удалось получить остаток филамента с принтера.")
    }
  }
  async copy () {
    this.status = await clipboardCopy(this.url, (this.$refs.tagField as Vue | undefined)?.$el)
      ? u1t("Ссылка скопирована. Вставьте её в запись URL в NFC Tools.")
      : u1t("Выделите и скопируйте ссылку вручную.")
  }
  async copyAddress () {
    const address = tagAddress(this.url)
    this.status = await clipboardCopy(address, (this.$refs.tagField as Vue | undefined)?.$el)
      ? u1t("Адрес скопирован без протокола.")
      : u1t("Скопируйте адрес вручную: ") + address
  }
  async copyAndOpenTools () {
    const destination = this.nfcToolsUrl
    if (!destination || !this.preset) return
    const field = (this.$refs.tagField as Vue | undefined)?.$el
    if (!await clipboardCopy(this.url, field)) {
      this.status = u1t("Выделите и скопируйте ссылку вручную.")
      return
    }
    this.status = u1t("Ссылка скопирована. В NFC Tools вставьте её в запись URL.")
    window.location.assign(destination)
  }
  async writeAndroid () {
    const Constructor = readerConstructor(); if (!Constructor || !this.preset) return
    this.controller = new AbortController(); this.working = true; this.status = u1t("Приложите NTAG216 к телефону. Запись заменит её текущую NDEF-запись.")
    try { await new Constructor().write({ records: [{ recordType: 'url', data: this.url }] }, { signal: this.controller.signal }); this.status = u1t("Телефон подтвердил запись метки. Проверьте её кнопкой чтения.") } catch (e) { this.status = String(e) } finally { this.working = false }
  }
  async readAndroid () {
    const Constructor = readerConstructor(); if (!Constructor) return
    const controller = new AbortController()
    this.controller = controller; this.working = true
    const reader = new Constructor()
    reader.addEventListener('reading', event => {
      if (controller.signal.aborted) return
      const records = (event as NfcEvent).message.records
      for (const record of records) if (record.recordType === 'url' || record.recordType === 'text') {
        try { const raw = new TextDecoder(record.encoding || 'utf-8').decode(record.data); parseTag(raw); this.accept(raw); return } catch { /* try next NDEF record */ }
      }
      this.status = u1t("Метка прочитана, но на ней нет совместимых данных U1.")
    })
    reader.addEventListener('readingerror', () => { this.status = u1t("Не удалось прочитать метку. Поднесите ближе.") })
    try {
      await reader.scan({ signal: controller.signal })
      if (!controller.signal.aborted) this.status = u1t("Приложите NTAG216 к задней части телефона.")
    } catch (e) {
      if (!controller.signal.aborted) { this.status = String(e); this.working = false }
    }
  }
  cancelScan () { this.controller?.abort(); this.controller = null; this.working = false }
  onDialog (opened: boolean) { if (!opened) this.close() }
  close () {
    this.cancelScan()
    this.opened = false; this.target = null
    try { localStorage.removeItem(targetKey) } catch { /* Storage can be disabled. */ }
  }
  add () { if (this.preset) this.$emit('add', this.preset); this.close() }
  select () { if (this.preset) this.$emit('select', { slot: this.slot, preset: this.preset }); this.close() }
}
</script>

<style scoped>
.nfc-copy-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; margin-bottom: 8px }
.nfc-card .v-btn { min-height: 40px; padding-inline: 5px; text-transform: none; letter-spacing: normal }
</style>
