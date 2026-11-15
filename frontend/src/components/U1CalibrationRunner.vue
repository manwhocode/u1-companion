<template>
<div>
  <v-btn v-if="!inline && !hideLauncher" small outlined @click="open">{{ $u1t("Запустить калибровку") }}</v-btn>
  <u1-settings-content :inline="inline" v-model="opened" persistent content-class="u1-dialog u1-unified-dialog" max-width="620" scrollable>
    <v-card :flat="inline">
      <u1-dialog-close v-if="!inline" @close="opened = false; close()" />
      <v-card-title>{{ $u1t("Запуск калибровки K") }}<v-spacer /></v-card-title>
      <v-card-text>
        <v-alert v-if="message" dense :type="failed ? 'error' : 'info'">{{ message }}</v-alert>
        <p>{{ $u1t("Выберите головки. Принтер последовательно выполнит штатную динамическую калибровку K с нагревом, перемещениями и подачей филамента.") }}</p>
        <p>{{ $u1t("TPU: филамент в головке или податчике. Остальные материалы: филамент в податчике. Если до головки материал ещё не загружен, перед тестом будет выполнена штатная загрузка U1.") }}</p>
        <v-btn small outlined :loading="refreshing" :disabled="running" @click="refresh(false)">{{ $u1t("Обновить датчики") }}</v-btn>
        <div v-for="slot in [0, 1, 2, 3]" :key="slot" class="calibration-head">
          <v-checkbox :input-value="selected.includes(slot)" :label="$u1t('Головка ') + (slot + 1)" :disabled="running || !!reason(slot) || !idle" hide-details dense @change="selectHead(slot, $event)" />
          <p>{{ reason(slot) || ((headLoaded(slot) ? $u1t("Филамент в головке") : $u1t("Филамент в податчике · загрузка перед калибровкой")) + ' · ' + (status.print_task_config?.filament_type[slot] || '')) }}</p>
        </div>
        <v-alert v-if="!idle && !running" dense type="warning">{{ idleReason }}</v-alert>
        <v-checkbox v-model="saveResults" :label="$u1t('Сохранить измеренный K для привязанных катушек')" :disabled="running" dense hide-details />
        <p class="mt-2">{{ $u1t("Используется выбранный режим хранения: общая калибровка филамента или индивидуальная для катушки. Без привязки катушки результат останется в принтере и в этом окне.") }}</p>
        <v-checkbox v-model="acknowledged" :label="$u1t('Зона движения свободна. Подтверждаю штатную загрузку при необходимости, нагрев и движения выбранных головок.')" :disabled="running || !selected.length || !idle" dense />
        <p>{{ $u1t("Очередь выполняется сервисом на принтере. Можно закрыть окно или вкладку: результаты сохранятся автоматически. После перезапуска принтера или сервиса очередь не возобновляется.") }}</p>
        <v-progress-linear v-if="running" indeterminate />
        <p v-if="running">{{ activeSlot === null ? $u1t("Проверка перед запуском…") : $u1t("{p0} головки {p1}…", { p0: phase === 'load' ? $u1t("Штатная загрузка") : $u1t("Калибровка"), p1: activeSlot + 1 }) }}</p>
        <v-alert v-for="row in results" :key="row.slot" dense :type="row.warning ? 'warning' : 'success'">{{ $u1t("Головка") }} {{ row.slot + 1 }} · K {{ row.value }}. {{ row.warning || row.saved }}</v-alert>
        <v-btn v-if="running" small outlined @click="stop">{{ $u1t("Не запускать следующие головки") }}</v-btn>
        <p v-if="running && stopRequested">{{ $u1t("Текущая головка завершит штатную процедуру; следующие запускаться не будут. Для немедленной аварийной остановки используется красная кнопка принтера.") }}</p>
      </v-card-text>
      <v-card-actions class="run-actions">
        <v-spacer />
        <v-btn color="primary" :loading="submitting" :disabled="submitting || running || refreshing || !idle || !selected.length || !acknowledged" @click="start">{{ $u1t("Запустить") }}</v-btn>
        
      </v-card-actions>
    </v-card>
  </u1-settings-content>
</div>
</template>

<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import U1SettingsContent from './U1SettingsContent.vue'
import { Component, Prop } from 'vue-property-decorator'
import { httpClientActions as http } from '@/api/httpClientActions'
import { u1DataRequest } from '@/utils/u1DataClient'
import { assertCalibrationIdle, calibrationHeadReason, calibrationHeadLoaded, calibrationQuery, type CalibrationStatus } from '@/utils/u1CalibrationRun'
interface Job { state: string; activeSlot?: number | null; stopRequested?: boolean; message?: string; results?: {slot: number; value: number; saved: string; warning: string}[] }

