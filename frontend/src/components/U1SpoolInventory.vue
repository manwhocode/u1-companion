<template>
<div>
  <v-btn @click="open('spools')">{{ $u1t("Мои катушки ·") }} {{ inventory.spools.length }}</v-btn>
  <v-btn @click="open('cores')">{{ $u1t("Пустые катушки ·") }} {{ inventory.cores.length }}</v-btn>
  <v-dialog content-class="u1-dialog u1-unified-dialog" v-model="opened" max-width="760" scrollable>
    <v-card>
      <u1-dialog-close @close="opened = false" />
      <v-card-title>{{ title }}</v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error">{{ error }}</v-alert>
        <v-btn class="ma-1" :disabled="busy" @click="load">{{ $u1t("Обновить") }}</v-btn>
        <template v-if="section === 'spools'">
          <v-btn class="ma-1" :disabled="!ready || busy || !colors.length" @click="newSpool">{{ $u1t("Добавить мою катушку") }}</v-btn>
          <p v-if="!colors.length">{{ $u1t("Добавьте основу в «Мои цвета», чтобы создать свою катушку.") }}</p>
          <p v-if="ready && !inventory.spools.length">{{ $u1t("Здесь будут ваши физические катушки и остаток пластика на каждой.") }}</p>
          <v-text-field v-model="spoolSearch" :label="$u1t('Найти катушку')" :placeholder="$u1t('Введите название катушки')" outlined dense clearable hide-details class="my-3" />
          <template v-if="spoolSearch && spoolSearch.trim()">
            <p v-if="!matchingSpools.length">{{ $u1t("Катушки не найдены. Попробуйте другое название.") }}</p>
            <v-card v-for="spool in matchingSpools" :key="spool.id" outlined class="pa-3 my-2">
              <strong><span class="spool-swatch" :style="{ backgroundColor: spool.hex }" />{{ spool.name }}</strong>
              <div>{{ spool.manufacturer }} {{ spool.material }} · {{ spool.hex }} · {{ remaining(spool) }} {{ $u1t("г филамента") }}</div>
              <div>{{ spool.coreName }} {{ $u1t("· тара") }} {{ spool.tare }} {{ $u1t("г · общий вес") }} {{ weight(remaining(spool) + spool.tare) }} {{ $u1t("г") }}</div>
              <div>{{ spoolCalibration(spool) }}</div>
                        <div>{{ spoolTemperatures(spool) }}</div>
              <div v-if="spool.pricePerGram != null">{{ formatUnitPrice(spool.pricePerGram) }} {{ $u1t("за грамм") }}</div>
              <v-btn v-if="target !== null" small class="ma-1" color="primary" :disabled="busy" @click="choose(spool)">{{ $u1t("В головку") }} {{ target + 1 }}</v-btn>
              <v-btn small class="ma-1" :disabled="busy" @click="editSpool(spool)">{{ $u1t("Изменить") }}</v-btn>
              <v-btn small outlined class="ma-1" :disabled="busy" @click="$emit('error-history', {id: spool.id, name: spool.name})">{{ $u1t("История ошибок") }}</v-btn>
                        <v-btn small class="ma-1" :disabled="busy" @click="$emit('calibration', spool.id)">{{ $u1t("Калибровка") }}</v-btn>
              <v-btn small class="ma-1" :disabled="busy" @click="writeTag(spool)">{{ $u1t("Записать NFC-метку") }}</v-btn>
              <v-btn icon small class="ma-1" :title="$u1t('QR-этикетка катушки')" :aria-label="$u1t('QR-этикетка катушки')" :disabled="busy" @click="openSpoolQr(spool)"><v-icon small>{{ qrIcon }}</v-icon></v-btn>
              <v-btn small text color="error" class="ma-1" :disabled="busy" @click="removeSpool(spool, false)">{{ $u1t("Удалить") }}</v-btn>
            </v-card>
          </template>
          <v-expansion-panels v-else multiple>
            <v-expansion-panel v-for="group in spoolGroups" :key="group.name">
              <v-expansion-panel-header>📁 {{ group.name }} ({{ group.count }})</v-expansion-panel-header>
              <v-expansion-panel-content>
                <v-expansion-panels multiple>
                  <v-expansion-panel v-for="material in group.materials" :key="material.name">
                    <v-expansion-panel-header>{{ material.name }} ({{ material.entries.length }})</v-expansion-panel-header>
                    <v-expansion-panel-content>
                      <v-card v-for="spool in material.entries" :key="spool.id" outlined class="pa-3 my-2">
                        <strong><span class="spool-swatch" :style="{ backgroundColor: spool.hex }" />{{ spool.name }}</strong>
                        <div>{{ spool.manufacturer }} {{ spool.material }} · {{ spool.hex }} · {{ remaining(spool) }} {{ $u1t("г филамента") }}</div>
                        <div>{{ spool.coreName }} {{ $u1t("· тара") }} {{ spool.tare }} {{ $u1t("г · общий вес") }} {{ weight(remaining(spool) + spool.tare) }} {{ $u1t("г") }}</div>
                        <div>{{ spoolCalibration(spool) }}</div>
                        <div>{{ spoolTemperatures(spool) }}</div>
                        <div v-if="spool.pricePerGram != null">{{ formatUnitPrice(spool.pricePerGram) }} {{ $u1t("за грамм") }}</div>
                        <v-btn v-if="target !== null" small class="ma-1" color="primary" :disabled="busy" @click="choose(spool)">{{ $u1t("В головку") }} {{ target + 1 }}</v-btn>
                        <v-btn small class="ma-1" :disabled="busy" @click="editSpool(spool)">{{ $u1t("Изменить") }}</v-btn>
                        <v-btn small outlined class="ma-1" :disabled="busy" @click="$emit('error-history', {id: spool.id, name: spool.name})">{{ $u1t("История ошибок") }}</v-btn>
                        <v-btn small class="ma-1" :disabled="busy" @click="$emit('calibration', spool.id)">{{ $u1t("Калибровка") }}</v-btn>
                        <v-btn small class="ma-1" :disabled="busy" @click="writeTag(spool)">{{ $u1t("Записать NFC-метку") }}</v-btn>
                        <v-btn icon small class="ma-1" :title="$u1t('QR-этикетка катушки')" :aria-label="$u1t('QR-этикетка катушки')" :disabled="busy" @click="openSpoolQr(spool)">
                          <v-icon small>{{ qrIcon }}</v-icon>
                        </v-btn>
                        <v-btn small text color="error" class="ma-1" :disabled="busy" @click="removeSpool(spool, false)">{{ $u1t("Удалить") }}</v-btn>
                      </v-card>
                    </v-expansion-panel-content>
                  </v-expansion-panel>
                </v-expansion-panels>
              </v-expansion-panel-content>
            </v-expansion-panel>
          </v-expansion-panels>
          <v-expansion-panels v-if="inventory.trash.length && target === null" class="mt-3">
            <v-expansion-panel>
              <v-expansion-panel-header>{{ $u1t("Корзина (") }}{{ inventory.trash.length }})</v-expansion-panel-header>
              <v-expansion-panel-content>
                <div v-for="spool in inventory.trash" :key="spool.id" class="my-2">
                  {{ spool.name }} · {{ spool.material }} · {{ spool.hex }}
                  <v-btn small class="ma-1" :disabled="busy" @click="restoreSpool(spool)">{{ $u1t("Восстановить") }}</v-btn>
                  <v-btn small text color="error" class="ma-1" :disabled="busy" @click="removeSpool(spool, true)">{{ $u1t("Удалить навсегда") }}</v-btn>
                </div>
              </v-expansion-panel-content>
            </v-expansion-panel>
          </v-expansion-panels>
        </template>
        <template v-else>
          <p>{{ $u1t("Укажите вес пустой катушки, чтобы отделять его от веса оставшегося пластика.") }}</p>
          <v-btn class="ma-1" :disabled="!ready || busy" @click="editCore()">{{ $u1t("Добавить пустую катушку") }}</v-btn>
          <v-card v-for="core in inventory.cores" :key="core.id" outlined class="pa-3 my-2">
            <strong>{{ core.name }}</strong> · {{ core.kind }} · {{ core.grams }} {{ $u1t("г") }}
            <v-btn small class="ma-1" :disabled="busy" @click="editCore(core)">{{ $u1t("Изменить") }}</v-btn>
          </v-card>
        </template>
      </v-card-text>
      
    </v-card>
  </v-dialog>
  <v-dialog content-class="u1-dialog u1-unified-dialog" :value="qrSpool !== null" max-width="520" @input="closeSpoolQr">
    <v-card v-if="qrSpool" class="pa-5">
      <u1-dialog-close @close="closeSpoolQr(false)" />
      <h2>QR · {{ qrSpool.name }}</h2>
      <p>{{ $u1t("Этикетка 7 × 7 см со ссылкой на эту катушку.") }}</p>
      <v-alert v-if="qrStatus" dense type="info">{{ $u1t(qrStatus) }}</v-alert>
      <img v-if="qrPng" class="spool-qr-image" :src="qrPng" :alt="$u1t('QR-этикетка катушки')">
      <v-text-field ref="qrAddress" :value="qrAddress" :label="$u1t('Адрес метки без протокола')" readonly />
      <v-btn v-if="qrPng" class="ma-1" :href="qrPng" :download="'U1-spool-' + qrSpool.id + '-70mm.png'">{{ $u1t("Скачать QR PNG") }}</v-btn>
      <v-btn class="ma-1" :disabled="!qrAddress" @click="copyQrAddress">{{ $u1t("Копировать адрес метки") }}</v-btn>
      
    </v-card>
  </v-dialog>
  <v-dialog content-class="u1-dialog u1-unified-dialog" :value="removing !== null" max-width="460" persistent>
    <v-card v-if="removing" class="pa-5">
      <u1-dialog-close @close="removing = null" />
      <h2>{{ $u1t("Удалить «") }}{{ removing.spool.name }}»?</h2>
      <p>{{ removing.permanent ? $u1t("Катушка будет удалена из корзины. Записи о расходе останутся в журнале.") : $u1t("Катушка будет перемещена в корзину.") }}</p>
      <p v-if="inventory.heads.includes(removing.spool.id)">{{ $u1t("Привязка катушки к головке в учёте будет снята.") }}</p>
      <v-alert v-if="removeError" type="error">{{ removeError }}</v-alert>
      <v-btn :disabled="busy" @click="removing = null">{{ $u1t("Отмена") }}</v-btn>
      <v-btn color="error" :loading="busy" @click="confirmRemoval">{{ removing.permanent ? $u1t("Удалить навсегда") : $u1t("В корзину") }}</v-btn>
    </v-card>
  </v-dialog>
  <v-dialog content-class="u1-dialog u1-unified-dialog" :value="spoolDraft !== null" max-width="530" persistent>
    <v-card v-if="spoolDraft" class="pa-5">
      <u1-dialog-close @close="spoolDraft = null" />
      <h2>{{ $u1t("Моя катушка") }}</h2>
      <v-autocomplete :items="colorItems" :value="spoolDraft.colorId" :label="$u1t('Основа из «Мои цвета»')" dense
        :menu-props="{ contentClass: 'u1-spool-color-menu' }" :disabled="busy" @input="setColor">
        <template #item="{ item, attrs, on }">
          <v-list-item v-bind="attrs" v-on="on">
            <span class="spool-swatch" :style="{ backgroundColor: item.hex }" aria-hidden="true" />
            <v-list-item-content><v-list-item-title>{{ item.text }}</v-list-item-title></v-list-item-content>
          </v-list-item>
        </template>
      </v-autocomplete>
      <v-text-field v-model="spoolDraft.name" :label="$u1t('Название моей катушки')" maxlength="100" dense :disabled="busy" />
      <p v-if="spoolDraft.colorId">{{ spoolDraft.manufacturer }} {{ spoolDraft.material }} · {{ spoolDraft.hex }}</p>
      <p v-if="spoolDraft.colorId">{{ spoolTemperatures(spoolDraft) }}</p>
      <v-text-field v-model="spoolDraft.nozzleTemperature" :label="$u1t('Своя температура сопла, °C')" type="number" min="150" max="300" step="any" inputmode="decimal" dense :disabled="busy" :hint="inheritTemperatureHint('nozzleTemperature')" persistent-hint />
      <v-text-field v-model="spoolDraft.bedTemperature" :label="$u1t('Своя температура стола, °C')" type="number" min="20" max="100" step="any" inputmode="decimal" dense :disabled="busy" :hint="inheritTemperatureHint('bedTemperature')" persistent-hint />
      <p>{{ $u1t("По умолчанию — наследование от цвета. Свои значения относятся только к этой катушке и применяются со следующей печати. Очистите поле, чтобы вернуть наследование.") }}</p>
      <v-btn v-if="spoolDraft.nozzleTemperature != null || spoolDraft.bedTemperature != null" small outlined class="mb-3" :disabled="busy" @click="inheritTemperatures">{{ $u1t("Вернуть наследование температур") }}</v-btn>
      <v-autocomplete :items="coreItems" :value="spoolDraft.coreId" :label="$u1t('Пустая катушка')" dense :disabled="busy" @input="setCore" />
      <v-btn small text :disabled="busy" @click="editCore()">{{ $u1t("Создать пустую катушку") }}</v-btn>
      <v-text-field v-model="spoolGrams" type="number" min="0" step="any" :label="$u1t('Остаток филамента без катушки, г')" dense :disabled="busy" />
      <v-text-field :value="grossGrams" type="number" :min="spoolDraft.tare" step="any" :label="$u1t('Общий вес на весах, г')" dense :disabled="busy || !spoolDraft.coreId" @input="setGross" />
      <p v-if="spoolDraft.inheritPurchasePrice !== false">{{ $u1t('Цена покупки катушки, €') }}: {{ colors.find(c => c.id === spoolDraft?.colorId)?.purchasePrice ?? '—' }}</p>
      <v-checkbox :input-value="spoolDraft.inheritPurchasePrice !== false" :label="$u1t('Наследовать закупочную цену из библиотеки')" @change="$set(spoolDraft, 'inheritPurchasePrice', $event)" />
      <template v-if="spoolDraft.inheritPurchasePrice === false">
        <v-text-field v-model.number="spoolDraft.purchasePrice" type="number" min="0" :label="$u1t('Цена покупки катушки, €')" />
        <v-text-field v-model.number="spoolDraft.purchaseWeight" type="number" min="1" :label="$u1t('Масса купленного филамента, г')" />
      </template>
      <v-text-field v-model="spoolPrice" type="number" min="0" step="any" :label="$u1t('Цена для клиента за грамм, €')" dense :disabled="busy" />
      <v-alert v-if="draftError" type="error">{{ draftError }}</v-alert>
      <v-btn :disabled="busy" @click="spoolDraft = null">{{ $u1t("Отмена") }}</v-btn>
      <v-btn color="primary" :loading="busy" @click="saveSpool">{{ $u1t("Сохранить") }}</v-btn>
    </v-card>
  </v-dialog>
  <v-dialog content-class="u1-dialog u1-unified-dialog" :value="coreDraft !== null" max-width="480" persistent>
    <v-card v-if="coreDraft" class="pa-5">
      <u1-dialog-close @close="coreDraft = null" />
      <h2>{{ $u1t("Пустая катушка") }}</h2>
      <v-text-field v-model="coreDraft.name" :label="$u1t('Название или модель')" maxlength="100" :disabled="busy" />
      <v-select v-model="coreDraft.kind" :items="coreKinds" :label="$u1t('Материал катушки')" :disabled="busy" />
      <v-text-field v-model="coreGrams" type="number" min="0" step="any" :label="$u1t('Вес пустой катушки, г')" :disabled="busy" />
      <v-alert v-if="coreError" type="error">{{ coreError }}</v-alert>
      <v-btn :disabled="busy" @click="coreDraft = null">{{ $u1t("Отмена") }}</v-btn>
      <v-btn color="primary" :loading="busy" @click="saveCore">{{ $u1t("Сохранить") }}</v-btn>
    </v-card>
  </v-dialog>
