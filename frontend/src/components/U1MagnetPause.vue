<template>
<div class="magnet-controls">
  <div class="magnet-buttons">
    <v-btn outlined :disabled="busy || !state?.available || !active || state?.parked" @click="openManual">{{ $u1t("Пауза · стол вниз") }}</v-btn>
    <v-btn outlined @click="openPlan">{{ $u1t("Паузы по слоям · магниты") }}</v-btn>
    <slot />
  </div>
  <p v-if="state?.message" class="mt-2 mb-0">{{ state.message }}</p>
  <p v-if="nextLayer" class="mb-0">{{ $u1t("Следующая пауза: перед слоем") }} {{ nextLayer }}.</p>
  <v-alert v-if="error" dense type="warning" dismissible @input="error = ''" class="mt-2 mb-0">{{ error }}</v-alert>
  <v-dialog v-model="planOpen" content-class="u1-dialog u1-unified-dialog" max-width="650" scrollable>
    <v-card>
      <u1-dialog-close @close="planOpen = false" />
      <v-card-title>{{ $u1t("Паузы для магнитов") }}</v-card-title>
      <v-card-text>
        <v-tabs class="magnet-tabs mb-4" :value="mode === 'next' ? 0 : 1" grow @change="switchMode($event === 0 ? 'next' : 'current')">
          <v-tab :disabled="busy">{{ $u1t("Паузы при запуске") }}</v-tab>
          <v-tab :disabled="busy">{{ $u1t("Текущая печать") }}</v-tab>
        </v-tabs>
        <v-alert v-if="error" dense type="error" dismissible @input="error = ''">{{ error }}</v-alert>
        <v-alert v-if="!state?.available" dense type="warning">{{ $u1t("Модуль пауз недоступен.") }}</v-alert>
        <v-alert v-if="modeReason" dense type="info">{{ modeReason }}</v-alert>
        <p>{{ $u1t("Перед выбранным слоем U1 приостановит печать и опустит стол в парковочное положение, как при окончании. После установки магнитов продолжите печать вручную.") }}</p>
        <template v-if="mode === 'next'">
          <p>{{ $u1t("Выберите загруженный файл и сохраните паузы до запуска. Затем запустите этот файл с ПК, из приложения Snapmaker или через плеер. Сохранение плана само печать не запускает.") }}</p>
          <v-autocomplete v-model="filename" :items="files" :label="$u1t('G-code на принтере')" outlined dense :disabled="busy || active" :loading="filesLoading" @change="reset" />
        </template>
        <template v-else>
          <p v-if="active"><strong>{{ filename }}</strong><br>{{ $u1t("Сейчас слой") }} {{ state?.currentLayer || 0 }}{{ $u1t(". Укажите только будущие слои — выбирать файл заново не нужно.") }}</p>
          <v-btn v-if="active && planJob !== state?.runtimeJob" outlined :disabled="busy" @click="refreshCurrent">{{ $u1t("Обновить текущую печать") }}</v-btn>
        </template>
        <v-text-field v-model="layers" :label="$u1t('Слои для паузы')" placeholder="12, 24 36" :hint="$u1t('Номера с 1, через запятую или пробел. Пауза перед началом слоя.')" persistent-hint outlined dense :disabled="busy || !!modeReason" @input="reset" />
        <v-btn outlined :disabled="busy || !state?.available || !!modeReason || !filename || !layers.trim()" :loading="work === 'prepare'" @click="prepare">{{ $u1t("Проверить слои и файл") }}</v-btn>
        <template v-if="plan">
          <p class="mt-3">{{ plan.filename }} {{ $u1t("· всего") }} {{ plan.total }} {{ $u1t("слоёв") }}<br>{{ $u1t("Паузы перед слоями:") }} <strong>{{ plan.layers.join(', ') }}</strong></p>
          <v-checkbox v-model="confirmed" :label="$u1t('Разрешаю паузы и опускание стола на этих слоях. Продолжение — только вручную после установки магнитов.')" :disabled="busy" />
          <v-btn color="primary" :disabled="busy || !confirmed || !!modeReason" :loading="work === 'arm'" @click="arm">{{ mode === 'current' ? $u1t("Добавить паузы в текущую печать") : $u1t("Сохранить паузы перед запуском") }}</v-btn>
        </template>
        <v-divider class="my-4" />
        <p v-if="state?.layers?.length">{{ $u1t("Сохранённые слои:") }} {{ state.layers.join(', ') }}<br>{{ $u1t("Уже выполнены:") }} {{ state.done?.join(', ') || $u1t("нет") }}</p>
        <v-btn v-if="['armed','active','waiting_insertion','blocked','needs_review'].includes(state?.state || '')" outlined :disabled="busy" @click="clear">{{ $u1t("Отменить будущие паузы") }}</v-btn>
        <p class="mt-4">{{ $u1t("Не перемещайте стол вручную и не выключайте принтер. Перед продолжением проверьте, что магниты не выступают над печатным слоем и инструменты убраны. При потере координат продолжение блокируется.") }}</p>
      </v-card-text>
    </v-card>
  </v-dialog>
  <v-dialog v-model="manualOpen" content-class="u1-dialog u1-unified-dialog" max-width="520">
    <v-card>
      <u1-dialog-close @close="manualOpen = false" />
      <v-card-title>{{ $u1t("Пауза с опусканием стола") }}</v-card-title>
      <v-card-text>
        <p>{{ state?.currentFilename }}</p>
        <p>{{ $u1t("U1 выполнит штатную паузу и припаркует стол вниз для установки магнитов. Это движение стола; зона должна быть свободна. Автотаймер продолжения отключится.") }}</p>
        <v-alert v-if="error" dense type="error" dismissible @input="error = ''">{{ error }}</v-alert>
        <v-checkbox v-model="manualConfirmed" :label="$u1t('Зона движения свободна. Разрешаю паузу и опускание стола.')" :disabled="busy" />
        <v-btn color="primary" :disabled="busy || !manualConfirmed || manualJob !== state?.runtimeJob" :loading="work === 'pause'" @click="lower">{{ $u1t("Пауза и опустить стол") }}</v-btn>
      </v-card-text>
    </v-card>
  </v-dialog>
