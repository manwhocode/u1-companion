<template>
<div class="mb-4">
  <v-btn class="ma-1" @click="openCheck">{{ $u1t("Проверить запас для G-code") }}</v-btn>
  <v-btn class="ma-1" @click="historyOpen = true">{{ $u1t("Списание филамента") }}{{ pending ? $u1t(" · к проверке: ") + pending : '' }}</v-btn>
  <v-alert v-if="error" type="error">{{ error }}</v-alert>
  <v-alert v-if="active?.changed" type="warning">{{ $u1t("Во время печати изменились головки или филамент. Списание потребует проверки.") }}</v-alert>
  <v-alert v-for="row in shortages" :key="row.head" type="warning">
    {{ $u1t("Головка") }} {{ row.head + 1 }} · {{ row.name }}{{ $u1t(". Не хватает примерно") }} {{ format(row.shortage) }} {{ $u1t("г.") }}
    <span v-if="row.seconds !== null && !active?.paused">{{ $u1t("Замена") }} {{ eta(row.seconds) }} {{ $u1t("по среднему расходу.") }}</span>
  </v-alert>
  <v-dialog content-class="u1-dialog u1-unified-dialog" v-model="checkOpen" max-width="760" scrollable>
    <v-card>
      <u1-dialog-close @close="checkOpen = false" />
      <v-card-title>{{ $u1t("Запас филамента для печати") }}</v-card-title>
      <v-card-text>
        <v-alert v-if="checkError" type="warning">{{ checkError }}</v-alert>
        <v-autocomplete v-model="filename" :items="files" :loading="loadingFiles" :label="$u1t('Выберите G-code с принтера')" @change="loadFile" />
        <p v-if="tools.length">{{ $u1t("Сверьте головки с теми, которые выберете при запуске печати.") }}</p>
        <v-select
          v-for="tool in tools" :key="tool.index" v-model="mapping[tool.index]"
          :label="tool.label" :items="headItems" dense
        />
        <v-alert v-if="tools.some(tool => mapping[tool.index] === null)" type="warning">
          {{ $u1t("Выберите головку для каждого филамента, чтобы проверить полный расход.") }}
        </v-alert>
        <v-alert v-for="row in needs" :key="row.head" :type="row.available === null || row.deficit > 0 ? 'warning' : 'success'">
          {{ $u1t("Головка") }} {{ row.head + 1 }} {{ $u1t("· нужно") }} {{ format(row.required) }} {{ $u1t("г.") }}
          <template v-if="row.available === null"> {{ $u1t("Привяжите катушку для проверки остатка.") }}</template>
          <template v-else> {{ $u1t("Осталось") }} {{ format(row.available) }} {{ $u1t("г.") }}
            <template v-if="row.deficit > 0"> {{ $u1t("Не хватает") }} {{ format(row.deficit) }} {{ $u1t("г.") }}
              <template v-if="estimated"> {{ $u1t("Замена примерно") }} {{ eta(estimated * row.available / row.required) }} {{ $u1t("от начала печати по среднему расходу.") }}</template>
            </template>
          </template>
          <div v-if="row.cost !== null">{{ $u1t('Стоимость для клиента') }} {{ formatCost(row.cost) }}</div>
        </v-alert>
        <p v-if="plannedPurchaseCost !== null"><strong>{{ $u1t('Себестоимость пластика') }}: {{ formatCost(plannedPurchaseCost) }}</strong></p>
        <p v-if="plannedCost !== null"><strong>{{ $u1t("Стоимость пластика на весь файл ·") }} {{ formatCost(plannedCost) }}</strong></p>
      </v-card-text>
      
    </v-card>
  </v-dialog>
  <v-dialog content-class="u1-dialog u1-unified-dialog" v-model="historyOpen" max-width="760" scrollable>
    <v-card>
      <u1-dialog-close @close="historyOpen = false" />
      <v-card-title>{{ $u1t("Списание филамента") }}</v-card-title>
      <v-card-text>
        <p v-if="!recentHeartbeat">{{ $u1t("Служба учёта пока не отвечает. Проверьте подключение к принтеру.") }}</p>
        <u1-log-tools kind="usage" @archive="showArchive = $event" @changed="loadUsage" />
        <p v-if="!visibleRecords.length">{{ $u1t("Записи появятся после печати с катушками, привязанными к головкам.") }}</p>
        <v-alert v-if="decisionError" type="error">{{ decisionError }}</v-alert>
        <v-card v-for="record in reviewRecords" :key="record.id" outlined class="pa-3 mb-3">
          <strong>{{ record.filename }}</strong>
          <p>{{ jobStatus(record.status) }} · {{ record.state === 'review' ? $u1t("Нужно подтвердить расход") : method(record.method) }}</p>
          <template v-if="record.state === 'review'">
            <p>{{ $u1t("Проверьте оценку для каждой катушки. Введите 0 г, если по этой катушке ничего списывать не нужно.") }}</p>
            <v-text-field
              v-for="(row, index) in record.rows" :key="row.head"
              :label="$u1t('Головка ') + (row.head + 1) + ' · ' + row.name + $u1t(' (г)')"
              :value="draftValue(record, index)" :disabled="!!submitted[record.id]"
              type="number" min="0" step="any" @input="setDraft(record, index, $event)"
            />
            <v-btn color="primary" :disabled="!!submitted[record.id]" :loading="saving === record.id" @click="confirm(record)">
              {{ submitted[record.id] ? $u1t("Ожидаю подтверждения принтера") : $u1t("Списать указанный расход") }}
            </v-btn>
          </template>
          <ul v-else><li v-for="row in record.rows" :key="row.head">{{ row.name }} · {{ format(row.grams) }} {{ $u1t("г") }}</li></ul>
        </v-card>
      </v-card-text>
      
    </v-card>
  </v-dialog>
  <v-dialog content-class="u1-dialog u1-unified-dialog" v-model="statsOpen" max-width="950" scrollable>
    <v-card class="stats-card">
      <u1-dialog-close @close="statsOpen = false" />
      <v-card-title>{{ $u1t("Статистика расхода") }}</v-card-title>
      <v-card-text>
        <div class="stats-summary">
          <div><small>{{ $u1t("Списано") }} {{ rangeActive ? $u1t("за период") : $u1t("за всё время") }}</small><strong>{{ format(totalGrams) }} {{ $u1t("г") }}</strong></div>
          <div><small>{{ $u1t("Заданий в журнале") }}</small><strong>{{ selectedJobs.length }}</strong></div>
          <div><small>{{ $u1t('Стоимость для клиента') }}</small><strong>{{ pricedGrams ? formatCost(totalCost) : '—' }}</strong></div>
        </div>
        <p>{{ $u1t('Себестоимость пластика') }}: {{ purchasedGrams ? formatCost(purchaseCost) : '—' }} <small v-if="purchasedGrams < datedGrams">{{ $u1t('(частично)') }}</small></p>
        <p v-if="!rangeActive && totalGrams - datedGrams > 0.01">{{ format(totalGrams - datedGrams) }} {{ $u1t("г учтены в общем итоге, но в журнале нет дат этих списаний.") }}</p>
        <div class="stats-filters">
          <v-text-field v-model="dateFrom" type="date" :lang="$i18n.locale" :label="$u1t('С даты')" dense outlined clearable />
          <v-text-field v-model="dateTo" type="date" :lang="$i18n.locale" :label="$u1t('По дату включительно')" dense outlined clearable />
          <v-btn outlined @click="dateFrom = ''; dateTo = ''">{{ $u1t("Всё время") }}</v-btn>
        </div>
        <v-alert v-if="dateFrom && dateTo && dateFrom > dateTo" type="warning">{{ $u1t("Дата начала должна быть не позже даты окончания.") }}</v-alert>
        <v-select v-model="dimension" :items="dimensions" :label="$u1t('Показать расход')" dense outlined />
        <p v-if="dimension === 'color'">{{ $u1t("Катушки одного цвета из библиотеки объединены. Старые записи без привязки к цвету показаны отдельно.") }}</p>
        <p v-if="dimension !== 'time'">{{ $u1t("Задания — число печатей с подтверждённым списанием, включая прерванные. Стоимость рассчитана по цене на момент печати.") }}</p>
        <v-select v-if="dimension === 'time'" v-model="period" :items="periods" :label="$u1t('Группировать расход')" dense outlined class="period-select" />
        <v-data-table
          :headers="statsHeaders" :items="statistics" item-key="key" :items-per-page="15"
          :sort-by="dimension === 'time' ? 'time' : 'grams'" :sort-desc="true" :no-data-text="$u1t('Пока нет подтверждённых списаний.')"
        >
          <template #item.time="{ item }">{{ periodLabel(item.time) }}</template>
          <template #item.name="{ item }">
            {{ item.name }}
            <small v-if="dimension === 'spool'" class="d-block">ID: {{ item.key }}</small>
          </template>
          <template #item.grams="{ item }">{{ format(item.grams) }} {{ $u1t("г") }}<small v-if="item.undatedGrams" class="d-block">{{ $u1t("Без даты:") }} {{ format(item.undatedGrams) }} {{ $u1t("г") }}</small></template>
          <template #item.purchaseCost="{ item }">{{ item.purchaseGrams ? formatCost(item.purchaseCost) : '—' }}<small v-if="item.purchaseGrams && item.grams > item.purchaseGrams + 0.001">{{ $u1t('(частично)') }}</small></template>
          <template #item.cost="{ item }">
            {{ item.pricedGrams ? formatCost(item.cost) : '—' }}
            <small v-if="item.pricedGrams > 0 && item.grams - item.pricedGrams > 0.001"> {{ $u1t("(частично)") }}</small>
          </template>
        </v-data-table>
      </v-card-text>
      
    </v-card>
  </v-dialog>