</div>
</template>

<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import { Component, Prop, Watch } from 'vue-property-decorator'
import axios from 'axios'
import { v4 as uuid } from 'uuid'
import { mdiQrcode } from '@mdi/js'
import { httpClientActions as http } from '@/api/httpClientActions'
import { groupFilaments, validatePreset, type FilamentPreset } from '@/utils/u1Filament'
import { formatUnitPrice } from '@/utils/u1SpoolStats'
import { tagAddress, tagUrl } from '@/utils/nfcFilament'
import { renderPlainQr } from '@/utils/plainQrLabel'
import { printPng } from '@/utils/pngPrintSize'
import QrScanner from '@/utils/reliableQrScanner'
import clipboardCopy from '@/util/clipboard-copy'
import { readU1Item, u1DataRequest } from '@/utils/u1DataClient'
import { calibrationSummary } from '@/utils/u1Calibration'

interface Color extends FilamentPreset { id: string; name: string; nozzleTemperature?: number; bedTemperature?: number }
interface Core { id: string; name: string; kind: string; grams: number }
export interface Spool extends Color { colorId: string; coreId: string; coreName: string; grams: number; tare: number; accountedGrams?: number; pricePerGram?: number; inheritPurchasePrice?: boolean }
export function remainingGrams (spool: Spool, totals: Record<string, number>) {
  const spent = Math.max(0, (totals[spool.id] || 0) - (spool.accountedGrams || 0))
  return Math.max(0, Number((spool.grams - spent).toFixed(3)))
}
interface Inventory { revision: string; spools: Spool[]; cores: Core[]; heads: (string | null)[]; trash: Spool[]; individualCalibration?: boolean }
const key = 'u1_spool_inventory_v1'
const emptyInventory = (): Inventory => ({ revision: '', spools: [], cores: [], heads: [null, null, null, null], trash: [] })
const coreKinds = [u1t("Картон / бумага"), u1t("Пластик"), u1t("Другое")]

