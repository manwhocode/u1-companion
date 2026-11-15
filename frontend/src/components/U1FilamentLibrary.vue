<template>
<div>
  <v-btn @click="openManager"><v-icon left>$filamentSpool</v-icon>{{ $u1t("Мои цвета ·") }} {{ entries.length }}</v-btn>
  <v-dialog content-class="u1-dialog u1-unified-dialog" v-model="opened" max-width="900" scrollable>
  <v-card class="pa-4">
      <u1-dialog-close @close="opened = false" />
  <v-card-title>{{ title }}<v-spacer /></v-card-title>
  <v-card-text>
  <p>{{ $u1t("Библиотека хранится на принтере. Выбор только заполняет форму головки.") }}</p>
  <v-alert v-if="message" :type="failed ? 'error' : 'success'">{{ message }}</v-alert>
  <div v-if="!fullSpectrumOnly" class="library-dialog-actions">
    <v-btn outlined :disabled="busy" @click="load">{{ $u1t("Обновить библиотеку") }}</v-btn>
    <v-btn outlined :disabled="busy" @click="editNew">{{ $u1t("Добавить цвет") }}</v-btn>
    <v-btn outlined @click="$emit('read-tag')">{{ $u1t("Считать NFC-метку") }}</v-btn>
    <v-btn color="primary" @click="openCatalog">{{ $u1t("Каталог Snapmaker") }}</v-btn>
  </div>
  <v-text-field v-model="search" :label="$u1t('Поиск по производителю, названию, материалу или HEX')" />
  <p v-if="!visible.length">{{ emptyMessage }}</p>
  <v-expansion-panels :value="expandGroups ? groups.map((_, i) => i) : undefined" multiple>
  <v-expansion-panel v-for="group in groups" :key="group.name">
    <v-expansion-panel-header>📁 {{ group.name }} ({{ group.count }})</v-expansion-panel-header>
    <v-expansion-panel-content>
    <v-expansion-panels :value="expandGroups ? group.materials.map((_, i) => i) : undefined" multiple>
    <v-expansion-panel v-for="material in group.materials" :key="material.name">
    <v-expansion-panel-header>{{ material.name }} ({{ material.entries.length }})</v-expansion-panel-header>
    <v-expansion-panel-content><v-row>
    <v-col v-for="entry in material.entries" :key="entry.id" cols="12" sm="6" lg="4">
      <v-card outlined class="pa-3">
        <h3><span class="swatch" :style="{ background: swatch(entry.hex, entry.secondaryHex) }" />{{ entry.name }}</h3>
        <p>{{ entry.material }} · {{ entry.hex }}{{ entry.secondaryHex ? ' / ' + entry.secondaryHex : '' }}{{ entry.fullSpectrum ? ' · Full Spectrum' : '' }}</p>
        <v-btn v-if="target !== null" small color="primary" class="ma-1" :disabled="busy" @click="choose(entry)">{{ $u1t("В головку") }} {{ target + 1 }}</v-btn>
        <p v-if="entry.nozzleTemperature != null || entry.bedTemperature != null">{{ $u1t("Сопло:") }} {{ entry.nozzleTemperature == null ? $u1t("из слайсера") : entry.nozzleTemperature + ' °C' }} {{ $u1t("· Стол:") }} {{ entry.bedTemperature == null ? $u1t("из слайсера") : entry.bedTemperature + ' °C' }}</p>
        <v-btn small class="ma-1" :disabled="busy" @click="draft = {...entry}">{{ $u1t("Изменить") }}</v-btn>
        <v-btn small outlined class="ma-1" :disabled="busy" @click="$emit('error-history', {id: entry.id, name: entry.name})">{{ $u1t("История ошибок") }}</v-btn>
        <v-btn small class="ma-1" :disabled="busy" @click="$emit('calibration', entry.id)">{{ $u1t("Калибровка") }}</v-btn>
        <v-btn small class="ma-1" @click="$emit('write-tag', entry)">{{ $u1t("Записать NFC-метку") }}</v-btn>
        <v-btn small class="ma-1" :disabled="busy" @click="removing = { entry, permanent: false }">{{ $u1t("Удалить") }}</v-btn>
      </v-card>
    </v-col>
    </v-row></v-expansion-panel-content>
  </v-expansion-panel></v-expansion-panels>
  </v-expansion-panel-content>
  </v-expansion-panel></v-expansion-panels>
  <v-expansion-panels v-if="!fullSpectrumOnly && trash.length && opened" class="mt-3">
    <v-expansion-panel><v-expansion-panel-header>{{ $u1t("Корзина (") }}{{ trash.length }})</v-expansion-panel-header><v-expansion-panel-content>
      <div v-for="entry in trash" :key="entry.id" class="my-2">
        {{ entry.name }} · {{ entry.material }} {{ entry.hex }}
        <v-btn small class="ma-1" :disabled="busy" @click="restore(entry)">{{ $u1t("Восстановить") }}</v-btn>
        <v-btn small text color="error" class="ma-1" :disabled="busy" @click="removing = { entry, permanent: true }">{{ $u1t("Удалить навсегда") }}</v-btn>
      </div>
    </v-expansion-panel-content></v-expansion-panel>
  </v-expansion-panels>
  </v-card-text>
  </v-card></v-dialog>
  <v-dialog content-class="u1-dialog u1-unified-dialog" v-model="catalogOpen" max-width="760" scrollable>
    <v-card>
      <u1-dialog-close @close="catalogOpen = false" />
      <v-card-title>{{ $u1t("Каталог Snapmaker") }}</v-card-title>
      <v-card-text>
        <v-btn block outlined color="primary" class="catalog-shop-button mb-3"
          :href="shopUrl('https://eu.snapmaker.com/collections/3d-printer-filament')" target="_blank" rel="noopener noreferrer">
          <v-icon left small>{{ cartIcon }}</v-icon>
          {{ $u1t("Магазин Snapmaker") }}
        </v-btn>
        <p>{{ $u1t("Выберите цвет, чтобы добавить его в «Мои цвета».") }}</p>
        <v-alert v-if="catalogMessage" :type="failed ? 'error' : 'success'">{{ catalogMessage }}</v-alert>
        <v-alert v-else-if="!ready && failed" type="error">{{ message }}</v-alert>
        <v-text-field v-model="catalogSearch" :label="$u1t('Найти по серии, цвету или HEX')" outlined dense />
        <v-expansion-panels :value="catalogSearch ? visibleCatalog.map((_, i) => i) : undefined" multiple>
          <v-expansion-panel v-for="family in visibleCatalog" :key="family.name">
            <v-expansion-panel-header>{{ family.name }} · {{ family.variants.length }}</v-expansion-panel-header>
            <v-expansion-panel-content>
              <v-btn block outlined color="primary" class="catalog-shop-button mb-2" :aria-label="$u1t('Купить ') + family.name"
                :href="shopUrl(family.url)" :title="$u1t('Купить в Snapmaker EU по партнёрской ссылке')" target="_blank" rel="noopener noreferrer">
                <v-icon left small>{{ cartIcon }}</v-icon>
                {{ $u1t("Купить филамент") }}
              </v-btn>
              <div v-for="[id, color, hex, secondaryHex] in family.variants" :key="id" class="catalog-row">
                <span v-if="hex" class="swatch" :style="{ background: swatch(hex, secondaryHex) }" />
                <span>{{ family.name }} - {{ color }}
                  <small>{{ hex ? [hex, secondaryHex].filter(Boolean).join(' / ') : $u1t("HEX не указан") }}</small>
                </span>
                <v-spacer />
                <v-text-field v-if="!hex && !catalogAdded.has(id) && !catalogInTrash.has(id)" v-model="catalogHex[id]"
                  class="catalog-hex" :label="$u1t('Введите HEX')" placeholder="#FFFFFF" maxlength="7" dense hide-details />
                <v-btn small outlined :disabled="!ready || busy || catalogAdded.has(id) || (!hex && !catalogInTrash.has(id) && !validHex(catalogHex[id]))"
                  @click="addCatalog(id, family.name + ' - ' + color, family.material, hex || catalogHex[id], secondaryHex, family.fullSpectrum)">
                  {{ catalogAdded.has(id) ? $u1t("Добавлен") : $u1t("Добавить") }}
                </v-btn>
              </div>
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
        <p v-if="!visibleCatalog.length">{{ $u1t("Цвета не найдены.") }}</p>
      </v-card-text>
      
    </v-card>
  </v-dialog>
  <v-dialog content-class="u1-dialog u1-unified-dialog" :value="draft !== null" max-width="500" persistent>
    <v-card v-if="draft" class="pa-5">
      <u1-dialog-close @close="draft = null" />
      <h2>{{ entries.some(e => e.id === draft?.id) ? $u1t("Изменить цвет") : $u1t("Добавить цвет") }}</h2>
      <v-text-field v-model="draft.name" :label="$u1t('Название цвета / катушки')" maxlength="100" :disabled="busy" />
      <v-combobox v-model="draft.manufacturer" :items="manufacturers" :label="$u1t('Производитель (название папки)')" :disabled="busy" />
      <v-select v-model="draft.material" :items="materials" :label="$u1t('Материал')" :disabled="busy" />
      <v-text-field v-model="draft.hex" label="HEX" maxlength="7" :disabled="busy" />
      <input v-model="draft.hex" type="color" :disabled="busy">
      <v-text-field v-model="draft.nozzleTemperature" :label="$u1t('Температура сопла, °C')" type="number" min="150" max="300" step="1" inputmode="decimal" :hint="$u1t('150–300 °C. Пусто — значение из слайсера.')" persistent-hint :disabled="busy" />
      <v-text-field v-model="draft.bedTemperature" :label="$u1t('Температура стола, °C')" type="number" min="20" max="100" step="1" inputmode="decimal" :hint="$u1t('20–100 °C. Пусто — значение из слайсера.')" persistent-hint :disabled="busy" />
      <p>{{ $u1t("Связанные катушки наследуют эти температуры, если у катушки не заданы свои значения. Новые значения применяются при следующем запуске печати. Прогрев для очистки сопла и команды отключения нагрева сохраняются.") }}</p>
      <v-checkbox v-model="draft.fullSpectrum" :label="$u1t('Цвет из Full Spectrum')" dense hide-details :disabled="busy" />
      <p v-if="editError" role="alert">{{ editError }}</p>
      <div class="color-draft-actions">
        <v-btn outlined :disabled="busy" @click="draft = null">{{ $u1t("Отмена") }}</v-btn>
        <v-btn color="primary" :loading="busy" @click="saveDraft">{{ $u1t("Сохранить цвет") }}</v-btn>
      </div>
    </v-card>
  </v-dialog>
  <v-dialog content-class="u1-dialog u1-unified-dialog" :value="removing !== null" max-width="450" persistent>
    <v-card v-if="removing" class="pa-5">
      <u1-dialog-close @close="removing=null" />
      <h2>{{ $u1t("Удалить «") }}{{ removing.entry.name }}»?</h2>
      <p>{{ removing.permanent ? $u1t("Цвет будет удалён из корзины.") : $u1t("Цвет будет перемещён в корзину.") }}</p>
      <v-btn :disabled="busy" @click="removing=null">{{ $u1t("Отмена") }}</v-btn>
      <v-btn color="error" :loading="busy" @click="remove">{{ removing.permanent ? $u1t("Удалить навсегда") : $u1t("В корзину") }}</v-btn>
    </v-card>
  </v-dialog>