</div>
</template>

<script lang="ts">
import { u1t } from '@/plugins/i18n'


import Vue from 'vue'
import { Component, Prop } from 'vue-property-decorator'
import axios from 'axios'
import { httpClientActions as http } from '@/api/httpClientActions'
import { readU1Item, u1DataRequest } from '@/utils/u1DataClient'
import { visibleLogRows } from '@/utils/u1LogLists'
import { formatCost, usageRows, cumulativeRows, filterUsage, type UsageDimension, type UsagePeriod, type UsageRecord } from '@/utils/u1SpoolStats'

interface SpoolBalance { name: string; grams: number; material: string; hex: string; pricePerGram?: number; purchasePerGram?: number }
interface Active { paused: boolean; changed: boolean; rows: { head: number; name: string; shortage: number; seconds: number | null }[] }
interface Usage { archivedRecords?: string[]; totals: { [id: string]: number }; records: UsageRecord[]; checkedAt?: number; active?: Active }
interface Tool { index: number; grams: number; label: string }
interface Metadata {
  filament_weight?: number[];
  filament_weights?: number[];
  filament_weight_total?: number;
  filament_type?: string;
  filament_colour?: string;
  estimated_time?: number;
}

@Component
export default class U1SpoolUsage extends Vue {
  @Prop({ default: () => [] }) readonly spools!: (SpoolBalance | undefined)[]
  records: UsageRecord[] = []
  archivedIds: string[] = []
  showArchive = false
  get visibleRecords () { return visibleLogRows(this.records, this.archivedIds, this.showArchive) }
  totals: Record<string, number> = {}
  statsOpen = false
  openStats () { this.statsOpen = true }
  period: UsagePeriod = 'day'
  dimension: UsageDimension = 'spool'
  get dimensions () { return [{ text: u1t("По катушкам"), value: 'spool' }, { text: u1t("По цветам библиотеки"), value: 'color' }, { text: u1t("По времени и заданиям"), value: 'time' }] }
  dateFrom = ''
  dateTo = ''
  get periods () { return [
    { text: u1t("По заданиям"), value: 'job' }, { text: u1t("По дням"), value: 'day' },
    { text: u1t("По месяцам"), value: 'month' }, { text: u1t("По годам"), value: 'year' }
  ] }
  formatCost = formatCost
  active: Active | null = null
  error = ''
  decisionError = ''
  recentHeartbeat = false
  timer: number | null = null
  loadingUsage = false
  historyOpen = false
  checkOpen = false
  checkError = ''
  filename = ''
  files: string[] = []
  loadingFiles = false
  tools: Tool[] = []
  mapping: (number | null)[] = []
  estimated = 0
  drafts: { [id: string]: string[] } = {}
  submitted: { [id: string]: boolean } = {}
  saving = ''