function grams (input: string, allowZero: boolean) {
  const value = Number(input)
  if (!input.trim() || !Number.isFinite(value) || value < 0 || (!allowZero && value === 0)) {
    throw new Error(allowZero ? u1t("Введите остаток в граммах, от 0") : u1t("Введите вес пустой катушки больше 0 г"))
  }
  return value
}

@Component
export default class U1SpoolInventory extends Vue {
  @Prop({ default: () => [] }) readonly colors!: Color[]
  @Prop({ default: () => ({}) }) readonly totals!: Record<string, number>
  inventory = emptyInventory()
  opened = false
  ready = false
  busy = false
  section: 'spools' | 'cores' = 'spools'
  target: number | null = null
  spoolSearch = ''
  error = ''
  draftError = ''
  coreError = ''
  removeError = ''
  removing: { spool: Spool; permanent: boolean } | null = null
  qrIcon = mdiQrcode
  qrSpool: Spool | null = null
  qrAddress = ''
  qrPng = ''
  qrStatus = ''
  spoolDraft: Spool | null = null
  coreDraft: Core | null = null
  spoolGrams = ''
  spoolPrice = ''
  formatUnitPrice = formatUnitPrice
  originalGrams = ''
  coreGrams = ''
  coreKinds = coreKinds

  get title () {
    if (this.section === 'cores') return u1t("Пустые катушки")
    return this.target === null ? u1t("Мои катушки") : u1t("Катушка для головки {p0}", { p0: this.target + 1 })
  }

