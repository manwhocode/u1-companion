<template>
<div>
  <v-btn v-if="!inline && !hideLauncher" small outlined @click="openFor('spool')">{{ $u1t("Калибровки филамента") }}</v-btn>
  <u1-settings-content :inline="inline" v-model="opened" content-class="u1-dialog u1-unified-dialog" max-width="620" scrollable>
    <v-card :flat="inline">
      <u1-dialog-close v-if="!inline" @close="opened = false" />
      <v-card-title class="calibration-title">{{ $u1t("Калибровка филамента") }}<v-btn icon small :aria-label="$u1t('Информация о калибровках')" :aria-expanded="showInfo" @click="showInfo = !showInfo">ⓘ</v-btn><v-spacer /></v-card-title>
      <v-card-text>
        <v-alert v-if="showInfo" dense outlined type="info">
          <p>{{ $u1t("Здесь хранится справочная информация о калибровке филамента: её можно посмотреть и использовать для настройки принтера.") }}</p>
          <p>{{ $u1t("Для назначенной головке катушки сохранённый K применяется модулем «Профили печати». Если включена штатная калибровка перед печатью, K управляет сам U1. Поле «Источник результата» указывает, где получено значение, и не запускает калибровку.") }}</p>
          <p class="mb-0">{{ $u1t("Для выполнения штатной калибровки U1 используйте отдельную кнопку «Запустить калибровку».") }}</p>
        </v-alert>
        <v-alert v-if="message" dense :type="failed ? 'error' : 'info'">{{ message }}</v-alert>
        <v-progress-linear v-if="loading" indeterminate />
        <template v-if="ready">
          <v-radio-group v-model="kind" row :disabled="busy" @change="changeKind">
            <v-radio value="spool" :label="$u1t('Моя катушка')" /><v-radio value="color" :label="$u1t('Общий филамент')" />
          </v-radio-group>
          <v-autocomplete v-model="selectedId" :items="items" :label="kind === 'spool' ? $u1t('Найти катушку') : $u1t('Найти филамент в «Моих цветах»')" outlined dense :disabled="busy" @change="fillValues" />
          <v-switch v-model="individual" :label="$u1t('Сохранять калибровку отдельно для каждой катушки')" :disabled="busy" @change="fillValues" />
          <p>{{ $u1t("Переключение не удаляет общие и индивидуальные значения. Режим сохраняется кнопкой ниже.") }}</p>
          <v-alert v-if="selectedId && !record" dense type="warning">{{ $u1t("Общая карточка отсутствует в «Моих цветах». Восстановите её или выберите другую основу катушки.") }}</v-alert>
          <template v-if="record">
            <p><strong>{{ record.name }}</strong> · {{ record.material }} · {{ record.hex }}</p>
            <p>{{ $u1t("Сохраняется:") }} <strong>{{ sourceLabel }}</strong>.</p>
            <p>{{ individualSummary }}</p>
            <p>{{ commonSummary }}</p>
            <v-text-field v-model="pressureAdvance" label="Pressure Advance (K)" :placeholder="$u1t('Например, 0.024')" inputmode="decimal" outlined dense :disabled="busy" :hint="$u1t('От 0 до 1. Пустое поле — коэффициент не задан.')" persistent-hint />
            <u1-date-field v-model="date" :label="$u1t('Дата калибровки')" outlined dense :disabled="busy" />
            <v-combobox v-model="method" :items="methods" :label="$u1t('Источник результата калибровки')" maxlength="100" outlined dense :disabled="busy" />
            <v-textarea v-model="notes" :label="$u1t('Сведения о тесте (необязательно)')" maxlength="1000" rows="2" outlined dense :disabled="busy" />
            <v-btn v-if="kind === 'spool' && assignedHead !== -1" small outlined :disabled="busy" @click="readCurrentK">{{ $u1t("Прочитать текущий K головки") }} {{ assignedHead + 1 }}</v-btn>
            <v-btn v-if="record.calibration && !resetConfirm" class="mt-3" small outlined color="warning" :disabled="busy" @click="resetConfirm = true">{{ $u1t("Сбросить калибровку") }}</v-btn>
            <v-alert v-if="resetConfirm" class="mt-3" dense type="warning" outlined>
              {{ $u1t("Удалить сохранённую калибровку:") }} {{ sourceLabel }}{{ $u1t("? Текущий K головки останется прежним. Перед изменением создаётся резервная копия.") }}
              <div class="calibration-reset-actions">
                <v-btn small color="warning" :loading="saving" :disabled="busy" @click="reset">{{ $u1t("Сбросить") }}</v-btn>
                <v-btn small outlined :disabled="busy" @click="resetConfirm = false">{{ $u1t("Отмена") }}</v-btn>
              </div>
            </v-alert>
            <p class="mt-3">{{ $u1t("Штатная FLOW_CALIBRATE на U1 определяет K. Текущее значение K само по себе не подтверждает выполнение калибровки для этой катушки.") }}</p>
            <p>{{ $u1t("Эта форма сохраняет результаты в базе и не запускает калибровку. Автоматическое применение к следующей печати можно проверить в окне «Профили печати».") }}</p>
          </template>
        </template>
      </v-card-text>
      <v-card-actions class="calibration-actions">
        <v-spacer />
        <v-btn color="primary" :loading="saving" :disabled="busy || !record" @click="save">{{ $u1t("Сохранить") }}</v-btn>
        
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
import { readU1Item, u1DataRequest } from '@/utils/u1DataClient'
import { httpClientActions as http } from '@/api/httpClientActions'
import { calibrationNumber, calibrationSummary, type FilamentCalibration } from '@/utils/u1Calibration'
import type { Entry } from './U1FilamentLibrary.vue'
import type { Spool } from './U1SpoolInventory.vue'

