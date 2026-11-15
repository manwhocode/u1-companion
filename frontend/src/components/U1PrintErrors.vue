<template>
<div>
  <v-btn @click="open">{{ $u1t("История ошибок") }}{{ visibleEvents.length ? ' · ' + visibleEvents.length : '' }}</v-btn>
  <v-dialog v-model="opened" content-class="u1-dialog u1-unified-dialog" max-width="1000" scrollable>
    <v-card>
      <u1-dialog-close @close="opened = false" />
      <v-card-title>{{ $u1t("Ошибки печати") }}<v-spacer /></v-card-title>
      <v-card-text>
        <p>{{ $u1t("Сообщения U1 во время печати и назначенные этому заданию катушки. Связь с катушкой или цветом не означает, что филамент вызвал ошибку.") }}</p>
        <v-alert v-if="error" dense type="warning">{{ error }}</v-alert>
        <v-alert v-else dense :type="healthy ? 'success' : 'warning'">
          {{ healthy ? $u1t("Запись штатных событий U1 подключена.") : (service?.connected ? $u1t("Сообщения получаются, но сохранение требует внимания.") : $u1t("Поток событий недоступен. Кратковременные сообщения могут быть пропущены; периодические наблюдения продолжаются.")) }}
          <span v-if="service?.message"> {{ service.message }}</span>
        </v-alert>
        <v-alert v-if="service?.dropped || service?.unbound" dense type="warning">{{ $u1t("Не сохранено из-за переполнения очереди:") }} {{ service?.dropped || 0 }}{{ $u1t(". Не удалось определить задание:") }} {{ service?.unbound || 0 }}.</v-alert>
        <p v-if="service?.since">{{ $u1t("Журнал подключён с") }} {{ date(service.since) }}{{ $u1t(". Старые ошибки не восстанавливаются по нынешним катушкам. Обычная отмена и ручная пауза сами по себе не считаются ошибкой.") }}</p>
        <u1-log-tools kind="errors" @archive="showArchive = $event" @changed="load(false)" />
        <div class="error-filters">
          <v-text-field v-model="search" :label="$u1t('Поиск по сообщению, коду или файлу')" dense outlined clearable hide-details />
          <v-select v-model="spoolId" :items="spoolItems" :label="$u1t('Катушка')" dense outlined clearable hide-details />
          <v-select v-model="colorId" :items="colorItems" :label="$u1t('Цвет')" dense outlined clearable hide-details />
          <v-text-field v-model="from" :label="$u1t('С даты')" type="date" dense outlined hide-details />
          <v-text-field v-model="to" :label="$u1t('По дату')" type="date" dense outlined hide-details />
        </div>
        <v-btn small outlined class="my-2" :loading="loading" @click="load(false)">{{ $u1t("Обновить журнал") }}</v-btn>
        <v-btn small text class="my-2" @click="resetFilters">{{ $u1t("Сбросить фильтры") }}</v-btn>
        <v-tabs v-model="tab"><v-tab>{{ $u1t("Сообщения ·") }} {{ filtered.length }}</v-tab><v-tab>{{ $u1t("По цветам") }}</v-tab><v-tab>{{ $u1t("На килограмм") }}</v-tab></v-tabs>
        <v-tabs-items v-model="tab">
          <v-tab-item>
            <v-data-table :headers="headers" :items="filtered" item-key="id" :page.sync="page" :items-per-page="10" sort-by="time" :sort-desc="true" :no-data-text="$u1t('Сообщений по выбранным условиям пока нет.')">
              <template #item.time="{ item }">{{ date(item.time) }}<small class="d-block">{{ source(item.source) }}</small></template>
              <template #item.filename="{ item }"><span class="error-message">{{ item.filename }}</span><small class="d-block">{{ $u1t("Задание") }} {{ item.jobId }} · {{ jobStatus(item.jobStatus) }}</small></template>
              <template #item.message="{ item }"><strong>{{ item.code }}</strong><div class="error-message">{{ item.message }}</div></template>
              <template #item.spools="{ item }">
                <div v-for="spool in item.spools" :key="spool.head" class="error-link">
                  <span v-if="spool.hex" class="error-swatch" :style="{backgroundColor: spool.hex}" />{{ $u1t("Головка") }} {{ spool.head + 1 }} · {{ spool.name }}
                  <small class="d-block">{{ spool.colorName || $u1t("Основа не определена") }} · {{ spool.material }} {{ spool.hex }}</small>
                </div>
                <span v-if="!item.spools.length">{{ $u1t("Катушки не определены") }}</span>
              </template>
            </v-data-table>
          </v-tab-item>
          <v-tab-item>
            <p class="mt-3">{{ $u1t("Число сообщений и заданий, в которых был назначен этот цвет. Это история печати, а не оценка качества филамента.") }}</p>
            <v-data-table :headers="colorHeaders" :items="colorSummary" item-key="id" :items-per-page="10" sort-by="messages" :sort-desc="true" :no-data-text="$u1t('Нет сообщений с определённым цветом.')">
              <template #item.name="{ item }"><span class="error-swatch" :style="{backgroundColor: item.hex}" />{{ item.name }}<small class="d-block">{{ item.material }} {{ item.hex }}</small></template>
            </v-data-table>
            <p v-if="unlinkedCount">{{ $u1t("Сообщений без привязки к цвету:") }} {{ unlinkedCount }}{{ $u1t(". Они сохранены во вкладке «Сообщения».") }}</p>
          </v-tab-item>
          <v-tab-item>
            <p class="mt-3">{{ $u1t("Сообщений в сохранённом журнале на 1 кг подтверждённого расхода. Это частота сообщений при печати с этим филаментом, а не причина неисправности.") }}</p>
            <p>{{ $u1t("Даты здесь выбирают задания по дате списания. Учитываются все связанные сообщения этих заданий, даже если они появились днём раньше. В расход включены печати без ошибок и подтверждённые прерванные печати.") }}</p>
            <v-alert v-if="search" dense type="info">{{ $u1t("Текстовый поиск относится к истории сообщений. На этой вкладке действуют только фильтры катушки, цвета и дат.") }}</v-alert>
            <v-alert v-if="from && to && from > to" dense type="warning">{{ $u1t("Дата начала должна быть не позже даты окончания.") }}</v-alert>
            <v-select v-model="rateDimension" :items="rateDimensions" :label="$u1t('Сравнить расход')" dense outlined />
            <v-data-table :headers="rateHeaders" :items="rates.rows" item-key="key" :items-per-page="10" sort-by="grams" :sort-desc="true" :no-data-text="$u1t('Нет подтверждённых списаний с этой привязкой за выбранный период.')">
              <template #item.name="{ item }">{{ item.name }}<small class="d-block">ID: {{ item.key }}</small></template>
              <template #item.grams="{ item }">{{ number(item.grams) }} {{ $u1t("г") }}</template>
              <template #item.perKg="{ item }">{{ item.perKg === null ? '—' : number(item.perKg) }}</template>
            </v-data-table>
            <p v-if="rates.unknownGrams">{{ $u1t("Не включено в сравнение:") }} {{ number(rates.unknownGrams) }} {{ $u1t("г без сохранённой привязки к") }} {{ rateDimension === 'color' ? $u1t("цвету") : $u1t("катушке") }}.</p>
            <p class="mt-3">{{ $u1t("Статистика учитывает весь сохранённый архив, включая очищенные из списка записи. Формула: число связанных сообщений ÷ расход в граммах × 1000. При нулевом расходе — прочерк. Ожидающие подтверждения списания, старые итоги без дат и сообщения без сопоставимой привязки не входят в расчёт. Пропущенные при отключении журнала сообщения восстановить полностью нельзя; ноль означает отсутствие сохранённых сообщений.") }}</p>
          </v-tab-item>
        </v-tabs-items>
        <p class="mt-3">{{ $u1t("«Наблюдение» отмечает время обнаружения при опросе. «Результат задания» означает, что подробное сообщение не было получено. История входит в JSON-экспорт и резервные копии.") }}</p>
      </v-card-text>
      
    </v-card>
  </v-dialog>