  get spoolGroups () { return groupFilaments(this.inventory.spools) }

  get matchingSpools () {
    const words = (this.spoolSearch || '').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
    return this.inventory.spools.filter(spool => {
      const text = [spool.name, spool.manufacturer, spool.material, spool.hex, spool.id, spool.coreName].filter(Boolean).join(' ').toLocaleLowerCase()
      return words.every(word => text.includes(word))
    })
  }

  get colorItems () {
    const items = this.colors.map(color => ({
      value: color.id,
      hex: color.hex,
      text: [color.hex, color.name, color.material, color.manufacturer].filter(Boolean).join(' · ')
    }))
    const draft = this.spoolDraft
    if (draft?.colorId && !items.some(item => item.value === draft.colorId)) {
      items.push({ value: draft.colorId, hex: draft.hex, text: u1t("{p0} · {p1} (сохранённая основа)", { p0: draft.hex, p1: draft.material }) })
    }
    return items
  }

  get coreItems () {
    return this.inventory.cores.map(core => ({ value: core.id, text: u1t("{p0} · {p1} г", { p0: core.name, p1: core.grams }) }))
  }

  get grossGrams () {
    if (!this.spoolDraft?.coreId || this.spoolGrams === '') return ''
    return this.weight(Number(this.spoolGrams) + this.spoolDraft.tare)
  }