interface Library { revision: string; entries: Entry[] }
interface Inventory { revision: string; spools: Spool[]; heads: (string | null)[]; individualCalibration?: boolean }

@Component({components:{U1SettingsContent}})
export default class U1Calibration extends Vue {
  @Prop({default:false,type:Boolean}) readonly inline!: boolean
  @Prop({default:false,type:Boolean}) readonly hideLauncher!: boolean
  mounted () { if (this.inline) this.openFor('spool') }
  opened = false
  showInfo = false
  loading = false
  saving = false
  reading = false
  resetConfirm = false
  ready = false
  kind: 'spool' | 'color' = 'spool'
  selectedId = ''
  individual = false
  library: Library = { revision: '', entries: [] }
  inventory: Inventory = { revision: '', spools: [], heads: [] }
  pressureAdvance = ''
  date = ''
  method = ''
  notes = ''
  message = ''
  failed = false
  get methods () { return [u1t("Вручную"), u1t("Штатная калибровка U1 (K)"), 'OrcaSlicer', u1t("Тестовая модель")] }
  get busy () { return this.loading || this.saving || this.reading }
  get spool () { return this.kind === 'spool' ? this.inventory.spools.find(item => item.id === this.selectedId) : undefined }
  get color () { return this.library.entries.find(item => item.id === (this.kind === 'spool' ? this.spool?.colorId : this.selectedId)) }
  get record () { return this.kind === 'spool' && this.individual ? this.spool : this.color }
  get sourceLabel () { return this.kind === 'spool' && this.individual ? u1t("только эта катушка") : u1t("общий филамент — для всех связанных катушек") }
  get commonSummary () { return u1t("Общая калибровка: ") + calibrationSummary(this.color?.calibration) }
  get individualSummary () { return this.spool ? u1t("Эта катушка: ") + calibrationSummary(this.spool.calibration) : '' }
  get assignedHead () { return this.spool ? this.inventory.heads.indexOf(this.spool.id) : -1 }
  get items () {
    const entries = this.kind === 'spool' ? this.inventory.spools : this.library.entries
    return entries.map(item => ({ value: item.id, text: `${item.name} · ${item.manufacturer || ''} ${item.material} · ${item.hex}` }))
  }
  changeKind () { this.selectedId = ''; this.fillValues() }
  fillValues () {
    this.resetConfirm = false
    const value = this.record?.calibration
    this.pressureAdvance = value?.pressureAdvance === undefined ? '' : String(value.pressureAdvance)
    // Local calendar date, independent of UTC offset.
    const today = new Date()
    this.date = value?.date || `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
    this.method = value?.method || u1t("Вручную")
    this.notes = value?.notes || ''
  }
  async openFor (kind: 'spool' | 'color', id = '') {
    if (this.busy) return
    this.opened = true
    this.ready = false
    this.loading = true
    this.message = ''
    this.failed = false
    this.kind = kind
    this.selectedId = id
    try {
      const [library, inventory] = await Promise.all([
        readU1Item<Library>('u1_filament_library_v1'), readU1Item<Inventory>('u1_spool_inventory_v1')
      ])
      this.library = library.data.result.value
      this.inventory = inventory.data.result.value
      this.individual = this.inventory.individualCalibration === true
      this.ready = true
      this.fillValues()
    } catch (error) { this.failed = true; this.message = String(error) } finally { this.loading = false }
  }
  async readCurrentK () {
    const slot = this.assignedHead
    if (slot < 0 || this.busy) return
    this.reading = true
    this.failed = false
    try {
      const object = slot === 0 ? 'extruder' : 'extruder' + slot
      const result = await http.get<{result: {status: Record<string, {pressure_advance?: number}>}}>('/printer/objects/query?' + object)
      const value = result.data.result.status[object]?.pressure_advance
      if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(u1t("Принтер не вернул K."))
      this.pressureAdvance = String(value)
      this.message = u1t("Прочитан текущий K головки {p0}: {p1}. Проверьте, что он относится к выбранной катушке, затем сохраните.", { p0: slot + 1, p1: value })
    } catch (error) { this.failed = true; this.message = String(error) } finally { this.reading = false }
  }
  async reset () {
    if (!this.record?.calibration || this.busy || !this.resetConfirm) return
    this.saving = true
    this.failed = false
    try {
      await u1DataRequest('calibration', { kind: this.kind, id: this.selectedId, individual: this.individual, value: null,
        libraryRevision: this.library.revision, inventoryRevision: this.inventory.revision })
      this.$emit('saved')
      await this.openAfterReset()
    } catch (error) { this.failed = true; this.message = String(error) } finally { this.saving = false }
  }
  async openAfterReset () {
    const [library, inventory] = await Promise.all([
      readU1Item<Library>('u1_filament_library_v1'), readU1Item<Inventory>('u1_spool_inventory_v1')
    ])
    this.library = library.data.result.value
    this.inventory = inventory.data.result.value
    this.fillValues()
    this.message = u1t("Сохранённая калибровка сброшена. Текущий K головки не изменялся.")
  }
  async save () {
    if (!this.record || this.busy) return
    this.saving = true
    this.failed = false
    try {
      const pressureAdvance = calibrationNumber(this.pressureAdvance, 1)
      let value: FilamentCalibration | null = null
      if (pressureAdvance !== undefined) {
        if (!this.date || !/^\d{4}-\d{2}-\d{2}$/.test(this.date)) throw new Error(u1t("Укажите дату калибровки."))
        if (typeof this.method !== 'string' || !this.method.trim()) throw new Error(u1t("Укажите метод калибровки."))
        value = { ...this.record.calibration, date: this.date, method: this.method.trim(), ...(this.notes.trim() ? { notes: this.notes.trim() } : {}),
          pressureAdvance }
      } else if (this.record.calibration) {
        throw new Error(u1t("Укажите K для сохранённой калибровки."))
      }
      await u1DataRequest('calibration', { kind: this.kind, id: this.selectedId, individual: this.individual, value,
        libraryRevision: this.library.revision, inventoryRevision: this.inventory.revision })
      this.$emit('saved')
      this.opened = false
    } catch (error) { this.failed = true; this.message = String(error) } finally { this.saving = false }
  }
}
</script>

<style scoped>
.calibration-reset-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px }
.calibration-title { gap: 6px; word-break: normal }
.calibration-title .v-btn { flex-shrink: 0 }
.calibration-actions { gap: 6px; padding-left: 64px !important }
.calibration-actions .v-btn { margin: 0 !important }
</style>