  get pending () { return this.records.filter(record => record.state === 'review').length }
  get reviewRecords () { return this.visibleRecords.filter(record => record.state === 'review').concat(this.visibleRecords.filter(record => record.state === 'applied').slice(0, 15)) }
  get jobRows () { return usageRows(this.records, 'job') }
  get rangeActive () { return !!(this.dateFrom || this.dateTo) }
  get selectedRecords () { return filterUsage(this.records, this.dateFrom || '', this.dateTo || '') }
  get selectedJobs () { return usageRows(this.selectedRecords, 'job') }
  get statistics () {
    const costs = this.selectedRecords.map(r => ({...r,rows:r.rows.map(row=>({...row,pricePerGram:row.purchasePerGram}))}))
    const purchase = this.dimension === 'time' ? usageRows(costs,this.period) : cumulativeRows(costs,this.dimension,this.rangeActive ? {} : this.totals)
    const rows = this.dimension === 'time' ? usageRows(this.selectedRecords, this.period) : cumulativeRows(this.selectedRecords, this.dimension, this.rangeActive ? {} : this.totals)
    return rows.map(row=>({...row,purchaseCost:purchase.find(p=>p.key===row.key)?.cost ?? 0,purchaseGrams:purchase.find(p=>p.key===row.key)?.pricedGrams ?? 0}))
  }
  get totalGrams () {
    return cumulativeRows(this.selectedRecords, 'spool', this.rangeActive ? {} : this.totals).reduce((sum, row) => sum + row.grams, 0)
  }
  get datedGrams () { return this.jobRows.reduce((sum, row) => sum + row.grams, 0) }
  get purchaseCost () { return this.selectedRecords.filter(r => r.state === 'applied').flatMap(r => r.rows).reduce((sum,r) => sum + (r.purchasePerGram == null ? 0 : r.grams * r.purchasePerGram),0) }
  get purchasedGrams () { return this.selectedRecords.filter(r => r.state === 'applied').flatMap(r => r.rows).reduce((sum,r) => sum + (r.purchasePerGram == null ? 0 : r.grams),0) }
  get totalCost () { return this.selectedJobs.reduce((sum, row) => sum + row.cost, 0) }
  get pricedGrams () { return this.selectedJobs.reduce((sum, row) => sum + row.pricedGrams, 0) }
  get statsHeaders () {
    if (this.dimension !== 'time') return [
      { text: this.dimension === 'spool' ? u1t("Катушка") : u1t("Цвет"), value: 'name' },
      { text: u1t("Заданий в журнале"), value: 'jobs' }, { text: u1t("Расход"), value: 'grams' }, { text: u1t('Стоимость для клиента'), value: 'cost' }, {text:u1t('Себестоимость пластика'),value:'purchaseCost'}
    ]
    return [
      { text: u1t("Дата"), value: 'time' },
      this.period === 'job' ? { text: u1t("Файл"), value: 'name' } : { text: u1t("Заданий"), value: 'jobs' },
      { text: u1t("Расход"), value: 'grams' },
      { text: u1t('Стоимость для клиента'), value: 'cost' }, {text:u1t('Себестоимость пластика'),value:'purchaseCost'}
    ]
  }