  weight (value: number) { return Number(value.toFixed(3)) }
  remaining (spool: Spool) { return remainingGrams(spool, this.totals) }
  spoolCalibration (spool: Spool) {
    const individual = this.inventory.individualCalibration === true
    const value = individual ? spool.calibration : this.colors.find(color => color.id === spool.colorId)?.calibration
    return u1t("{p0}: {p1}", { p0: individual ? u1t("Калибровка катушки") : u1t("Общая калибровка"), p1: calibrationSummary(value) })
  }

  spoolTemperatures (spool: Pick<Spool, 'colorId' | 'nozzleTemperature' | 'bedTemperature'>) {
    const color = this.colors.find(color => color.id === spool.colorId)
    const value = (field: 'nozzleTemperature' | 'bedTemperature') => {
      const own = spool[field]
      const inherited = color?.[field]
      return own != null && String(own).trim() !== '' ? u1t("{p0} °C (своя)", { p0: own }) : (inherited == null ? u1t("из слайсера") : u1t("{p0} °C (из цвета)", { p0: inherited }))
    }
    return u1t("Температуры: сопло {p0} · стол {p1}", { p0: value('nozzleTemperature'), p1: value('bedTemperature') })
  }

  inheritTemperatureHint (field: 'nozzleTemperature' | 'bedTemperature') {
    const inherited = this.colors.find(color => color.id === this.spoolDraft?.colorId)?.[field]
    return u1t("Пусто — наследовать: {p0}", { p0: inherited == null ? u1t("температура из слайсера") : inherited + u1t(" °C из цвета") })
  }

