<template>
<div class="u1-maintenance mb-3">
  <div class="maintenance-toolbar">
    <v-btn small outlined @click="opened = true; load()">{{ $u1t("Обслуживание U1") }}</v-btn>
    <small v-if="state?.value">{{ $u1t("Общая наработка:") }} {{ hours(state.totalSeconds) }} {{ $u1t("ч") }}</small>
  </div>
  <v-alert v-if="state?.serviceDue" dense type="warning" class="mt-2 mb-1">{{ state.value?.service ? $u1t("Пора выполнить обслуживание U1.") : $u1t("Дата обслуживания неизвестна. Подтвердите выполненные работы в разделе «Обслуживание U1».") }}</v-alert>
  <v-alert v-if="state?.bedDue" dense type="info" class="mt-2 mb-1"><div class="maintenance-bed-notice"><span>{{ state.value?.bed ? $u1t("Пора выполнить штатную калибровку стола.") : $u1t("Последняя калибровка стола не отмечена. Подтвердите её после выполнения.") }}</span><v-btn small outlined :disabled="saving || state.calibrationActive" @click="bedConfirmOpen = true">{{ $u1t("Выполнить калибровку") }}</v-btn></div></v-alert>
  <v-alert v-if="state?.bedCalibration?.message && (state.calibrationActive || ['failed', 'interrupted'].includes(state.bedCalibration.state))" dense :type="state.bedCalibration.state === 'failed' || state.bedCalibration.state === 'interrupted' ? 'warning' : 'info'" class="mt-2 mb-1">{{ state.bedCalibration.message }}</v-alert>
  <v-alert v-if="error || state?.message" dense type="warning" class="mt-2">{{ error || state?.message }}</v-alert>
  <v-dialog v-model="opened" content-class="u1-maintenance-dialog u1-unified-dialog" max-width="760" scrollable>
    <v-card>
      <u1-dialog-close @close="opened = false" />
      <v-card-title>{{ $u1t("Обслуживание U1") }}<v-spacer /></v-card-title>
      <v-card-text v-if="state?.value">
        <p>{{ $u1t("Активная печать без пауз:") }} <strong>{{ hours(state.totalSeconds) }} {{ $u1t("ч") }}</strong>{{ $u1t(". Завершённых печатей в доступной истории:") }} {{ state.completedPrints }}.</p>
        <p>{{ $u1t("Исходная наработка взята из штатной истории U1. Удалённые до установки записи могут не содержать деталей. Счётчики сохраняются при перезагрузке; нагрев и ожидание не добавляются по часам на компьютере.") }}</p>
        <v-btn outlined class="mb-3" :disabled="saving" @click="openPeriods">{{ $u1t("Периоды и уведомления") }}</v-btn>
        <v-card outlined class="pa-3 mb-3">
          <h3>{{ $u1t("Обслуживание") }}</h3>
          <p>{{ $u1t("Последнее подтверждение:") }} {{ date(state.value.service?.time) }}<br>{{ $u1t("После обслуживания:") }} {{ state.serviceSeconds === null ? $u1t("неизвестно") : hours(state.serviceSeconds) + $u1t(" ч") }} <br>{{ intervalSummary('service') }}<br>{{ $u1t("Календарный срок:") }} {{ date(state.serviceDueAt) }}.</p>
          <p>{{ $u1t("Напоминание срабатывает по первому выбранному сроку. Общая наработка не обнуляется.") }}</p>
          <v-btn color="primary" outlined :disabled="saving" @click="ask('service')">{{ $u1t("Обслуживание выполнено") }}</v-btn>
        </v-card>
        <v-card outlined class="pa-3 mb-3">
          <h3>{{ $u1t("Калибровка стола") }}</h3>
          <v-switch :input-value="state.value.bedEnabled" :disabled="saving" :label="$u1t('Напоминать о калибровке стола')" @change="toggleBed" />
          <p>{{ $u1t("Последнее подтверждение:") }} {{ date(state.value.bed?.time) }}<br>{{ $u1t("После калибровки:") }} {{ state.bedSeconds === null ? $u1t("неизвестно") : hours(state.bedSeconds) + $u1t(" ч") }} · {{ state.bedPrints === null ? $u1t("неизвестно") : state.bedPrints }} {{ $u1t("завершённых печатей.") }}<br>{{ intervalSummary('bed') }}</p>
          <div class="bed-calibration-actions"><v-btn color="primary" :disabled="saving || state.calibrationActive" @click="bedConfirmOpen = true">{{ $u1t("Выполнить калибровку") }}</v-btn>
          <v-btn color="primary" outlined :disabled="saving" @click="ask('bed')">{{ $u1t("Калибровка стола выполнена") }}</v-btn></div>
          <p class="mt-2">{{ $u1t("Кнопка только фиксирует уже выполненную штатную калибровку. Отмена или ошибка печати не увеличивает число завершённых печатей, но потраченное активное время учитывается.") }}</p>
        </v-card>
        <h3>{{ $u1t("Что проверять на U1") }}</h3>
        <p>{{ $u1t("Металлические направляющие/линейные подшипники — очистка и подходящая смазка по инструкции. Карбоновые направляющие X — очистка, без масла и смазки. Винты Z, контакты и ремни обслуживаются по своим интервалам из руководства; напоминание 100 ч / месяц — заданный вами общий интервал.") }}</p>
        <v-btn small outlined href="https://wiki.snapmaker.com/en/snapmaker_u1/troubleshooting/Core_Components_Maintenance_Guide.md" target="_blank" rel="noopener noreferrer">{{ $u1t("Руководство Snapmaker ↗") }}</v-btn>
        <p class="mt-3">{{ $u1t("Предупреждения видны в открытом Fluidd на всех страницах и повторяются при запуске через Fluidd. Печать не блокируется. В штатное приложение Snapmaker и закрытый браузер уведомления пока не отправляются.") }}</p>
        <v-alert v-if="error" type="error" dense>{{ error }}</v-alert>
        <v-alert v-if="state.message" type="warning" dense>{{ state.message }}</v-alert>
        <h3 class="mt-4">{{ $u1t("История подтверждений") }}</h3>
        <v-data-table :headers="historyHeaders" :items="state.value.history" item-key="id" :items-per-page="5" sort-by="time" :sort-desc="true" :no-data-text="$u1t('Подтверждений пока нет.')">
          <template #item.time="{ item }">{{ date(item.time) }}</template>
          <template #item.kind="{ item }">{{ item.kind === 'service' ? $u1t("Обслуживание") : $u1t("Калибровка стола") }}</template>
          <template #item.seconds="{ item }">{{ hours(item.seconds) }} {{ $u1t("ч") }}</template>
        </v-data-table>
      </v-card-text>
      <v-card-text v-else>{{ $u1t("Счётчики ещё не получены.") }} {{ error || state?.message }}</v-card-text>
      
    </v-card>
  </v-dialog>
  <v-dialog v-model="bedConfirmOpen" content-class="u1-maintenance-dialog u1-unified-dialog" max-width="560">
    <v-card><u1-dialog-close @close="bedConfirmOpen = false" /><v-card-title>{{ $u1t("Калибровка стола") }}</v-card-title><v-card-text>
      <p>{{ $u1t("Освободите стол и установите печатную пластину. U1 выполнит штатную калибровку с нагревом стола до 55 °C и движениями. После успеха отметка сохранится автоматически. Окно можно закрыть.") }}</p>
      <v-checkbox v-model="bedConfirmed" :label="$u1t('Стол освобождён, печатная пластина установлена')" />
      <v-alert v-if="error" dense type="error">{{ error }}</v-alert>
      <v-btn block color="primary" :disabled="!bedConfirmed || saving || state?.calibrationActive" :loading="saving" @click="startBed">{{ $u1t("Выполнить калибровку") }}</v-btn>
    </v-card-text></v-card>
  </v-dialog>
  <v-dialog v-model="periodsOpen" content-class="u1-maintenance-dialog u1-unified-dialog" max-width="650" scrollable>
    <v-card><u1-dialog-close @close="periodsOpen = false" /><v-card-title>{{ $u1t("Периоды и уведомления") }}</v-card-title><v-card-text>
      <p>{{ $u1t("Пустое поле отключает отдельный критерий. Напоминание срабатывает по первому достигнутому сроку. Выключение напоминаний убирает сообщения в приложении и Alexa; счётчики и история сохраняются.") }}</p>
      <v-card v-for="kind in periodKinds" :key="kind.key" outlined class="pa-3 mb-3">
        <h3>{{ kind.label }}</h3><v-switch v-model="periodDraft[kind.key].enabled" :label="$u1t('Напоминать')" :disabled="saving" />
        <v-row dense><v-col v-for="field in periodFields" :key="field.key" cols="6"><v-text-field v-model="periodDraft[kind.key][field.key]" type="number" min="1" :max="field.max" :label="field.label" outlined dense clearable hide-details :disabled="saving" /></v-col></v-row>
      </v-card>
      <v-alert v-if="error" dense type="error">{{ error }}</v-alert><v-btn block color="primary" :loading="saving" :disabled="saving" @click="savePeriods">{{ $u1t("Сохранить периоды") }}</v-btn>
    </v-card-text></v-card>
  </v-dialog>
  <v-dialog v-model="confirmOpen" content-class="u1-maintenance-dialog u1-unified-dialog" max-width="490">
    <v-card>
      <u1-dialog-close @close="confirmOpen = false" />
      <v-card-title>{{ $u1t("Подтверждение выполненных работ") }}</v-card-title>
      <v-card-text>
        <p>{{ action === 'service' ? $u1t("Записать обслуживание и начать новый настроенный интервал?") : $u1t("Записать калибровку стола и начать новый настроенный интервал?") }}</p>
        <v-checkbox v-model="confirmed" :label="$u1t('Я выполнил эти работы на принтере')" />
        <v-alert v-if="error" dense type="error">{{ error }}</v-alert>
      </v-card-text>
      <v-card-actions class="maintenance-actions"><v-btn outlined color="primary" @click="confirmOpen = false">{{ $u1t("Отмена") }}</v-btn><v-spacer /><v-btn color="primary" :disabled="!confirmed || saving" :loading="saving" @click="confirm">{{ $u1t("Подтвердить") }}</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</div>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'