  periodLabel (time: number) {
    if (this.period === 'year') return String(new Date(time).getFullYear())
    const options: Intl.DateTimeFormatOptions = this.period === 'month' ? { month: 'long', year: 'numeric' } : { dateStyle: 'medium' }
    return new Date(time).toLocaleDateString(this.$i18n.locale, options)
  }
  get shortages () { return this.active?.changed ? [] : this.active?.rows.filter(row => row.shortage > 0) || [] }
  get headItems () {
    return Array.from({ length: 4 }, (_, value) => ({
      value, text: u1t(u1t("Головка {p0} · {p1}"), { p0: value + 1, p1: this.spools[value]?.name || u1t("без привязки") })
    }))
  }

  get needs () {
    const required = [0, 0, 0, 0]
    for (const tool of this.tools) {
      const head = this.mapping[tool.index]
      if (head !== null) required[head] += tool.grams
    }
    return required.flatMap((grams, head) => {
      const available = this.spools[head]?.grams ?? null
      const purchase = this.spools[head]?.purchasePerGram
      const price = this.spools[head]?.pricePerGram
      return grams ? [{ head, required: grams, available, purchaseCost: purchase == null ? null : grams * purchase, cost: price == null ? null : grams * price, deficit: available === null ? 0 : Math.max(0, grams - available) }] : []
    })
  }

