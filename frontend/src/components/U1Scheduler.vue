<template>
<div class="mb-3">
  <v-btn small outlined @click="open">{{ $u1t("Отложенный запуск") }}</v-btn>
  <v-alert v-if="job && ['armed','starting','blocked','needs_review'].includes(job.state)" dense :type="job.state === 'armed' ? 'info' : 'warning'" class="mt-2 mb-1">
    {{ job.filename || $u1t("Расписание") }} · {{ status(job.state) }}<span v-if="job.state === 'armed'"> {{ $u1t("· до старта") }} {{ countdown }}</span><br>{{ job.message }}
    <v-btn small outlined class="ml-2" @click="open">{{ $u1t("Открыть") }}</v-btn>
  </v-alert>
  <v-dialog v-model="opened" content-class="u1-maintenance-dialog u1-unified-dialog" max-width="800" scrollable>
    <v-card>
      <u1-dialog-close @close="opened = false" />
      <v-card-title>{{ $u1t("Отложенный запуск U1") }}<v-spacer /></v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" dense>{{ error }}</v-alert>
        <v-card v-if="job?.filename" outlined class="pa-3 mb-3">
          <strong>{{ job.filename }} · {{ status(job.state) }}</strong>
          <p>{{ job.message }}<br>{{ $u1t("Старт:") }} {{ date(job.startAt) }}<br>{{ $u1t("Прогноз окончания:") }} {{ date(job.finishAt) }}</p>
          <v-btn v-if="['armed','blocked','needs_review'].includes(job.state)" outlined color="primary" :disabled="busy" @click="cancel">{{ $u1t("Отменить расписание") }}</v-btn>
          <v-btn v-if="job.mapping && job.state !== 'starting'" outlined class="ml-2" :disabled="busy" @click="edit">{{ $u1t("Перенести / изменить") }}</v-btn>
          <p v-if="job.state === 'started' || job.state === 'starting'" class="mt-2">{{ $u1t("Отмена расписания не останавливает запущенную печать. Используйте штатную отмену печати.") }}</p>
        </v-card>
        <v-autocomplete v-model="filename" :items="files" :label="$u1t('G-code, уже загруженный на принтер')" outlined dense @change="clearPlan" />
        <v-select v-model="mode" :items="modes" :label="$u1t('Режим запуска')" outlined dense @change="clearPlan" />
        <v-text-field v-if="mode === 'delay'" v-model.number="delayMinutes" type="number" min="1" max="43200" :label="$u1t('Через сколько минут')" outlined dense @input="clearPlan" />
        <u1-date-field v-else v-model="when" datetime :label="mode === 'finish' ? $u1t('Желаемое время окончания') : $u1t('Дата и время старта')" outlined dense @input="clearPlan" />
        <v-text-field v-model.number="preparationMinutes" type="number" min="0" max="120" :label="$u1t('Запас на прогрев и подготовку, минут')" outlined dense @input="clearPlan" />
        <p>{{ $u1t("Окончание — прогноз слайсера плюс этот запас, точное время не гарантировано. До запуска — от 1 минуты до 30 дней. Одновременно хранится одно активное расписание.") }}</p>
        <v-row dense>
          <v-col v-for="(_, index) in mapping" :key="index" cols="6" sm="3"><v-select v-model="mapping[index]" :items="heads" :label="$u1t('Филамент T') + (index + 1)" outlined dense @change="clearPlan" /></v-col>
        </v-row>
        <v-checkbox v-model="bedLevel" :label="$u1t('Штатное выравнивание стола при запуске')" @change="clearPlan" />
        <v-checkbox v-model="flowCalibration" :label="$u1t('Штатная динамическая калибровка K при запуске')" @change="clearPlan" />
        <v-btn color="primary" outlined :loading="busy" :disabled="busy || !filename || job?.state === 'starting'" @click="prepare">{{ $u1t("Проверить и рассчитать") }}</v-btn>
        <v-card v-if="plan" outlined class="pa-3 mt-3">
          <h3>{{ $u1t("Проверь расписание") }}</h3>
          <p>{{ plan.filename }}<br>{{ $u1t("Старт:") }} <strong>{{ date(plan.startAt) }}</strong><br>{{ $u1t("Прогноз окончания:") }} {{ date(plan.finishAt) }}</p>
          <div v-for="row in plan.rows" :key="row.logical">T{{ row.logical + 1 }} {{ $u1t("→ головка") }} {{ row.head + 1 }} · {{ row.name }} · {{ row.material }} {{ row.hex }} {{ $u1t("· нужно") }} {{ grams(row.required) }} {{ $u1t("г, есть") }} {{ grams(row.remaining) }} {{ $u1t("г") }}</div>
          <v-checkbox v-model="bedClear" :label="$u1t('Стол свободен, модель снята, зона движения проверена')" />
          <v-checkbox v-model="consent" :label="$u1t('Я разрешаю автоматический запуск в назначенное время, учитывая риск печати без присмотра')" />
          <v-btn color="primary" :disabled="busy || !bedClear || !consent" :loading="busy" @click="arm">{{ job?.state === 'armed' ? $u1t("Заменить расписание") : $u1t("Сохранить и разрешить запуск") }}</v-btn>
        </v-card>
        <p class="mt-3">{{ $u1t("Перед запуском повторно проверяются файл, катушки, сопла, датчики филамента, ошибки, крышка, нагрев и очередь. При изменениях запуск отменяется. Привяжите «Мои катушки» к используемым головкам: запас должен покрывать расход файла.") }}</p>
        <p>{{ $u1t("Расписание выполняется службой на принтере при выключенном ПК. Принтер должен быть включён. После пропущенного времени, изменения системного времени или неопределённого ответа автоповтора нет — нужна проверка и новый перенос.") }}</p>
        <p>{{ $u1t("Расписание сохраняется отдельно от библиотеки и входит в полный установочный бэкап папки данных. Импорт библиотеки не создаёт и не разрешает расписание. Предупреждения отображаются в открытом Fluidd; Alexa добавляется отдельным пунктом в конце ТЗ.") }}</p>
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
interface Plan {
  id: string; filename: string; startAt: number; finishAt: number; mapping: number[]; mode: string; preparationMinutes: number;
  options: { bed_level: number; flow_calibrate: number };
  rows: { logical: number; head: number; name: string; material: string; hex: string; required: number; remaining: number }[];
}
interface Job extends Partial<Plan> { state: string; message: string; updatedAt?: number; now: number }
@Component
export default class U1Scheduler extends Vue {
  opened = false
  busy = false
  loading = false
  error = ''
  files: string[] = []
  filename = ''
  mode = 'delay'
  get modes () { return [{ text: u1t("Через интервал"), value: 'delay' }, { text: u1t("В назначенное время"), value: 'at' }, { text: u1t("Закончить к указанному времени"), value: 'finish' }] }
  delayMinutes = 30
  when = ''
  preparationMinutes = 10
  mapping = [0, 1, 2, 3]
  heads = [0, 1, 2, 3].map(value => ({ value, text: u1t("Головка ") + (value + 1) }))
  bedLevel = true
  flowCalibration = false
  bedClear = false
  consent = false
  plan: Plan | null = null
  job: Job | null = null
  serverNow = 0
  lastNotice = ''
  timer: number | null = null
  clock: number | null = null
  clearPlan () { this.plan = null; this.consent = false; this.bedClear = false }
  grams (value: number) { return value.toLocaleString(this.$i18n.locale, { maximumFractionDigits: 1 }) }
  date (value?: number) { return value ? new Date(value * 1000).toLocaleString(this.$i18n.locale) : '—' }
  status (value: string) { return ({ idle: u1t("Нет расписания"), armed: u1t("Ожидает старта"), starting: u1t("Передача запроса"), started: u1t("Запрос принят U1"), cancelled: u1t("Отменено"), blocked: u1t("Запуск отменён проверкой"), needs_review: u1t("Нужна проверка") } as Record<string, string>)[value] || value }
  get countdown () { const seconds = Math.max(0, Math.ceil((this.job?.startAt || 0) - this.serverNow)); return Math.floor(seconds / 3600) + u1t(" ч ") + Math.floor(seconds % 3600 / 60) + u1t(" мин ") + seconds % 60 + u1t(" с") }
  async open () {
    this.opened = true
    this.load()
    try { const response = await http.get<{result: {path: string}[]}>('/server/files/list?root=gcodes'); this.files = response.data.result.filter(item => item.path.toLowerCase().endsWith('.gcode')).map(item => item.path) } catch { this.error = u1t("Не удалось получить список файлов.") }
  }
  async edit () { if (this.job?.state === 'armed') { await this.cancel(); if (this.job?.state === 'armed') return } if (!this.job?.filename || !this.job.mapping || !this.job.options) return; this.filename = this.job.filename; this.mapping = [...this.job.mapping]; this.mode = 'at'; this.when = ''; this.bedLevel = !!this.job.options.bed_level; this.flowCalibration = !!this.job.options.flow_calibrate; this.clearPlan() }
  async action<T> (operation: string, payload: object) {
    this.busy = true
    try { const value = await u1DataRequest<T>(operation, payload); this.error = ''; return value } catch (error) { this.error = (error as Error).message; return null } finally { this.busy = false }
  }
  async prepare () {
    this.clearPlan()
    this.plan = await this.action<Plan>('schedule_prepare', { filename: this.filename, mode: this.mode, mapping: this.mapping, delayMinutes: this.delayMinutes, when: this.when ? new Date(this.when).getTime() / 1000 : null, preparationMinutes: this.preparationMinutes, bedLevel: this.bedLevel, flowCalibration: this.flowCalibration })
  }
  async arm () { if (!this.plan) return; const job = await this.action<Job>('schedule_arm', { planId: this.plan.id, consent: this.consent, bedClear: this.bedClear }); if (job) { this.job = job; this.serverNow = job.now; this.clearPlan() } }
  async cancel () { if (!this.job) return; const job = await this.action<Job>('schedule_cancel', { id: this.job.id }); if (job) this.job = job }
  async load () {
    if (this.loading || this.busy) return
    this.loading = true
    try {
      const job = await u1DataRequest<Job>('schedule_state'); this.job = job; this.serverNow = job.now
      if (['blocked', 'needs_review'].includes(job.state) && this.lastNotice !== job.state + job.updatedAt) { this.lastNotice = job.state + job.updatedAt; this.$store.dispatch('notifications/pushNotification', { type: 'warning', title: u1t("U1: отложенный запуск требует проверки"), description: job.message, snackbar: true, merge: true }) }
    } catch (error) { if (this.opened) this.error = (error as Error).message } finally { this.loading = false }
  }
  mounted () { this.load(); this.timer = window.setInterval(() => this.load(), 10000); this.clock = window.setInterval(() => { this.serverNow++ }, 1000) }
  beforeDestroy () { if (this.timer !== null) window.clearInterval(this.timer); if (this.clock !== null) window.clearInterval(this.clock) }
}
</script>