@Component({components:{U1SettingsContent}})
export default class U1CalibrationRunner extends Vue {
  @Prop({default:false,type:Boolean}) readonly inline!: boolean
  @Prop({default:false,type:Boolean}) readonly hideLauncher!: boolean
  mounted () { if (this.inline) this.open() }
  opened = false
  refreshing = false
  polling = false
  running = false
  selected: number[] = []
  acknowledged = false
  saveResults = true
  stopRequested = false
  activeSlot: number | null = null
  phase = 'calibrate'
  status: CalibrationStatus = {}
  message = ''
  failed = false
  results: {slot: number; value: number; saved: string; warning: string}[] = []
  timer: number | null = null
  submitting = false
  refreshGeneration = 0
  get idleReason () { try { assertCalibrationIdle(this.status); return '' } catch (error) { return error instanceof Error ? error.message : String(error) } }
  get idle () { return !this.idleReason }
  reason (slot: number) { return calibrationHeadReason(this.status, slot) }
  headLoaded (slot: number) { return calibrationHeadLoaded(this.status, slot) }
  selectHead (slot: number, checked: boolean) {
    this.acknowledged = false
    this.selected = checked && !this.reason(slot) && this.idle ? [...new Set([...this.selected, slot])] : this.selected.filter(head => head !== slot)
  }
  async readStatus () {
    return (await http.get<{result: {status: CalibrationStatus}}>(calibrationQuery)).data.result.status
  }
  async open () {
    this.opened = true
    this.selected = []
    this.acknowledged = false
    this.message = ''
    this.failed = false
    this.refresh(false)
    if (this.timer === null) this.timer = window.setInterval(() => { if (this.opened) this.refresh(true) }, 2000)
  }
  close () {
    this.opened = false
    this.refreshGeneration++
    this.refreshing = false
    this.polling = false
    if (this.timer !== null) window.clearInterval(this.timer)
    this.timer = null
  }
  beforeDestroy () { if (this.timer !== null) window.clearInterval(this.timer) }
  async refresh (silent = false) {
    if (this.polling || this.submitting) return
    const generation = ++this.refreshGeneration
    this.polling = true
    this.refreshing = !silent
    try {
      const result = await Promise.race([
        Promise.all([u1DataRequest<Job>('calibration_run_state', {}, 12000), this.readStatus()]),
        new Promise<never>((_, reject) => window.setTimeout(() => reject(new Error(u1t("Не удалось обновить состояние за 12 секунд. Нажмите «Обновить датчики»."))), 12000))
      ])
      if (!this.opened || generation !== this.refreshGeneration) return
      this.applyJob(result[0])
      this.status = result[1]
      const selected = this.selected.filter(slot => !this.reason(slot))
      if (selected.length !== this.selected.length) this.acknowledged = false
      if (!this.running) this.selected = selected
    } catch (error) { if (this.opened && generation === this.refreshGeneration) { this.status = {}; this.acknowledged = false; this.failed = true; this.message = String(error) } } finally { if (generation === this.refreshGeneration) { this.refreshing = false; this.polling = false } }
  }
  applyJob (job: Job) {
    const wasRunning = this.running
    this.running = ['starting', 'loading', 'calibrating', 'saving', 'finishing'].includes(job.state)
    this.activeSlot = job.activeSlot ?? null
    this.phase = job.state === 'loading' ? 'load' : 'calibrate'
    this.stopRequested = job.stopRequested === true
    this.results = job.results || []
    this.message = job.message || ''
    this.failed = ['failed', 'interrupted'].includes(job.state)
    if (wasRunning && !this.running) this.$emit('finished')
  }
  async stop () {
    try { this.applyJob(await u1DataRequest<Job>('calibration_run_stop')) } catch (error) { this.failed = true; this.message = String(error) }
  }
  async start () {
    if (this.running || this.refreshing || this.submitting || !this.acknowledged || !this.selected.length) return
    this.submitting = true
    this.failed = false
    try {
      const plan = await u1DataRequest<{token: string}>('calibration_run_prepare', { heads: [...this.selected], saveResults: this.saveResults })
      this.applyJob(await u1DataRequest<Job>('calibration_run_start', { token: plan.token }))
      this.acknowledged = false
    } catch (error) {
      this.failed = true
      this.message = String(error) + u1t(" Обновите состояние перед повторным запуском.")
    } finally { this.submitting = false }
  }
}
</script>

<style scoped>
.calibration-head { border-bottom: 1px solid rgba(127,127,127,.25); padding-bottom: 4px }
.calibration-head p { margin: 4px 0 4px 32px; font-size: .85rem }
.run-actions { padding-left: 64px !important; gap: 6px }
.run-actions .v-btn { margin: 0 !important }
</style>