import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
interface Period { enabled: boolean; hours: number | null; days: number | null; months: number | null; prints: number | null }
interface Marker { time: number; seconds: number; completed: number }
interface State {
  value: { revision: string; service: Marker | null; bed: Marker | null; bedEnabled: boolean; history: (Marker & { id: string; kind: string })[] } | null;
  periods?: {service: Period; bed: Period};
  bedCalibration?: {state: string; message: string} | null; calibrationActive?: boolean;
  totalSeconds: number; completedPrints: number; serviceSeconds: number | null; bedSeconds: number | null; bedPrints: number | null;
  serviceDueAt: number | null; serviceDue: boolean; bedDue: boolean; checkedAt: number; message: string;
}
@Component
export default class U1Maintenance extends Vue {
  periodsOpen = false
  get periodKinds (): {key: 'service' | 'bed'; label:string}[] { return [{key: 'service', label: u1t("Обслуживание")}, {key: 'bed', label: u1t("Калибровка стола")}] }
  get periodFields (): {key: 'hours' | 'days' | 'months' | 'prints'; label:string; max:number}[] { return [{key: 'hours', label: u1t("Активная печать, ч"), max: 100000}, {key: 'days', label: u1t("Календарных дней"), max: 36500}, {key: 'months', label: u1t("Календарных месяцев"), max: 120}, {key: 'prints', label: u1t("Завершённых печатей"), max: 100000}] }
  periodDraft: {service: Period; bed: Period} = {service: {enabled: true, hours: 100, days: null, months: 1, prints: null}, bed: {enabled: true, hours: 10, days: null, months: null, prints: 5}}
  get configuredPeriods () { return this.state?.periods || { service: { enabled: true, hours: 100, days: null, months: 1, prints: null }, bed: { enabled: this.state?.value?.bedEnabled !== false, hours: 10, days: null, months: null, prints: 5 } } }
  openPeriods () { this.periodDraft = JSON.parse(JSON.stringify(this.configuredPeriods)) as typeof this.periodDraft; this.error = ''; this.periodsOpen = true }
  intervalSummary (kind: 'service' | 'bed') { const p = this.configuredPeriods[kind]; if (!p.enabled) return u1t("Напоминания отключены"); return this.periodFields.filter(f => p[f.key] !== null).map(f => String(p[f.key]) + ' ' + f.label.toLowerCase()).join(' / ') }
  async savePeriods () {
    const value = JSON.parse(JSON.stringify(this.periodDraft)) as typeof this.periodDraft
    for (const kind of this.periodKinds) for (const field of this.periodFields) {
      const raw: unknown = value[kind.key][field.key]
      const n = raw === '' || raw === null ? null : Number(raw)
      if (n !== null && (!Number.isInteger(n) || n < 1 || n > field.max)) { this.error = u1t("Укажите положительные целые интервалы или оставьте поле пустым."); return }
      value[kind.key][field.key] = n
    }
    if (await this.change({ action: 'periods', value })) this.periodsOpen = false
  }
  opened = false
  bedConfirmOpen = false
  bedConfirmed = false
  confirmOpen = false
  confirmed = false
  action: 'service' | 'bed' = 'service'
  state: State | null = null
  error = ''
  saving = false
  loading = false
  timer: number | null = null
  get historyHeaders () { return [{ text: u1t("Дата"), value: 'time' }, { text: u1t("Работы"), value: 'kind' }, { text: u1t("Общая наработка"), value: 'seconds' }] }
  hours (value: number) { return (value / 3600).toLocaleString(this.$i18n.locale, { maximumFractionDigits: 2 }) }
  date (value?: number | null) { return value == null ? u1t("не указана") : new Date(value * 1000).toLocaleDateString(this.$i18n.locale) }
  ask (action: 'service' | 'bed') { this.action = action; this.confirmed = false; this.error = ''; this.confirmOpen = true }
  notify () {
    if (!this.state) return
    if (this.state.serviceDue || this.state.bedDue) this.$store.dispatch('notifications/pushNotification', { type: 'warning', title: u1t("U1: проверьте обслуживание перед печатью"), description: [this.state.serviceDue ? u1t("Нужно обслуживание или его первое подтверждение.") : '', this.state.bedDue ? u1t("Нужна калибровка стола или её первое подтверждение.") : ''].filter(Boolean).join(' '), snackbar: true, merge: true })
  }
  async load () {
    if (this.loading || this.saving) return
    this.loading = true
    try { this.state = await u1DataRequest<State>('maintenance_state'); this.error = '' } catch (error) { this.error = (error as Error).message } finally { this.loading = false }
  }
  async startBed () {
    if (this.saving || !this.bedConfirmed) return
    this.saving = true
    try {
      const plan = await u1DataRequest<{token: string}>('bed_calibration_prepare')
      const job = await u1DataRequest<{state: string; message: string}>('bed_calibration_start', {token: plan.token, confirmed: true})
      if (this.state) { this.state.bedCalibration = job; this.state.calibrationActive = true }
      this.error = ''; this.bedConfirmOpen = false; this.bedConfirmed = false
    } catch (error) { this.error = (error as Error).message } finally { this.saving = false }
  }
  async change (payload: object) {
    if (!this.state?.value || this.saving) return false
    this.saving = true
    try { this.state = await u1DataRequest<State>('maintenance_change', { revision: this.state.value.revision, ...payload }); this.error = ''; return true } catch (error) { this.error = (error as Error).message; return false } finally { this.saving = false }
  }
  async confirm () { if (this.confirmed && await this.change({ action: this.action, confirmed: true, timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' })) this.confirmOpen = false }
  toggleBed (enabled: boolean) { this.change({ action: 'bed_enabled', enabled }) }
  mounted () { this.load(); this.timer = window.setInterval(() => this.load(), 15000); window.addEventListener('u1-before-print', this.notify) }
  beforeDestroy () { if (this.timer !== null) window.clearInterval(this.timer); window.removeEventListener('u1-before-print', this.notify) }
}
</script>
<style>
.u1-maintenance-dialog { margin: 5px !important; max-height: calc(100dvh - 10px) !important; border-radius: 12px }
@media (max-width: 600px) { .u1-maintenance-dialog { max-width: calc(100vw - 10px) !important } }
.u1-maintenance-dialog .v-card__title { overflow-wrap: anywhere; word-break: normal }
.u1-maintenance-dialog input { font-size: 16px !important }
.maintenance-actions { padding-left: 64px !important; flex-wrap: wrap; gap: 8px }
.maintenance-toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap }
.maintenance-bed-notice { display: flex; align-items: center; gap: 12px; flex-wrap: wrap }
.maintenance-bed-notice span { flex: 1 1 280px }
</style>

<style scoped>.bed-calibration-actions {display:flex;gap:10px;align-items:stretch;flex-wrap:wrap}.bed-calibration-actions .v-btn {margin:0!important;min-height:40px;height:auto;white-space:normal;flex:1 1 240px}.bed-calibration-actions .v-btn >>> .v-btn__content {white-space:normal;padding:8px 0}</style>