</div>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { mdiCartOutline } from '@mdi/js'
import { v4 as uuid } from 'uuid'
import axios from 'axios'
import { readU1Item, u1DataRequest } from '@/utils/u1DataClient'
import { groupFilaments, materials, validatePreset, type FilamentPreset } from '@/utils/u1Filament'
import { snapmakerCatalog } from '@/utils/snapmakerCatalog'
import { snapmakerReferralUrl } from '@/utils/snapmakerReferral'
export interface Entry extends FilamentPreset { id: string; name: string; manufacturer?: string; secondaryHex?: string; fullSpectrum?: boolean; nozzleTemperature?: number; bedTemperature?: number }
interface Library { revision: string; entries: Entry[]; trash: Entry[] }
const key = 'u1_filament_library_v1'
@Component
export default class U1FilamentLibrary extends Vue {
  entries: Entry[] = []
  trash: Entry[] = []
  materials = materials
  target: number | null = null
  fullSpectrumOnly = false
  opened = false
  catalogOpen = false
  cartIcon = mdiCartOutline
  shopUrl = snapmakerReferralUrl
  catalogSearch = ''
  catalogHex: Record<string, string> = {}
  catalogMessage = ''
  search = ''
  revision = ''
  ready = false
  busy = false
  message = ''
  failed = false
  editError = ''
  draft: Entry | null = null
  removing: { entry: Entry; permanent: boolean } | null = null
  get title () {
    if (this.target === null) return u1t("Библиотека цветов")
    return this.fullSpectrumOnly ? u1t("Full Spectrum · Головка {p0}", { p0: this.target + 1 }) : u1t("Цвет для головки {p0}", { p0: this.target + 1 })
  }
  get expandGroups () { return this.fullSpectrumOnly || !!this.search.trim() }
  get emptyMessage () {
    if (!this.ready) return u1t("Загрузка библиотеки…")
    if (this.search.trim()) return u1t("Цвета не найдены.")
    return this.fullSpectrumOnly ? u1t("Отметьте нужные цвета галочкой «Цвет из Full Spectrum» в «Моих цветах».") : u1t("Нет сохранённых цветов")
  }
  get visible () {
    const search = this.search.trim().toLowerCase()
    return this.entries.filter(entry => (!this.fullSpectrumOnly || entry.fullSpectrum === true) &&
      u1t("{p0} {p1} {p2} {p3}", { p0: entry.manufacturer || u1t("Без производителя"), p1: entry.name, p2: entry.material, p3: entry.hex }).toLowerCase().includes(search))
  }
  get visibleCatalog () {
    const terms = this.catalogSearch.toLowerCase().split(/\s+/).filter(term => term && term !== '-')
    return snapmakerCatalog.map(family => ({
      ...family,
      variants: family.variants.filter(([, color, hex, secondaryHex]) => {
        const label = `${family.name} ${family.material} ${color} ${hex} ${secondaryHex || ''}`.toLowerCase()
        return terms.every(term => label.includes(term))
      })
    })).filter(family => family.variants.length)
  }