  inheritTemperatures () {
    if (this.spoolDraft) {
      Vue.delete(this.spoolDraft, 'nozzleTemperature')
      Vue.delete(this.spoolDraft, 'bedTemperature')
    }
  }

  setGross (input: string) {
    const draft = this.spoolDraft
    if (draft) this.spoolGrams = input === '' ? '' : String(this.weight(Number(input) - draft.tare))
  }

  async read (): Promise<Inventory> {
    try {
      const result = await readU1Item<Inventory>(key)
      const value = result.data.result.value
      if (!value || typeof value.revision !== 'string' || !Array.isArray(value.spools) || !Array.isArray(value.cores) ||
          (value.trash !== undefined && !Array.isArray(value.trash)) ||
          !Array.isArray(value.heads) || value.heads.length !== 4 || value.heads.some(id => id !== null && !value.spools.some(spool => spool.id === id))) {
        throw new Error(u1t("Неверный формат списка катушек"))
      }
      return { ...value, trash: value.trash ?? [] }
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) return emptyInventory()
      throw error
    }
  }

  async load () {
    if (this.busy) return
    this.busy = true
    this.error = ''
    try {
      this.inventory = await this.read()
      this.ready = true
    } catch (error) { this.error = String(error) } finally { this.busy = false }
  }

  async persist (next: Inventory) {
    const before = await this.read()
    if (before.revision !== next.revision) {
      throw new Error(u1t("Список изменился на другом устройстве. Обновите его и повторите действие."))
    }
    const result = await u1DataRequest<{value: Inventory}>('inventory', { value: next })
    const after = await this.read()
    if (after.revision !== result.value.revision) throw new Error(u1t("Принтер не подтвердил сохранение списка катушек"))
    this.inventory = after
    this.ready = true
  }

  open (section: 'spools' | 'cores', slot: number | null = null) {
    this.section = section
    this.target = slot
    this.opened = true
    this.load()
  }

  newSpool () {
    this.editSpool({ id: uuid(), colorId: '', coreId: '', coreName: '', name: '', material: '', hex: '#FFFFFF', manufacturer: '', grams: 0, tare: 0 })
    this.spoolGrams = ''
  }

  editSpool (spool: Spool) {
    this.draftError = ''
    this.spoolDraft = { ...spool }
    this.spoolGrams = String(this.remaining(spool))
    this.originalGrams = this.spoolGrams
    this.spoolPrice = spool.pricePerGram == null ? '' : String(spool.pricePerGram)
  }

  setColor (id: string) {
    const color = this.colors.find(item => item.id === id)
    if (!color || !this.spoolDraft) return
    this.spoolDraft = { ...this.spoolDraft, ...validatePreset(color), manufacturer: color.manufacturer || '', colorId: id, name: this.spoolDraft.name || color.name }
  }

  setCore (id: string) {
    const core = this.inventory.cores.find(item => item.id === id)
    if (core && this.spoolDraft) this.spoolDraft = { ...this.spoolDraft, coreId: id, coreName: core.name, tare: core.grams }
  }

  async saveSpool () {
    if (!this.spoolDraft || this.busy) return
    this.busy = true
    this.draftError = ''
    try {
      const draft = this.spoolDraft
      const name = draft.name.trim()
      if (!draft.colorId || !draft.coreId || !name) throw new Error(u1t("Выберите основу, пустую катушку и укажите название"))
      const spools = this.inventory.spools.slice()
      const index = spools.findIndex(item => item.id === draft.id)
      const entered = grams(this.spoolGrams, true)
      const spool = { ...draft, ...validatePreset(draft), name }
      for (const [field, low, high] of [['nozzleTemperature', 150, 300], ['bedTemperature', 20, 100]] as const) {
        const raw = spool[field]
        if (raw == null || String(raw).trim() === '') delete spool[field]
        else {
          const value = Number(String(raw).replace(',', '.'))
          if (!Number.isFinite(value) || value < low || value > high) throw new Error(u1t("Температура {p0}: от {p1} до {p2} °C", { p0: field === 'nozzleTemperature' ? u1t("сопла") : u1t("стола"), p1: low, p2: high }))
          spool[field] = value
        }
      }
      for (const field of ['purchasePrice','purchaseWeight'] as const) {
        const raw = spool[field]; if (raw == null || String(raw).trim() === '') delete spool[field];
        else { const n = Number(raw); if (!Number.isFinite(n) || n < 0 || (field === 'purchaseWeight' && n === 0)) throw new Error(u1t('Введите положительную массу и цену от 0 €')); spool[field] = n }
      }
      const rawPrice = this.spoolPrice.trim().replace(',', '.')
      if (rawPrice) {
        const price = Number(rawPrice)
        if (!Number.isFinite(price) || price < 0) throw new Error(u1t("Введите цену за грамм от 0 €"))
        spool.pricePerGram = price
      } else {
        delete spool.pricePerGram
      }
      if (index === -1 || entered !== Number(this.originalGrams)) {
        let totals = this.totals
        if (index !== -1 && this.inventory.heads.includes(spool.id)) {
          const status = await http.get<{result: {status: {print_stats: {state: string}}}}>('/printer/objects/query?print_stats')
          if (['printing', 'paused'].includes(status.data.result.status.print_stats.state)) {
            throw new Error(u1t("Измените вес привязанной катушки после окончания печати."))
          }
        }
        try {
          const usage = await readU1Item<{
            totals: Record<string, number>;
            tracked: {rows: {spoolId?: string}[]} | null;
            records: {state: string; rows: {spoolId?: string}[]}[];
          }>('u1_spool_usage_v1')
          const value = usage.data.result.value
          if (value.tracked?.rows.some(row => row.spoolId === spool.id) ||
              value.records.some(record => record.state === 'review' && record.rows.some(row => row.spoolId === spool.id))) {
            throw new Error(u1t("Сначала дождитесь списания или подтвердите расход в журнале."))
          }
          totals = value.totals
        } catch (error) {
          if (!(axios.isAxiosError(error) && error.response?.status === 404)) throw error
        }
        spool.grams = entered
        spool.accountedGrams = totals[spool.id] || 0
      }
      if (index === -1) spools.push(spool)
      else spools.splice(index, 1, spool)
      await this.persist({ ...this.inventory, spools })
      this.spoolDraft = null
    } catch (error) { this.draftError = String(error) } finally { this.busy = false }
  }

  editCore (core?: Core) {
    this.coreError = ''
    this.coreDraft = core ? { ...core } : { id: uuid(), name: '', kind: coreKinds[0], grams: 0 }
    this.coreGrams = core ? String(core.grams) : ''
  }

  removeSpool (spool: Spool, permanent: boolean) {
    this.removeError = ''
    this.removing = { spool, permanent }
  }

  async confirmRemoval () {
    if (!this.removing || this.busy) return
    const { spool, permanent } = this.removing
    const current = this.inventory
    this.busy = true
    this.removeError = ''
    try {
      if (permanent) {
        await this.persist({ ...current, trash: current.trash.filter(item => item.id !== spool.id) })
      } else {
        const activeSpool = current.spools.find(item => item.id === spool.id)
        if (!activeSpool) throw new Error(u1t("Катушка уже отсутствует в списке."))
        if (current.heads.includes(spool.id)) {
          const status = await http.get<{result: {status: {idle_timeout: {state: string}; print_stats: {state: string}}}}>('/printer/objects/query?print_stats&idle_timeout')
          const { idle_timeout: idle, print_stats: stats } = status.data.result.status
          if (idle.state !== 'Idle' || !['standby', 'complete', 'cancelled'].includes(stats.state)) {
            throw new Error(u1t("Дождитесь окончания печати перед удалением привязанной катушки."))
          }
        }
        await this.persist({
          ...current,
          spools: current.spools.filter(item => item.id !== spool.id),
          heads: current.heads.map(id => id === spool.id ? null : id),
          trash: [...current.trash, activeSpool]
        })
      }
      this.removing = null
    } catch (error) { this.removeError = String(error) } finally { this.busy = false }
  }

  async restoreSpool (spool: Spool) {
    if (this.busy || !this.inventory.trash.some(item => item.id === spool.id)) return
    this.busy = true
    this.error = ''
    try {
      const current = this.inventory
      await this.persist({
        ...current,
        spools: [...current.spools, spool],
        trash: current.trash.filter(item => item.id !== spool.id)
      })
    } catch (error) { this.error = String(error) } finally { this.busy = false }
  }

  async saveCore () {
    if (!this.coreDraft || this.busy) return
    this.busy = true
    this.coreError = ''
    try {
      const name = this.coreDraft.name.trim()
      if (!name) throw new Error(u1t("Введите название пустой катушки"))
      const core = { ...this.coreDraft, name, grams: grams(this.coreGrams, false) }
      const cores = this.inventory.cores.slice()
      const index = cores.findIndex(item => item.id === core.id)
      if (index === -1) cores.push(core)
      else cores.splice(index, 1, core)
      await this.persist({ ...this.inventory, cores })
      if (this.spoolDraft) this.setCore(core.id)
      this.coreDraft = null
    } catch (error) { this.coreError = String(error) } finally { this.busy = false }
  }

  writeTag (spool: Spool) {
    this.opened = false
    this.$emit('write-tag', { ...spool, spoolId: spool.id })
  }

  async openSpoolQr (spool: Spool) {
    this.qrSpool = spool
    this.qrAddress = ''
    this.qrPng = ''
    this.qrStatus = u1t("Создаю и проверяю этикетку…")
    try {
      const url = tagUrl({ ...spool, spoolId: spool.id }, window.location.origin)
      this.qrAddress = tagAddress(url)
      const label = await renderPlainQr(url, `${spool.material} ${spool.hex}`, spool.name)
      const decoded = await QrScanner.scanImage(label, { returnDetailedScanResult: true })
      if (decoded.data !== url) throw new Error(u1t("Этикетка не прошла проверку чтения."))
      if (this.qrSpool === spool) {
        this.qrPng = printPng(label)
        this.qrStatus = ''
      }
    } catch (error) {
      if (this.qrSpool === spool) this.qrStatus = String(error)
    }
  }

  closeSpoolQr (opened: boolean) {
    if (!opened) this.qrSpool = null
  }

  async copyQrAddress () {
    const field = this.$refs.qrAddress as Vue | undefined
    this.qrStatus = await clipboardCopy(this.qrAddress, field?.$el)
      ? u1t("Адрес скопирован без протокола.")
      : u1t("Выделите и скопируйте адрес вручную.")
  }

  choose (spool: Spool) {
    if (this.target === null) return
    this.opened = false
    this.$emit('choose', { slot: this.target, preset: { ...spool, spoolId: spool.id } })
  }

  mounted () { this.load() }

  @Watch('inventory')
  publishInventory () { this.$emit('inventory', this.inventory) }

  async findSpool (id: string) {
    const inventory = await this.read()
    return inventory.spools.find(spool => spool.id === id)
  }

  async readRemainingGrams (spool: Spool) {
    try {
      const response = await readU1Item<{ totals: Record<string, number> }>('u1_spool_usage_v1')
      return remainingGrams(spool, response.data.result.value.totals)
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) return remainingGrams(spool, {})
      throw error
    }
  }

  async assign (slot: number, spoolId: string | null) {
    const current = await this.read()
    if (spoolId && !current.spools.some(spool => spool.id === spoolId)) throw new Error(u1t("Катушка не найдена"))
    const heads = current.heads.map((id, index) => index === slot ? spoolId : id === spoolId ? null : id)
    if (heads.every((id, index) => id === current.heads[index])) {
      this.inventory = current
      return
    }
    await this.persist({ ...current, heads })
  }
}
</script>

<style scoped>
.spool-swatch { display: inline-block; width: 1em; height: 1em; margin-right: .5em; border-radius: 50%; border: 1px solid #999; vertical-align: middle }
.spool-qr-image { display: block; max-width: 100%; width: 280px; height: auto; margin: 0 auto }
</style>