</div>
</template>

<script lang="ts">
import { u1t } from '@/plugins/i18n'


import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { readU1Item } from '@/utils/u1DataClient'
import { visibleLogRows } from '@/utils/u1LogLists'
import { errorRateRows, type UsageRecord } from '@/utils/u1SpoolStats'

interface Link { head: number; spoolId: string; name: string; colorId?: string; colorName?: string; material?: string; hex?: string }
interface Event { id: string; jobId: string; filename: string; time: number; source: string; code: string; message: string; severity: number; jobStatus: string; spools: Link[] }
interface Service { connected?: boolean; message?: string; since?: number; dropped?: number; unbound?: number }
interface Usage { archivedErrors?: string[]; records?: UsageRecord[]; errors?: Event[]; errorService?: Service; checkedAt?: number }

@Component
export default class U1PrintErrors extends Vue {
  opened = false
  loading = false
  inflight = false
  events: Event[] = []
  archivedIds: string[] = []
  showArchive = false
  get visibleEvents () { return visibleLogRows(this.events, this.archivedIds, this.showArchive) }
  records: UsageRecord[] = []
  rateDimension: 'spool' | 'color' = 'spool'
  get rateDimensions () { return [{ text: u1t("По катушкам"), value: 'spool' }, { text: u1t("По цветам библиотеки"), value: 'color' }] }
  get rateHeaders () { return [{ text: u1t("Катушка / цвет"), value: 'name' }, { text: u1t("Расход"), value: 'grams' }, { text: u1t("Заданий"), value: 'jobs' }, { text: u1t("Сообщений"), value: 'messages' }, { text: u1t("Заданий с сообщениями"), value: 'errorJobs' }, { text: u1t("Сообщений / кг"), value: 'perKg' }] }
  get rates () { return errorRateRows(this.records, this.events, this.rateDimension, this.from, this.to, this.spoolId, this.colorId) }
  number (value: number) { return value.toLocaleString(this.$i18n.locale, { maximumFractionDigits: 3 }) }
  service: Service | null = null
  healthy = false
  error = ''
  search: string | null = ''
  spoolId: string | null = null
  colorId: string | null = null
  targetLabel = ''
  from = ''
  to = ''
  page = 1
  tab = 0
  timer: number | null = null
  get headers () { return [{ text: u1t("Дата"), value: 'time' }, { text: u1t("Файл"), value: 'filename' }, { text: u1t("Сообщение U1"), value: 'message' }, { text: u1t("Назначенные катушки"), value: 'spools', sortable: false }] }
  get colorHeaders () { return [{ text: u1t("Цвет"), value: 'name' }, { text: u1t("Сообщений"), value: 'messages' }, { text: u1t("Заданий"), value: 'jobs' }] }