  get plannedPurchaseCost () {
    if (!this.needs.length || this.tools.some(tool => this.mapping[tool.index] === null) || this.needs.some(row => row.purchaseCost === null)) return null
    return this.needs.reduce((sum,row)=>sum+(row.purchaseCost ?? 0),0)
  }
  get plannedCost () {
    if (!this.needs.length || this.tools.some(tool => this.mapping[tool.index] === null) || this.needs.some(row => row.cost === null)) return null
    return this.needs.reduce((sum, row) => sum + (row.cost ?? 0), 0)
  }

  format (value: number) { return value.toLocaleString(this.$i18n.locale, { maximumFractionDigits: 2 }) }
  eta (seconds: number) {
    if (seconds < 60) return u1t("менее чем через минуту")
    const minutes = Math.round(seconds / 60)
    const hours = Math.floor(minutes / 60)
    return u1t(u1t("через {p0}{p1} мин"), { p0: hours ? hours + u1t(" ч ") : '', p1: minutes % 60 })
  }

  jobStatus (status: string) {
    if (status === 'completed') return u1t("Печать завершена")
    if (status === 'cancelled') return u1t("Печать отменена")
    return u1t("Печать прервана")
  }

  method (method: string) {
    if (method === 'measured') return u1t("Расход по счётчику U1")
    if (method === 'manual') return u1t("Расход подтверждён вручную")
    return u1t("Списана оценка по G-code")
  }

  mounted () {
    this.loadUsage()
    this.timer = window.setInterval(() => this.loadUsage(), 10000)
  }

  beforeDestroy () { if (this.timer !== null) window.clearInterval(this.timer) }

  async loadUsage () {
    if (this.loadingUsage) return
    this.loadingUsage = true
    try {
      const response = await readU1Item<Usage>('u1_spool_usage_v1')
      const value = response.data.result.value
      this.records = value.records
      this.archivedIds = value.archivedRecords || []
      this.totals = value.totals
      this.recentHeartbeat = Date.now() / 1000 - (value.checkedAt || 0) < 90
      this.active = this.recentHeartbeat ? value.active || null : null
      this.$emit('totals', value.totals)
      this.error = ''
    } catch (error) {
      this.recentHeartbeat = false
      this.active = null
      if (!(axios.isAxiosError(error) && error.response?.status === 404)) this.error = u1t("Не удалось обновить данные расхода.")
    } finally { this.loadingUsage = false }
  }