  get catalogAdded () {
    return new Set(this.entries.filter(entry => entry.id.startsWith('snapmaker-')).map(entry => entry.id.slice(10)))
  }

  get catalogInTrash () {
    return new Set(this.trash.filter(entry => entry.id.startsWith('snapmaker-')).map(entry => entry.id.slice(10)))
  }

  validHex (value?: string) {
    return /^#?[0-9a-f]{6}$/i.test(value?.trim() || '')
  }

  swatch (hex: string, secondaryHex?: string) {
    return secondaryHex && this.validHex(secondaryHex)
      ? `linear-gradient(135deg, ${hex} 50%, ${secondaryHex} 50%)`
      : hex
  }

  openCatalog () {
    this.catalogSearch = ''
    this.catalogMessage = ''
    this.catalogOpen = true
    if (!this.ready && !this.busy) this.load()
  }

  async addCatalog (variant: string, name: string, material: string, hex?: string, secondaryHex?: string, fullSpectrum = false) {
    if (this.busy || !this.ready || this.catalogAdded.has(variant)) return
    this.busy = true
    this.catalogMessage = ''
    try {
      const id = 'snapmaker-' + variant
      const previous = this.trash.find(item => item.id === id) ||
        { ...validatePreset({ material, hex: hex || '', manufacturer: 'Snapmaker' }), id, name, ...(secondaryHex ? { secondaryHex } : {}) }
      const entry = fullSpectrum ? { ...previous, fullSpectrum: true } : previous
      await this.persist([...this.entries, entry], this.trash.filter(item => item.id !== id))
      this.catalogMessage = u1t("{p0} добавлен в «Мои цвета».", { p0: entry.name })
    } catch (error) {
      this.failed = true
      this.catalogMessage = error instanceof Error ? error.message : String(error)
    } finally { this.busy = false }
  }
  get manufacturers () { return [...new Set(['Snapmaker', 'Bambu Lab', 'eSUN', 'SUNLU', 'Polymaker', ...this.entries.map(e => e.manufacturer || '')])].filter(Boolean).sort() }
  get groups () { return groupFilaments(this.visible) }
  openManager () { this.target = null; this.fullSpectrumOnly = false; this.opened = true }
  openForHead (slot: number, fullSpectrumOnly = false) {
    if (!Number.isInteger(slot) || slot < 0 || slot > 3) return
    this.target = slot
    this.fullSpectrumOnly = fullSpectrumOnly
    this.search = ''
    this.opened = true
  }
  choose (entry: Entry) { if (this.target === null) return; this.$emit('select', { slot: this.target, preset: entry }); this.opened = false }
  mounted () { this.load() }
  async read (): Promise<Library> {
    try {
      const r = await readU1Item<Library>(key)
      const v = r.data.result.value
      if (!v || typeof v.revision !== 'string' || !Array.isArray(v.entries) || !Array.isArray(v.trash)) throw new Error(u1t("Неверный формат библиотеки; запись остановлена"))
      for (const entry of [...v.entries, ...v.trash]) { validatePreset(entry); if (!entry.id || !entry.name) throw new Error(u1t("Повреждена запись библиотеки")) }
      return v
    } catch (e) {
      if (axios.isAxiosError(e) && e.response?.status === 404) return { revision: '', entries: [], trash: [] }
      throw e
    }
  }
  async load () {
    this.busy = true
    try { const v = await this.read(); this.entries = v.entries; this.trash = v.trash; this.revision = v.revision; this.ready = true; this.$emit('entries', this.entries) }
    catch (e) { this.failed = true; this.message = String(e) }
    finally { this.busy = false }
  }
  editNew () { this.editError = ''; this.draft = { id: uuid(), name: '', manufacturer: '', material: 'PLA', hex: '#FFFFFF' } }
  addFromHead (preset: FilamentPreset, slot: number) { this.editError = ''; this.draft = { ...validatePreset(preset), id: uuid(), name: u1t("Головка {p0} · {p1} {p2}", { p0: slot + 1, p1: preset.material, p2: preset.hex }) } }
  addFromTag (preset: FilamentPreset & {name?: string; manufacturer?: string}) { this.editError = ''; this.draft = { ...validatePreset(preset), id: uuid(), name: preset.name || `${preset.material} ${preset.hex}`, manufacturer: preset.manufacturer || '' } }
  async persist (entries: Entry[], trash: Entry[]) {
    if (!this.ready) throw new Error(u1t("Сначала загрузите библиотеку"))
    const before = await this.read()
    if (before.revision !== this.revision) throw new Error(u1t("Библиотека изменена на другом устройстве. Обновите её и повторите действие."))
    const result = await u1DataRequest<{value: Library}>('library', { value: { revision: this.revision, entries, trash } })
    const after = await this.read()
    if (JSON.stringify(after) !== JSON.stringify(result.value)) throw new Error(u1t("Сохранение не подтверждено. Обновите библиотеку."))
    this.entries = after.entries; this.trash = after.trash; this.revision = after.revision
    this.$emit('entries', this.entries)
    this.failed = false; this.message = u1t("Библиотека сохранена на принтере")
  }
  async saveDraft () {
    if (!this.draft || this.busy) return
    this.busy = true; this.editError = ''
    try {
      const entry = { ...this.draft, ...validatePreset(this.draft), name: this.draft.name.trim(), manufacturer: String(this.draft.manufacturer || '').trim().slice(0, 80) }
      if (!entry.name) throw new Error(u1t("Введите название"))
      for (const [field, low, high] of [['nozzleTemperature', 150, 300], ['bedTemperature', 20, 100]] as const) {
        const raw = entry[field]
        if (raw == null || String(raw).trim() === '') delete entry[field]
        else {
          const value = Number(raw)
          if (!Number.isFinite(value) || value < low || value > high) throw new Error(u1t("Температура {p0}: от {p1} до {p2} °C", { p0: field === 'nozzleTemperature' ? u1t("сопла") : u1t("стола"), p1: low, p2: high }))
          entry[field] = value
        }
      }
      const entries = [...this.entries]; const i = entries.findIndex(e => e.id === entry.id)
      if (i < 0) entries.push(entry); else entries.splice(i, 1, entry)
      await this.persist(entries, this.trash); this.draft = null
    } catch (e) { this.editError = String(e) } finally { this.busy = false }
  }
  async addHeads (presets: FilamentPreset[]) {
    if (this.busy) return
    this.busy = true
    try {
      const entries = [...this.entries]
      for (const preset of presets) {
        const p = validatePreset(preset)
        if (!entries.some(e => e.material === p.material && e.hex === p.hex)) entries.push({ ...p, id: uuid(), name: `${p.material} ${p.hex}` })
      }
      await this.persist(entries, this.trash)
    } catch (e) { this.failed = true; this.message = String(e) } finally { this.busy = false }
  }
  async remove () {
    if (!this.removing || this.busy) return
    this.busy = true
    try {
      const { entry, permanent } = this.removing
      if (permanent) await this.persist(this.entries, this.trash.filter(item => item.id !== entry.id))
      else await this.persist(this.entries.filter(item => item.id !== entry.id), [...this.trash, entry])
      this.removing = null
    }
    catch (e) { this.failed = true; this.message = String(e); this.removing = null } finally { this.busy = false }
  }
  async restore (entry: Entry) {
    this.busy = true
    try { await this.persist([...this.entries, entry], this.trash.filter(e => e.id !== entry.id)) }
    catch (e) { this.failed = true; this.message = String(e) } finally { this.busy = false }
  }
}
</script>
<style scoped>
.swatch{display:inline-block;width:26px;height:26px;vertical-align:middle;border:1px solid #999;border-radius:50%;margin-right:8px}
.catalog-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 9px 0; border-bottom: 1px solid rgba(127,127,127,.2) }
.catalog-hex { flex: 0 0 105px }
.catalog-row .swatch { flex: 0 0 26px; margin: 0 }
.catalog-row small { display: block; opacity: .78 }
.catalog-shop-button.v-btn { min-height: 42px; text-transform: none; letter-spacing: normal }
.color-draft-actions { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr); gap: 8px; padding: 8px 0 0 }
.color-draft-actions .v-btn { min-height: 42px; text-transform: none; letter-spacing: normal }
.library-dialog-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 155px), 1fr)); gap: 6px; margin-bottom: 8px }
.library-dialog-actions .v-btn { min-height: 40px; padding-inline: 5px; text-transform: none; letter-spacing: normal }
</style>