  get filtered () {
    const words = (this.search || '').toLocaleLowerCase().trim().split(/\s+/).filter(Boolean)
    const start = this.from ? new Date(this.from + 'T00:00:00').getTime() / 1000 : -Infinity
    const end = this.to ? new Date(this.to + 'T23:59:59.999').getTime() / 1000 : Infinity
    return this.visibleEvents.filter(event => event.time >= start && event.time <= end &&
      (!this.spoolId || event.spools.some(spool => spool.spoolId === this.spoolId)) &&
      (!this.colorId || event.spools.some(spool => spool.colorId === this.colorId)) &&
      words.every(word => `${event.filename} ${event.code} ${event.message} ${event.spools.map(spool => `${spool.name} ${spool.colorName || ''} ${spool.hex || ''}`).join(' ')}`.toLocaleLowerCase().includes(word)))
  }

  options (kind: 'spool' | 'color') {
    const values = new Map<string, string>()
    for (const event of [...this.events].sort((a, b) => b.time - a.time)) for (const spool of event.spools) {
      const id = kind === 'spool' ? spool.spoolId : spool.colorId
      if (id && !values.has(id)) values.set(id, `${kind === 'spool' ? spool.name : (spool.colorName || id)} · ${spool.material || ''} ${spool.hex || ''}`)
    }
    for (const record of this.records) for (const spool of record.rows) {
      const id = kind === 'spool' ? spool.spoolId : spool.colorId
      if (id && !values.has(id)) values.set(id, (kind === 'spool' ? spool.name : spool.colorName) || id)
    }
    const selected = kind === 'spool' ? this.spoolId : this.colorId
    if (selected && !values.has(selected)) values.set(selected, this.targetLabel || selected)
    return [...values].map(([value, text]) => ({ value, text })).sort((a, b) => a.text.localeCompare(b.text, 'ru'))
  }