  async openCheck () {
    this.checkOpen = true
    this.loadingFiles = true
    this.checkError = ''
    try {
      const response = await http.get<{result: {path: string}[]}>('/server/files/list?root=gcodes')
      this.files = response.data.result.map(file => file.path).filter(path => /\.(gcode|gco|g)$/i.test(path))
    } catch { this.checkError = u1t("Не удалось загрузить файлы с принтера.") }
    finally { this.loadingFiles = false }
  }

  async loadFile (filename: string) {
    this.tools = []
    this.mapping = []
    this.estimated = 0
    this.checkError = ''
    if (!filename) return
    try {
      const response = await http.get<{result: Metadata}>('/server/files/metadata?filename=' + encodeURIComponent(filename))
      if (filename !== this.filename) return
      const metadata = response.data.result
      const weights = metadata.filament_weight || metadata.filament_weights
      if (!Array.isArray(weights) || !weights.some(grams => grams > 0)) {
        const total = metadata.filament_weight_total
        this.checkError = total ? u1t(u1t("Файл содержит общий расход {p0} г. Для проверки по головкам нужны отдельные значения из слайсера."), { p0: this.format(total) }) : u1t("В файле нет расхода в граммах.")
        return
      }
      const colors = metadata.filament_colour?.split(';') || []
      const types = metadata.filament_type?.split(';') || []
      this.mapping = weights.map((_, index) => {
        const matching = this.spools.findIndex(spool => spool && spool.material === types[index] && spool.hex.toUpperCase() === colors[index]?.toUpperCase())
        return matching >= 0 ? matching : index < 4 ? index : null
      })
      this.tools = weights.flatMap((grams, index) => Number.isFinite(grams) && grams > 0
        ? [{ index, grams, label: u1t(u1t("Филамент {p0} · {p1} {p2} · {p3} г"), { p0: index + 1, p1: types[index] || '', p2: colors[index] || '', p3: this.format(grams) }) }]
        : [])
      this.estimated = metadata.estimated_time || 0
    } catch { if (filename === this.filename) this.checkError = u1t("Не удалось прочитать данные файла.") }
  }

  draftValue (record: UsageRecord, index: number) {
    return this.drafts[record.id]?.[index] ?? String(record.rows[index].grams)
  }

  setDraft (record: UsageRecord, index: number, value: string) {
    const draft = this.drafts[record.id]?.slice() || record.rows.map(row => String(row.grams))
    draft[index] = value
    this.$set(this.drafts, record.id, draft)
  }

  async confirm (record: UsageRecord) {
    if (this.saving || this.submitted[record.id]) return
    this.decisionError = ''
    const input = record.rows.map((_, index) => this.draftValue(record, index))
    const grams = input.map(Number)
    if (input.some(value => !value.trim()) || grams.some(value => !Number.isFinite(value) || value < 0 || value > 100000)) {
      this.decisionError = u1t("Введите корректный расход в граммах для каждой катушки.")
      return
    }
    this.saving = record.id
    try {
      await u1DataRequest('review', { id: record.id, value: { time: record.time, grams } })
      this.$set(this.submitted, record.id, true)
    } catch { this.decisionError = u1t("Не удалось сохранить решение. Повторите попытку.") }
    finally { this.saving = '' }
  }
}
</script>

<style scoped>
.stats-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 12px 0 22px }
.stats-summary > div { display: grid; gap: 4px; padding: 14px; border-radius: 12px; background: rgba(127,127,127,.13) }
.stats-summary strong { font-size: 1.45rem; font-variant-numeric: tabular-nums }
.stats-filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-start }
.stats-filters .v-input { flex: 1 1 170px; min-width: 0 }
.period-select { max-width: 260px }
</style>