</div>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'



import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
import { httpClientActions as http } from '@/api/httpClientActions'
interface State { available: boolean; state: string; message: string; runtimeJob: string; currentFilename: string; printState: string; currentLayer: number; parked: boolean; layers?: number[]; done?: number[]; token?: string }
interface Plan { token: string; filename: string; layers: number[]; total: number; mode: string }
@Component
export default class U1MagnetPause extends Vue {
  state: State | null = null
  plan: Plan | null = null
  planOpen = false
  manualOpen = false
  manualConfirmed = false
  manualJob = ''
  mode = 'next'
  planJob = ''
  layers = ''
  filename = ''
  nextFilename = ''
  files: string[] = []
  filesLoading = false
  confirmed = false
  error = ''
  pendingAck: { token?: string; job?: string; action: string } | null = null
  work = ''
  loading = false
  timer: number | null = null
  get busy () { return this.work !== '' }
  get active () { return ['printing', 'paused'].includes(this.state?.printState || '') }
  get modeReason () {
    if (this.mode === 'next' && this.active) return u1t("Печать уже идёт. Откройте вкладку «Текущая печать», чтобы добавить паузы в неё.")
    if (this.mode === 'current' && !this.active) return u1t("Сейчас печать не идёт. Запустите её с ПК или приложения, затем откройте эту вкладку.")
    if (this.mode === 'current' && this.planJob !== this.state?.runtimeJob) return u1t("Задание изменилось. Обновите текущую печать перед настройкой пауз.")
    return ''
  }
  get nextLayer () { return ['armed', 'active', 'pausing', 'waiting_insertion'].includes(this.state?.state || '') ? this.state?.layers?.find(n => !this.state?.done?.includes(n)) : undefined }
  reset () { this.plan = null; this.confirmed = false }
  switchMode (mode: 'next' | 'current') {
    if (this.mode === 'next') this.nextFilename = this.filename
    this.mode = mode; this.error = ''; this.reset()
    this.filename = mode === 'current' ? this.state?.currentFilename || '' : this.nextFilename
    this.planJob = mode === 'current' ? this.state?.runtimeJob || '' : ''
  }
  async refreshCurrent () { await this.load(); this.switchMode('current') }
  async load () {
    if (this.loading || this.busy) return
    this.loading = true
    try {
      this.state = await u1DataRequest<State>('magnet_state', {}, 12000)
      const p = this.pendingAck; const s = this.state
      const matched = p && (p.action === 'arm' ? s.token === p.token && ['armed', 'active', 'pausing', 'waiting_insertion', 'finished'].includes(s.state) : p.action === 'pause' ? s.runtimeJob === p.job && s.parked && s.printState === 'paused' : s.token === p.token && s.state === 'cancelled')
      if (matched && /timed? ?out|timeout|Сервис пока не ответил/i.test(this.error)) { this.error = ''; this.pendingAck = null }
    } catch { this.state = null } finally { this.loading = false }
  }
  async openPlan () {
    this.planOpen = true; this.error = ''; this.reset(); await this.load()
    this.switchMode(this.active ? 'current' : 'next')
    this.filesLoading = true
    try { const result = await http.get<{result: {path: string}[]}>('/server/files/list?root=gcodes'); this.files = result.data.result.filter(f => /\.gcode$/i.test(f.path)).map(f => f.path) } catch (error) { this.error = (error as Error).message } finally { this.filesLoading = false }
  }
  openManual () { this.error = ''; this.manualConfirmed = false; this.manualJob = this.state?.runtimeJob || ''; this.manualOpen = true }
  async prepare () {
    if (this.busy || this.modeReason) return
    this.work = 'prepare'; this.error = ''; this.reset()
    try { this.plan = await u1DataRequest<Plan>('magnet_prepare', { filename: this.filename, layers: this.layers, mode: this.mode, job: this.planJob }, 60000) } catch (error) { this.error = (error as Error).message } finally { this.work = '' }
  }
  async arm () {
    if (!this.plan || !this.confirmed || this.busy || this.modeReason) return
    const token = this.plan.token; this.pendingAck = { action: 'arm', token }; this.reset(); this.work = 'arm'; this.error = ''
    try { this.state = await u1DataRequest<State>('magnet_arm', { token, confirmed: true }); this.planOpen = false } catch (error) { this.error = (error as Error).message } finally { this.work = ''; this.load() }
  }
  async clear () { await this.action('clear') }
  async lower () { if (this.manualConfirmed) await this.action('pause') }
  async action (action: 'pause' | 'clear') {
    if (this.busy) return
    this.work = action; this.error = ''; this.pendingAck = { action, job: this.manualJob, token: this.state?.token }
    try { this.state = await u1DataRequest<State>('magnet_action', { action, job: this.manualJob, token: this.state?.token, confirmed: true }, 180000); this.manualOpen = false } catch (error) { this.error = (error as Error).message } finally { this.work = ''; this.load() }
  }
  mounted () { this.load(); this.timer = window.setInterval(() => this.load(), 5000) }
  beforeDestroy () { if (this.timer !== null) window.clearInterval(this.timer) }
}
</script>
<style scoped>
.magnet-controls { margin-top:10px; font-size:13px }
.magnet-tabs >>> .v-tab { min-width:0; padding:8px; white-space:normal; line-height:1.2; letter-spacing:0; text-transform:none }
.magnet-buttons { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:6px }
.magnet-buttons >>> .maintenance-tools, .magnet-buttons >>> .maintenance-tools > div { display:contents !important }
.magnet-buttons > .v-btn, .magnet-buttons >>> .maintenance-tools > div > .v-btn { width:100%; height:44px !important; min-width:0; margin:0; padding:6px; border-radius:4px; font-size:12px; font-weight:600; letter-spacing:0; text-transform:none }
.magnet-buttons >>> .v-btn__content { flex-shrink:1; white-space:normal; line-height:1.2; text-align:center }
.magnet-buttons >>> .maintenance-tools .v-alert { grid-column:1 / -1; order:1 }
@media(max-width:900px) { .magnet-buttons { grid-template-columns:repeat(3,minmax(0,1fr)) } }
@media(max-width:600px) { .magnet-buttons { grid-template-columns:repeat(2,minmax(0,1fr)) } }
</style>