  get spoolItems () { return this.options('spool') }
  get colorItems () { return this.options('color') }
  get unlinkedCount () { return this.filtered.filter(event => !event.spools.some(spool => spool.colorId)).length }
  get colorSummary () {
    const values = new Map<string, { id: string; name: string; material?: string; hex?: string; events: Set<string>; jobs: Set<string> }>()
    for (const event of this.filtered) for (const spool of event.spools) {
      if (!spool.colorId) continue
      if (this.spoolId && spool.spoolId !== this.spoolId) continue
      if (this.colorId && spool.colorId !== this.colorId) continue
      let row = values.get(spool.colorId)
      if (!row) {
        row = { id: spool.colorId, name: spool.colorName || spool.colorId, material: spool.material, hex: spool.hex, events: new Set(), jobs: new Set() }
        values.set(spool.colorId, row)
      }
      row.events.add(event.id)
      row.jobs.add(event.jobId)
    }
    return [...values.values()].map(row => ({ ...row, messages: row.events.size, jobs: row.jobs.size }))
  }

  date (value: number) { return new Date(value * 1000).toLocaleString(this.$i18n.locale) }
  source (value: string) { return ({ u1: u1t("Событие U1"), observed: u1t("Наблюдение"), history: u1t("Результат задания") } as Record<string, string>)[value] || value }
  jobStatus (value: string) { return ({ in_progress: u1t("в процессе"), completed: u1t("завершено"), cancelled: u1t("отменено"), error: u1t("ошибка"), klippy_shutdown: u1t("Klipper остановлен"), klippy_disconnect: u1t("связь потеряна"), history_missing: u1t("история задания удалена") } as Record<string, string>)[value] || value }
  resetFilters () { this.search = ''; this.spoolId = null; this.colorId = null; this.from = ''; this.to = ''; this.page = 1 }
  open () { this.opened = true; this.load(false) }
  openFor (kind: 'spool' | 'color', id: string, name: string) {
    this.resetFilters()
    this.targetLabel = name
    if (kind === 'spool') this.spoolId = id
    else this.colorId = id
    this.tab = 0
    this.open()
  }
  mounted () { this.load(true); this.timer = window.setInterval(() => this.load(true), 10000) }
  beforeDestroy () { if (this.timer !== null) window.clearInterval(this.timer) }
  async load (silent: boolean) {
    if (this.inflight) return
    this.inflight = true
    this.loading = !silent
    try {
      const value = (await readU1Item<Usage>('u1_spool_usage_v1')).data.result.value
      this.events = value.errors || []
      this.archivedIds = value.archivedErrors || []
      this.records = value.records || []
      this.service = value.errorService || null
      this.healthy = value.errorService?.connected === true && !value.errorService.message && Date.now() / 1000 - (value.checkedAt || 0) < 90
      this.error = ''
    } catch { this.healthy = false; this.error = u1t("Не удалось прочитать историю ошибок. Проверьте подключение к U1.") } finally { this.inflight = false; this.loading = false }
  }
}
</script>

<style scoped>
.error-filters { display: grid; grid-template-columns: repeat(auto-fit,minmax(160px,1fr)); gap: 8px }
.error-message { white-space: pre-wrap; overflow-wrap: anywhere; max-width: 360px }
.error-swatch { display: inline-block; width: 16px; height: 16px; border-radius: 50%; border: 1px solid #999; margin-right: 6px; vertical-align: middle }
.error-link { margin: 4px 0; overflow-wrap: anywhere }
.error-actions { padding-left: 64px !important }
</style>
