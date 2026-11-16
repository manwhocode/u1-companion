<template>
  <div class="filament-page">
    <v-card outlined class="u1-maintenance-panel">
      <div class="hero-heading">
        <div class="companion-brand">
          <img class="companion-logo" src="../assets/u1-companion.png" alt="" width="64" height="64">
          <div>
          <h1>U1 Companion</h1>
          <p>{{ $u1t("Катушки, печать и обслуживание вашего U1.") }}</p>
          </div>
        </div>
        <div class="companion-main-menu"><u1-program-settings class="companion-settings" @gpt="openGpt">
          <template #connection>
<v-expansion-panels accordion flat class="connection-sections">
<v-expansion-panel><v-expansion-panel-header>{{ $u1t("Установщик Windows") }}</v-expansion-panel-header><v-expansion-panel-content><v-btn outlined color="primary" href="https://github.com/manwhocode/u1-companion/releases/download/windows-installer-v1.0.1/U1-Companion-Setup.exe" target="_blank" rel="noopener noreferrer">{{ $u1t("Скачать EXE") }}</v-btn><p class="mt-3"><a href="https://github.com/manwhocode/u1-companion/blob/main/desktop/README.md" target="_blank" rel="noopener noreferrer">GitHub · U1 Companion</a></p></v-expansion-panel-content></v-expansion-panel>
<v-expansion-panel><v-expansion-panel-header>{{ $u1t("Установить сертификат") }}</v-expansion-panel-header><v-expansion-panel-content><p>{{ $u1t("Он позволяет открыть дополнение через доверенный HTTPS. Это нужно для прямого сканирования QR камерой и чтения/записи NFC-меток из браузера на поддерживаемом Android.") }}</p>
        
        <h3>iPhone</h3>
        <p><a :href="certificateUrl">{{ $u1t("Скачать профиль iPhone") }}</a></p>
        <p class="mt-2">{{ $u1t("Откройте Настройки → Основные → VPN и управление устройством → загруженный профиль → Установить. Затем в разделе Основные → Об этом устройстве → Доверие сертификатам включите доверие «U1 Local Camera CA».") }}</p>
        <h3>Android</h3>
        <p><a :href="androidCertificateUrl">{{ $u1t("Скачать сертификат Android") }}</a></p>
        <p class="mt-2">{{ $u1t("Откройте Настройки → Безопасность и конфиденциальность → Шифрование и учётные данные → Установить сертификат → Сертификат CA и выберите скачанный .crt. Названия пунктов зависят от телефона. Затем откройте HTTPS в Chrome и разрешите доступ к камере. Для чтения или записи меток включите NFC.") }}</p>
        <p>{{ $u1t("Установку и доверие подтверждаете вы; сайт не может сделать это за вас. Сертификат нужен для локального HTTPS, без доступа из интернета.") }}</p>
        <p><a :href="httpsUrl">{{ $u1t("Открыть HTTPS и камеру") }}</a></p></v-expansion-panel-content></v-expansion-panel>
<v-expansion-panel><v-expansion-panel-header>{{ $u1t("Добавить ярлык") }}</v-expansion-panel-header><v-expansion-panel-content><h3>iPhone</h3>
        <p>{{ $u1t("На этой странице в Safari откройте меню страницы → «Поделиться» → «На экран “Домой”» → «Добавить».") }}</p>
        <h3>Android</h3>
        <p>{{ $u1t("В Chrome откройте меню ⋮ → «Добавить на главный экран» → «Создать ярлык» → «Добавить». В некоторых версиях пункт называется «Установить и создать ярлык».") }}</p></v-expansion-panel-content></v-expansion-panel>
<v-expansion-panel><v-expansion-panel-header>{{ $u1t("Открыть HTTPS") }}</v-expansion-panel-header><v-expansion-panel-content><p>{{ $u1t("Откройте эту же страницу по защищённому соединению после установки сертификата.") }}</p><p><a :href="samePageHttps">{{ $u1t("Перейти на HTTPS") }}</a></p></v-expansion-panel-content></v-expansion-panel>
</v-expansion-panels>
</template>
          <template #data="{ active }"><u1-data-backup v-if="active" inline @imported="reloadUserData" /></template>
          <template #calibrations="{ active }"><v-expansion-panels v-if="active" accordion flat class="connection-sections">
<v-expansion-panel><v-expansion-panel-header>{{ $u1t("Калибровки филамента") }}</v-expansion-panel-header><v-expansion-panel-content><u1-calibration inline @saved="reloadUserData" /></v-expansion-panel-content></v-expansion-panel>
<v-expansion-panel><v-expansion-panel-header>{{ $u1t("Запуск калибровки K") }}</v-expansion-panel-header><v-expansion-panel-content><u1-calibration-runner inline @finished="reloadUserData" /></v-expansion-panel-content></v-expansion-panel>
<v-expansion-panel><v-expansion-panel-header>{{ $u1t("Температуры и K") }}</v-expansion-panel-header><v-expansion-panel-content><u1-print-profiles inline /></v-expansion-panel-content></v-expansion-panel>
</v-expansion-panels></template>
        </u1-program-settings>
        <v-btn icon outlined class="main-gpt-button" :aria-label="$u1t('Открыть чат GPT')" title="GPT" :aria-expanded="gptOpen" aria-controls="companion-gpt-chat" @click="toggleGpt"><svg width="26" height="26" viewBox="0 0 48 48" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="2.8" stroke-linejoin="round"><path v-for="n in 6" :key="n" :transform="'rotate(' + ((n - 1) * 60) + ' 24 24)'" d="M24 5 C34 2 43 13 37 23 L25 30 L17 25 L17 13 L24 9 L31 13 L31 23" /></g></svg></v-btn></div>
      </div>
      <u1-calibration ref="calibrations" hide-launcher @saved="reloadUserData" /><u1-maintenance />
    </v-card>
    <v-dialog v-model="gptOpen" max-width="760" scrollable content-class="u1-dialog u1-unified-dialog"><v-card><u1-dialog-close @close="gptOpen = false" /><v-card-title>GPT</v-card-title><v-card-text><U1AI v-if="gptVisited" /></v-card-text></v-card></v-dialog>
    <u1-print-player @timer="openPauseTimer">
      <div class="maintenance-tools"><u1-scheduler /><u1-timed-pause ref="pauseTimer" /><u1-recovery /></div>
    </u1-print-player>
    <v-card outlined class="workspace-panel">
      <div class="workspace-section">
        <h2>{{ $u1t("Библиотека") }}</h2>
        <div class="library-actions">
          <u1-filament-library ref="library" class="library-controls" @error-history="openErrorHistory('color', $event)" @calibration="openCalibration('color', $event)" @select="selectLibraryPreset" @write-tag="writeTag" @read-tag="readTag(null)" @entries="colors = $event" />
          <u1-spool-inventory ref="spools" class="library-controls" @error-history="openErrorHistory('spool', $event)" @calibration="openCalibration('spool', $event)" :colors="colors" :totals="usageTotals" @inventory="spoolInventory = $event" @write-tag="writeTag" @choose="selectLibraryPreset" />
          <v-btn color="primary" @click="openCatalog">{{ $u1t("Каталог Snapmaker") }}</v-btn>
        </div>
      </div>
      <div class="workspace-section">
        <h2>{{ $u1t("Расход и печать") }}</h2>
        <div class="usage-actions-grid">
          <u1-dryer />
          <u1-print-errors ref="errors" />
          <v-btn outlined color="primary" @click="openUsageStats">{{ $u1t("Статистика расхода") }}</v-btn>
          <u1-spool-usage ref="usage" :spools="assignedSpools" @totals="usageTotals = $event" />
        </div>
      </div>
    </v-card>
    <u1-nfc ref="nfc" :lookup-remaining="lookupRemaining" @select="reviewTag" @add="addTag" />
    <div class="heads-toolbar">
      <h2>{{ $u1t("Печатные головки") }}</h2>
      <div class="hero-actions">
        <v-btn small text :disabled="busy" @click="refresh">{{ $u1t("Обновить с принтера") }}</v-btn>
        <v-btn small text :disabled="busy" @click="importHeadColors">{{ $u1t("Добавить текущие цвета в библиотеку") }}</v-btn>
      </div>
    </div>
    <v-alert v-if="message" :type="failed ? 'error' : 'info'">{{ message }}</v-alert>
    <v-row>
      <v-col v-for="(head, slot) in heads" :key="slot" cols="12" md="6">
        <v-card outlined class="head-card" :style="{ '--spool-color': validColor(head.hex) }">
          <div class="head-header">
            <span class="swatch" :style="{backgroundColor: validColor(head.hex)}" />
            <div>
              <h3>{{ $u1t("Головка") }} {{ slot + 1 }}</h3>
              <small>{{ head.loaded ? $u1t("Филамент установлен") : $u1t("Нет филамента") }} · {{ head.editable ? $u1t("Можно изменить") : $u1t("Изменение заблокировано") }}</small>
            </div>
          </div>
          <p v-if="assignedSpools[slot] && head.loaded">{{ $u1t("Привязана катушка «") }}{{ assignedSpools[slot].name }}» · {{ assignedSpools[slot].grams }} {{ $u1t("г") }}</p>
          <p>{{ assignedSpools[slot] ? savedCalibration(slot) : $u1t("Сохранённая калибровка: выберите катушку") }} {{ $u1t("(текущая") }} {{ livePressureAdvance[slot] ?? $u1t("нет данных") }})</p>
          <p v-if="selectedSpools[slot]">{{ $u1t("Выбрана катушка «") }}{{ selectedSpools[slot].name }}{{ $u1t("» · подтвердите через «Проверить и применить»") }}</p>
          <div class="head-fields">
            <v-select v-model="head.material" :items="materials" :label="$u1t('Материал')" :disabled="busy" dense outlined hide-details />
            <v-combobox v-model="head.manufacturer" :items="manufacturers" :label="$u1t('Производитель')" :disabled="busy" dense outlined hide-details />
            <v-text-field v-model="head.hex" :label="$u1t('HEX цвета')" placeholder="#39FF14" :disabled="busy" maxlength="7" dense outlined hide-details />
            <div class="color-controls">
              <label class="color-input">
              {{ $u1t("Выбрать цвет") }}
              <span class="color-picker-swatch" :style="{ backgroundColor: validColor(head.hex) }">
                <input v-model="head.hex" type="color" :disabled="busy">
              </span>
              </label>
              <v-btn small outlined class="palette-toggle" :aria-label="$u1t('Быстрые цвета · головка ') + (slot + 1)" :aria-expanded="paletteExpanded[slot]" :aria-controls="'head-palette-' + slot" @click="$set(paletteExpanded, slot, !paletteExpanded[slot])">{{ $u1t("Палитра") }}</v-btn>
            </div>
          </div>
          <div v-show="paletteExpanded[slot]" :id="'head-palette-' + slot" class="palette my-3" role="group" :aria-label="$u1t('Быстрые цвета SnapSpeed')">
            <button v-for="color in palette" :key="color.id" type="button" :title="color.name + ' · ' + color.hex"
              :aria-label="color.name + ' ' + color.hex" :aria-pressed="head.hex.toUpperCase() === color.hex"
              :style="{backgroundColor: color.hex}" :disabled="busy" @click="head.hex = color.hex" />
          </div>
          <div class="head-actions head-secondary-actions">
            <v-btn small outlined :disabled="busy" :aria-label="$u1t('NFC и QR · головка ') + (slot + 1)" :title="$u1t('NFC и QR')" @click="tagMenuSlot = slot"><v-icon>{{ qrIcon }}</v-icon></v-btn>
            <v-btn small outlined :disabled="busy" :aria-label="$u1t('Выбрать цвет · головка ') + (slot + 1)" :title="$u1t('Выбрать цвет')" @click="colorMenuSlot = slot"><v-icon>{{ paletteIcon }}</v-icon></v-btn>
            <v-btn small outlined :disabled="busy" :aria-label="$u1t('Сохранить цвет · головка ') + (slot + 1)" :title="$u1t('Сохранить цвет')" @click="saveToLibrary(slot)"><v-icon>{{ saveIcon }}</v-icon></v-btn>
            <v-btn small color="primary" :disabled="busy || !head.loaded || !head.editable" @click="review(slot)">{{ $u1t("Проверить и применить") }}</v-btn>
          </div>
        </v-card>
      </v-col>
    </v-row>
    <u1-support />
    <v-dialog :value="colorMenuSlot !== null" content-class="u1-dialog u1-unified-dialog" max-width="420" @input="!$event && (colorMenuSlot = null)">
      <v-card v-if="colorMenuSlot !== null" class="pa-4">
        <u1-dialog-close @close="colorMenuSlot = null" />
        <h2>{{ $u1t("Цвет · головка") }} {{ colorMenuSlot + 1 }}</h2>
        <div class="head-popup-actions">
          <v-btn outlined :disabled="busy" @click="chooseHeadColor('spools')">{{ $u1t("Из моих катушек") }}</v-btn>
          <v-btn outlined :disabled="busy" @click="chooseHeadColor('library')">{{ $u1t("Из библиотеки") }}</v-btn>
          <v-btn outlined color="primary" :disabled="busy" @click="chooseHeadColor('spectrum')">{{ $u1t("Из Full Spectrum") }}</v-btn>
        </div>
      </v-card>
    </v-dialog>
    <v-dialog :value="tagMenuSlot !== null" content-class="u1-dialog u1-unified-dialog" max-width="420" @input="!$event && (tagMenuSlot = null)">
      <v-card v-if="tagMenuSlot !== null" class="pa-4">
        <u1-dialog-close @close="tagMenuSlot = null" />
        <h2>{{ $u1t("NFC и QR · головка") }} {{ tagMenuSlot + 1 }}</h2>
        <div class="head-popup-actions">
          <v-btn outlined :disabled="busy" @click="chooseHeadTag('qr')">{{ $u1t("QR-этикетка и сканирование") }}</v-btn>
          <v-btn outlined :disabled="busy" @click="chooseHeadTag('read')">{{ $u1t("Считать NFC-метку") }}</v-btn>
          <v-btn outlined :disabled="busy" @click="chooseHeadTag('write')">{{ $u1t("Записать NFC-метку") }}</v-btn>
        </div>
      </v-card>
    </v-dialog>
    <v-dialog content-class="u1-dialog u1-unified-dialog" :value="pending !== null" max-width="520" persistent>
      <v-card v-if="pending" class="pa-5">
        <u1-dialog-close @close="pending = null" />
        <h2>{{ $u1t("Записать в головку") }} {{ pending.slot + 1 }}?</h2>
        <p>{{ pending.before }} → {{ pending.preset.material }} {{ pending.preset.hex }}</p>
        <p v-if="pending.name">{{ $u1t("Катушка «") }}{{ pending.name }}»</p>
        <p v-if="pending.spoolId">{{ pending.grams == null ? $u1t("Остаток филамента недоступен.") : $u1t("Остаток филамента: {p0} г", { p0: pending.grams }) }}</p>
        <p>{{ $u1t("Материал будет записан как Snapmaker / Basic — так же, как в Hub. Настройки температуры и подачи из слайсера это не меняет.") }}</p>
        <v-btn :disabled="busy" @click="pending = null">{{ $u1t("Отмена") }}</v-btn>
        <v-btn color="primary" :loading="busy" @click="apply">{{ $u1t("Сохранить на принтере") }}</v-btn>
      </v-card>
    </v-dialog>
    <v-dialog content-class="u1-dialog u1-unified-dialog" :value="qrSlot !== null" max-width="560" @input="closeQr">
      <v-card v-if="qrSlot !== null" class="pa-5">
        <u1-dialog-close @close="closeQr()" />
        <h2>{{ $u1t("QR · Головка") }} {{ qrSlot + 1 }}</h2>
        <p>{{ $u1t("Сохраните или распечатайте этикетку. Она содержит материал и HEX, работает без базы Hub.") }}</p>
        <v-combobox v-model="heads[qrSlot].manufacturer" :items="manufacturers" :label="$u1t('Производитель на этикетке')" @change="downloadQr" />
        <p>{{ $u1t("Чёрно-белая этикетка 7 × 7 см с рамкой для вырезания. QR содержит материал, цвет и производителя.") }}</p>
        <v-btn @click="downloadQr">{{ $u1t("Скачать QR PNG") }}</v-btn>
        <div v-if="labelPng" class="mt-3">
          <a :href="labelPng" :download="labelFilename">{{ $u1t("Сохранить готовую этикетку PNG") }}</a>
          <img :src="labelPng" :alt="$u1t('Готовая QR-этикетка PNG')" style="display:block;max-width:100%;margin-top:8px">
          <p>{{ $u1t("На iPhone и Android также можно удержать изображение и сохранить его через меню браузера.") }}</p>
        </div>
        <label class="d-block my-4">{{ $u1t("Сканировать фото QR") }} <input type="file" accept="image/*" capture="environment" :disabled="photoBusy" @change="scanImage"></label>
        <p role="status">{{ photoStatus }}</p>
        <v-btn v-if="photoBusy" @click="photoAbort?.abort()">{{ $u1t("Отменить сканирование") }}</v-btn>
        <v-btn v-if="cameraAvailable" class="mb-3" @click="startCamera">{{ $u1t("Сканировать камерой") }}</v-btn>
        <p v-else>{{ $u1t("На HTTP используйте фото QR: браузер не разрешает прямой доступ к камере.") }}</p>
        <div v-show="scanning" class="camera-frame"><video ref="video" class="qr-video" muted playsinline /></div>
        <p v-if="scanning" role="status">{{ cameraStatus }}</p>
        <v-btn v-if="scanning" @click="stopCamera">{{ $u1t("Остановить камеру") }}</v-btn>
        <v-textarea v-model="qrText" :label="$u1t('Или вставьте содержимое QR')" />
        <v-btn @click="importQr(qrText)">{{ $u1t("Заполнить форму") }}</v-btn>
        
      </v-card>
    </v-dialog>
    
    
  </div>
</template>

<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import { mdiQrcodeScan, mdiPaletteOutline, mdiContentSaveOutline } from '@mdi/js'
import { Component, Watch } from 'vue-property-decorator'
import QrcodeVue from 'qrcode.vue'
import QrScanner from '@/utils/reliableQrScanner'
import U1FilamentLibrary, { type Entry } from '@/components/U1FilamentLibrary.vue'
import U1Nfc from '@/components/U1Nfc.vue'
import U1SpoolInventory, { remainingGrams } from '@/components/U1SpoolInventory.vue'
import U1SpoolUsage from '@/components/U1SpoolUsage.vue'
import U1DataBackup from '@/components/U1DataBackup.vue'
import U1Calibration from '@/components/U1Calibration.vue'
import U1CalibrationRunner from '@/components/U1CalibrationRunner.vue'
import U1AI from '@/views/U1AI.vue'
import U1ProgramSettings from '@/components/U1ProgramSettings.vue'
import U1Dryer from '@/components/U1Dryer.vue'
import U1Maintenance from '@/components/U1Maintenance.vue'
import U1Scheduler from '@/components/U1Scheduler.vue'
import U1TimedPause from '@/components/U1TimedPause.vue'
import U1PrintPlayer from '@/components/U1PrintPlayer.vue'
import U1Recovery from '@/components/U1Recovery.vue'
import U1Support from '@/components/U1Support.vue'
import U1PrintErrors from '@/components/U1PrintErrors.vue'
import U1PrintProfiles from '@/components/U1PrintProfiles.vue'
import { calibrationSummary } from '@/utils/u1Calibration'
import { parseTag, type NfcPreset } from '@/utils/nfcFilament'
import { scanFilamentPhoto } from '@/utils/scanFilamentPhoto'
import { renderPlainQr } from '@/utils/plainQrLabel'
import { printPng } from '@/utils/pngPrintSize'
import { snapSpeedPalette } from '@/utils/snapmakerCatalog'
import { httpClientActions as http } from '@/api/httpClientActions'
import { assertWritable, commands, materials, validatePreset, type FilamentPreset, type TaskConfig } from '@/utils/u1Filament'

interface Status { print_stats: { state: string }; print_task_config: TaskConfig; extruder?: {pressure_advance?: number}; extruder1?: {pressure_advance?: number}; extruder2?: {pressure_advance?: number}; extruder3?: {pressure_advance?: number} }
@Component({ components: { U1Support, U1AI, QrcodeVue, U1FilamentLibrary, U1Nfc, U1SpoolInventory, U1SpoolUsage, U1DataBackup, U1Calibration, U1CalibrationRunner, U1ProgramSettings, U1PrintProfiles, U1PrintErrors, U1Dryer, U1Maintenance, U1Scheduler, U1TimedPause, U1PrintPlayer, U1Recovery } })
export default class U1Filaments extends Vue {
  gptOpen = false
  gptVisited = false
  toggleGpt () { this.gptVisited = true; this.gptOpen = !this.gptOpen }
  openGpt () { this.gptVisited = true; this.gptOpen = true }
  @Watch('$route.query.gpt', { immediate: true })
  onGptQuery () { if (this.$route.query.gpt === '1') this.openGpt() }
  qrIcon = mdiQrcodeScan
  paletteIcon = mdiPaletteOutline
  saveIcon = mdiContentSaveOutline
  colorMenuSlot: number | null = null
  tagMenuSlot: number | null = null
  chooseHeadColor (kind: 'spools' | 'library' | 'spectrum') {
    const slot = this.colorMenuSlot; this.colorMenuSlot = null
    if (slot === null) return
    if (kind === 'spools') this.openSpools(slot)
    else this.openHeadLibrary(slot, kind === 'spectrum')
  }
  chooseHeadTag (kind: 'qr' | 'read' | 'write') {
    const slot = this.tagMenuSlot; this.tagMenuSlot = null
    if (slot === null) return
    if (kind === 'qr') this.openQr(slot)
    else if (kind === 'read') this.readTag(slot)
    else this.writeTag(this.heads[slot])
  }
  materials = materials
  palette = snapSpeedPalette
  paletteExpanded = [false, false, false, false]
  heads = Array.from({ length: 4 }, () => ({ hex: '#FFFFFF', material: '', manufacturer: '', loaded: false, editable: false, liveHex: '', liveMaterial: '' }))
  spoolChoices: (NfcPreset | null)[] = [null, null, null, null]
  manufacturers = ['Snapmaker', 'Bambu Lab', 'eSUN', 'SUNLU', 'Polymaker', 'Creality', 'Elegoo', 'Anycubic']
  busy = false
  message = ''
  failed = false
  pending: { slot: number; preset: FilamentPreset; before: string; spoolId?: string; name?: string; grams?: number } | null = null
  colors: Entry[] = []
  spoolInventory: U1SpoolInventory['inventory'] | null = null
  usageTotals: Record<string, number> = {}
  livePressureAdvance: (number | null)[] = [null, null, null, null]
  openPauseTimer () { (this.$refs.pauseTimer as U1TimedPause).open() }
  openUsageStats () { (this.$refs.usage as U1SpoolUsage).openStats() }
  openErrorHistory (kind: 'spool' | 'color', value: {id: string; name: string}) { (this.$refs.errors as U1PrintErrors).openFor(kind, value.id, value.name) }
  openCalibration (kind: 'spool' | 'color', id: string) { (this.$refs.calibrations as U1Calibration).openFor(kind, id) }
  savedCalibration (slot: number) {
    const spool = this.assignedSpools[slot]
    if (!spool) return ''
    const individual = this.spoolInventory?.individualCalibration === true
    const value = individual ? spool.calibration : this.colors.find(color => color.id === spool.colorId)?.calibration
    return u1t("{p0}: {p1}", { p0: individual ? u1t("Калибровка катушки") : u1t("Общая калибровка"), p1: calibrationSummary(value) })
  }
  get selectedSpools () {
    return this.heads.map((head, slot) => {
      const choice = this.spoolChoices[slot]
      return choice && choice.material === head.material && choice.hex === head.hex?.toUpperCase() &&
        (choice.manufacturer || '') === head.manufacturer ? choice : null
    })
  }

  get assignedSpools () {
    const inventory = this.spoolInventory
    return this.heads.map((head, slot) => {
      const spool = head.loaded && inventory?.spools.find(spool =>
        spool.id === inventory.heads[slot] && spool.hex === head.liveHex && spool.material === head.liveMaterial)
      return spool ? { ...spool, grams: remainingGrams(spool, this.usageTotals) } : undefined
    })
  }
  qrSlot: number | null = null
  qrText = ''
  qrTheme = 'plain'
  labelPng = ''
  labelFilename = ''
  get httpsUrl () { return `https://${window.location.hostname}/u1-filaments-ui/#/u1-filaments` }
  get certificateUrl () { return `http://${window.location.hostname}:8081/U1-Camera.mobileconfig` }
  get androidCertificateUrl () { return `http://${window.location.hostname}:8081/u1-local-ca.crt` }
  scanning = false
  photoBusy = false
  photoStatus = ''
  photoAbort: AbortController | null = null
  scanner: QrScanner | null = null
  cameraStatus = ''
  get isHttps () { return window.location.protocol === 'https:' }
  get samePageHttps () { const url = new URL(window.location.href); url.protocol = 'https:'; url.port = ''; return url.href }
  get cameraAvailable () { return !!navigator.mediaDevices?.getUserMedia && window.isSecureContext }
  get qrPayload () { const head = this.heads[this.qrSlot ?? 0]; return 'u1filament:' + JSON.stringify({ material: head.material, hex: head.hex, ...(head.manufacturer ? { manufacturer: head.manufacturer } : {}) }) }
  async openQr (slot: number) { this.qrSlot = slot; this.labelPng = ''; this.photoStatus = ''; await this.$nextTick(); await this.downloadQr() }
  async mounted () { window.addEventListener('u1-open-gpt', this.openGpt); await this.refresh(); this.onNfcRoute() }
  @Watch('$route.fullPath')
  onNfcRoute () {
    if (this.$route.query.tag !== '1') return
    const { tag, m, c, n, b, s, ...query } = this.$route.query
    const raw = window.location.href
    this.$router.replace({ path: this.$route.path, query }).catch(() => {})
    ;(this.$refs.nfc as U1Nfc).accept(raw, true)
  }
  writeTag (preset: NfcPreset) { (this.$refs.nfc as U1Nfc).writePreset(preset) }
  readTag (slot: number | null) { (this.$refs.nfc as U1Nfc).readPreset(slot) }
  async lookupRemaining (id: string) {
    const inventory = this.$refs.spools as U1SpoolInventory
    const spool = await inventory.findSpool(id)
    return spool ? inventory.readRemainingGrams(spool) : null
  }
  openSpools (slot: number) { (this.$refs.spools as U1SpoolInventory).open('spools', slot) }
  reviewTag ({ slot, preset }: { slot: number; preset: NfcPreset }) { this.review(slot, preset) }
  addTag (preset: NfcPreset) { (this.$refs.library as U1FilamentLibrary).addFromTag(preset) }
  beforeDestroy () { window.removeEventListener('u1-open-gpt', this.openGpt); this.closeQr() }
  validColor (hex: string) { return /^#[0-9a-f]{6}$/i.test(hex) ? hex : '#808080' }
  selectLibraryPreset ({ slot, preset }: { slot: number; preset: NfcPreset }) {
    if (this.busy) return
    try {
      const color = validatePreset(preset)
      Object.assign(this.heads[slot], { ...color, manufacturer: color.manufacturer || '' })
      this.$set(this.spoolChoices, slot, preset.spoolId ? { ...color, name: preset.name, spoolId: preset.spoolId } : null)
      this.failed = false; this.message = u1t("Цвет выбран для головки {p0}. Для записи нажмите «Проверить и применить».", { p0: slot + 1 })
    } catch (e) { this.error(e) }
  }
  saveToLibrary (slot: number) {
    try { (this.$refs.library as U1FilamentLibrary).addFromHead(this.heads[slot], slot) } catch (e) { this.error(e) }
  }
  importHeadColors () { (this.$refs.library as U1FilamentLibrary).addHeads(this.heads.filter(h => h.loaded)) }
  openHeadLibrary (slot: number, fullSpectrumOnly = false) { (this.$refs.library as U1FilamentLibrary).openForHead(slot, fullSpectrumOnly) }
  openCatalog () { (this.$refs.library as U1FilamentLibrary).openCatalog() }
  async reloadUserData () {
    await Promise.all([
      (this.$refs.library as U1FilamentLibrary).load(),
      (this.$refs.spools as U1SpoolInventory).load(),
      (this.$refs.usage as U1SpoolUsage).loadUsage()
    ])
    await this.refresh()
  }
  error (e: unknown) { this.failed = true; this.message = e instanceof Error ? e.message : String(e) }
  async status (): Promise<Status> {
    const r = await http.get<{result: {status: Status}}>('/printer/objects/query?print_stats&print_task_config&extruder&extruder1&extruder2&extruder3')
    return r.data.result.status
  }
  async refresh () {
    this.busy = true
    try {
      const st = await this.status()
      this.livePressureAdvance = [st.extruder, st.extruder1, st.extruder2, st.extruder3].map(extruder => typeof extruder?.pressure_advance === 'number' ? extruder.pressure_advance : null)
      const t = st.print_task_config
      this.spoolChoices = [null, null, null, null]
      this.heads = this.heads.map((head, i) => {
        const hex = '#' + (t.filament_color_rgba?.[i] || 'FFFFFF').slice(0, 6).toUpperCase()
        const material = t.filament_type?.[i] || ''
        return { hex, material, manufacturer: head.manufacturer || '', loaded: t.filament_exist?.[i] === true, editable: t.filament_edit?.[i] === true, liveHex: hex, liveMaterial: material }
      })
    } catch (e) { this.error(e) } finally { this.busy = false }
  }
  async review (slot: number, tag?: NfcPreset) {
    if (this.busy || this.pending) return
    this.busy = true; this.message = ''
    try {
      const input: NfcPreset = tag || this.selectedSpools[slot] || this.heads[slot]
      const { spoolId } = input
      const inventory = this.$refs.spools as U1SpoolInventory
      const spool = spoolId ? await inventory.findSpool(spoolId) : undefined
      if (spoolId && !spool) throw new Error(u1t("Катушка отсутствует в «Моих катушках»"))
      if (!tag && spool && (spool.material !== input.material || spool.hex !== input.hex ||
          (spool.manufacturer || '') !== (input.manufacturer || ''))) {
        throw new Error(u1t("Данные катушки изменились. Выберите её снова."))
      }
      const preset = validatePreset(spool || input)
      const grams = spool ? await inventory.readRemainingGrams(spool).catch(() => undefined) : undefined
      const st = await this.status()
      assertWritable(slot, st.print_stats.state, st.print_task_config)
      this.pending = { slot, preset, spoolId: spool?.id, name: spool?.name || tag?.name, grams, before: `${st.print_task_config.filament_type[slot]} #${st.print_task_config.filament_color_rgba[slot].slice(0, 6)}` }
    } catch (e) { this.error(e) } finally { this.busy = false }
  }
  async apply () {
    if (!this.pending || this.busy) return
    const { slot, preset, spoolId } = this.pending
    this.busy = true
    try {
      const inventory = this.$refs.spools as U1SpoolInventory
      if (spoolId) {
        const spool = await inventory.findSpool(spoolId)
        if (!spool || spool.material !== preset.material || spool.hex !== preset.hex) {
          throw new Error(u1t("Данные катушки изменились. Выберите её снова."))
        }
      }
      const before = await this.status()
      assertWritable(slot, before.print_stats.state, before.print_task_config)
      // Export a recovery record before every write. Storage failure aborts the operation.
      const history = JSON.parse(localStorage.getItem('u1-filament-backups') || '[]') as unknown[]
      if (!Array.isArray(history)) throw new Error(u1t("Повреждён журнал резервных копий"))
      history.push({ time: new Date().toISOString(), printer: this.$typedState.config.apiUrl, slot, before })
      localStorage.setItem('u1-filament-backups', JSON.stringify(history))
      const scripts = commands(slot, preset)
      // A color-only change must preserve the existing SnapSpeed/subtype metadata.
      if (before.print_task_config.filament_type[slot] === preset.material && before.print_task_config.filament_vendor[slot] !== 'NONE') scripts.shift()
      for (const script of scripts) {
        const live = await this.status()
        assertWritable(slot, live.print_stats.state, live.print_task_config)
        await http.post('/printer/gcode/script', { script })
      }
      const after = (await this.status()).print_task_config
      if (after.filament_color_rgba[slot].toUpperCase() !== preset.hex.slice(1) + 'FF' || after.filament_type[slot] !== preset.material || after.filament_vendor[slot] === 'NONE') throw new Error(u1t("Принтер не подтвердил все данные. Возможна частичная запись — обновите состояние и проверьте экран U1."))
      this.heads[slot].manufacturer = preset.manufacturer || ''
      try { await inventory.assign(slot, spoolId || null) }
      catch (e) { throw new Error(u1t("Принтер подтвердил материал и цвет, но привязка катушки не сохранена. {p0}", { p0: String(e) })) }
      this.failed = false; this.message = u1t("Головка {p0}: {p1} {p2} — подтверждено принтером", { p0: slot + 1, p1: preset.material, p2: preset.hex })
    } catch (e) { this.error(e) } finally { this.pending = null; this.busy = false; await this.refresh() }
  }
  importQr (raw: string) {
    try {
      const preset = parseTag(raw)
      if (this.qrSlot === null) return
      const { spoolId, name, ...color } = preset
      this.$set(this.spoolChoices, this.qrSlot, spoolId ? { ...color, name, spoolId } : null)
      Object.assign(this.heads[this.qrSlot], color)
      this.closeQr(); this.failed = false; this.message = u1t("QR прочитан. Проверьте материал и цвет, затем нажмите «Проверить и применить».")
    } catch (e) { this.photoStatus = e instanceof Error ? e.message : String(e); this.error(e) }
  }
  async downloadQr () {
    if (this.photoBusy) return
    const head = this.heads[this.qrSlot ?? 0]
    const payload = this.qrPayload
    const slot = this.qrSlot
    this.photoBusy = true; this.photoStatus = u1t("Создаю и проверяю этикетку…")
    try {
      const label = await renderPlainQr(payload, `${head.material} ${head.hex}`, head.manufacturer)
      const decoded = await QrScanner.scanImage(label, { returnDetailedScanResult: true })
      if (decoded.data !== payload) throw new Error(u1t("Этикетка не прошла проверку чтения."))
      this.labelPng = printPng(label)
      this.labelFilename = `U1-${head.material}-${head.hex.slice(1)}-70mm.png`
      this.photoStatus = u1t("QR проверен. Нажмите «Сохранить готовую этикетку PNG». Печатайте размером 7 × 7 см.")
    } catch (e) { this.photoStatus = String(e) } finally {
      this.photoBusy = false
      if (slot !== null && this.qrSlot === slot && this.qrPayload !== payload) this.downloadQr()
    }
  }
  async scanImage (event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0]
    if (!file) return
    this.photoBusy = true
    this.photoAbort?.abort()
    const controller = new AbortController()
    this.photoAbort = controller
    const started = performance.now()
    const slot = this.qrSlot
    try {
      const result = await scanFilamentPhoto(file, text => { this.photoStatus = text }, controller.signal)
      if (controller.signal.aborted || this.qrSlot !== slot) return
      this.importQr(result)
      this.message += u1t(" ({p0} с)", { p0: ((performance.now() - started) / 1000).toFixed(1) })
      this.photoStatus = ''
    } catch (e) {
      this.photoStatus = e instanceof Error ? e.message : String(e)
    } finally { this.photoBusy = false; this.photoAbort = null }
    ;(event.target as HTMLInputElement).value = ''
  }
  async startCamera () {
    try {
      this.scanner?.destroy()
      this.scanning = true
      await this.$nextTick()
      this.cameraStatus = u1t("Запускаю заднюю камеру…")
      this.scanner = new QrScanner(this.$refs.video as HTMLVideoElement, result => {
        try { parseTag(result.data); this.importQr(result.data) }
        catch (e) { this.cameraStatus = e instanceof Error ? e.message : String(e) }
      }, {
        returnDetailedScanResult: true,
        preferredCamera: 'environment',
        maxScansPerSecond: 8,
        highlightScanRegion: true,
        highlightCodeOutline: true,
        calculateScanRegion: video => {
          const w = video.videoWidth || 1280; const h = video.videoHeight || 720
          const scale = Math.min(1, 960 / Math.max(w, h))
          return { x: 0, y: 0, width: w, height: h, downScaledWidth: Math.round(w * scale), downScaledHeight: Math.round(h * scale) }
        },
        onDecodeError: error => {
          if (String(error).includes('No QR code found')) return
          this.cameraStatus = u1t("Ошибка декодера: ") + String(error)
        }
      })
      this.scanner.setInversionMode('both')
      await this.scanner.start()
      this.cameraStatus = u1t("Камера работает. Поместите весь QR с белыми полями в кадр и держите неподвижно.")
    } catch (e) { this.stopCamera(); this.photoStatus = e instanceof Error ? e.message : String(e) }
  }
  stopCamera () { this.scanner?.destroy(); this.scanner = null; this.scanning = false }
  closeQr () { this.photoAbort?.abort(); this.scanner?.destroy(); this.scanner = null; this.scanning = false; this.qrSlot = null; this.qrText = ''; this.labelPng = '' }
}
</script>

<style scoped>
.u1-maintenance-panel { padding:12px; margin-bottom:12px; border-radius:16px }
.maintenance-tools { display:flex; flex-wrap:wrap; gap:6px }
.maintenance-tools > div { margin-bottom:0 !important }
.u1-maintenance-panel >>> .v-alert { overflow-wrap:anywhere }
.u1-maintenance-panel >>> .v-btn { max-width:100%; height:auto; min-height:32px; white-space:normal }
.u1-maintenance-panel >>> .v-btn__content { white-space:normal; line-height:1.25 }

.filament-page { max-width: 1380px; margin: 0 auto; padding: 0 0 20px }

.companion-main-menu { display:flex;align-items:center;gap:8px;flex-wrap:wrap }
.main-gpt-button { width:40px;height:40px;min-height:40px;border-radius:6px }
.companion-gpt-panel { padding:14px;margin-bottom:16px;min-width:0 }
.gpt-collapse { display:flex;justify-content:flex-end;margin-bottom:10px }
.companion-brand { display:flex;align-items:center;gap:12px;min-width:0 }.companion-logo { flex:0 0 auto;object-fit:contain;width:64px;height:64px } @media(max-width:600px) { .companion-logo { width:48px;height:48px }.companion-brand { gap:8px } }
.hero-heading { display:flex; justify-content:space-between; align-items:center; gap:12px; min-width:0; margin-bottom:12px }
.hero-heading h1 { font-size:clamp(1.5rem,4vw,2rem); line-height:1.15; margin:0 0 4px }
.hero-heading p { margin:0; font-size:.9rem }
.companion-settings { flex:0 0 auto }
.companion-actions { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr)); gap:8px; width:100% }
.companion-actions > div { min-width:0 }
.companion-actions >>> .v-btn { width:100%; height:44px !important; min-width:0; padding:6px 12px; border-radius:8px; letter-spacing:.025em; white-space:normal }
.companion-actions >>> .v-btn__content { flex-shrink:1; white-space:normal; line-height:1.2; text-align:center }
@media (max-width:600px) {
  .hero-heading { flex-wrap:wrap; gap:10px }
  .companion-settings { width:auto }
  .companion-actions { grid-template-columns:repeat(2,minmax(0,1fr)); gap:6px }
  .companion-actions >>> .v-btn { font-size:11px; height:52px !important; padding-inline:6px; letter-spacing:0; text-transform:none }
}

.hero-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 6px }
.head-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px }
.head-actions .v-btn { width:100%; min-width:0; height:40px !important; margin:0; padding:4px 6px; border-radius:4px; font-size:14px; font-weight:600; letter-spacing:.01em; text-transform:none }
.head-actions .v-btn >>> .v-btn__content { flex-shrink:1; white-space:normal; text-align:center; line-height:1.2 }
.head-actions.head-secondary-actions { grid-template-columns:40px 40px 40px minmax(0,1fr) }
.head-popup-actions { display:grid; gap:8px; margin-top:14px }
.head-popup-actions .v-btn { width:100%; min-height:44px; white-space:normal; text-transform:none; letter-spacing:.01em }
.workspace-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); border-radius: 16px; margin-bottom: 18px }
.usage-heading { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:8px }
.usage-heading h2 { margin-bottom:0 !important; min-width:0 }
.usage-heading .v-btn { margin:0; max-width:55%; height:auto; min-height:32px; padding:6px 8px; letter-spacing:.01em }
.usage-heading .v-btn >>> .v-btn__content { white-space:normal; flex-shrink:1; line-height:1.2; text-align:center }
@media (max-width:600px) { .usage-heading .v-btn { font-size:11px } }
.workspace-section { padding: 12px 12px 0 }
.library-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 160px), 1fr)); gap: 6px; margin-bottom: 12px }
.library-controls { display: contents }
.workspace-section h2, .heads-toolbar h2 { font-size: 1.13rem; margin-bottom: 8px }
.heads-toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 6px; margin-bottom: 6px }
.heads-toolbar h2 { margin: 0 }
.head-card { height: 100%; padding: 12px; border-radius: 16px; border-top: 3px solid var(--spool-color) }
.head-card p { margin-bottom:6px; font-size:.875rem; line-height:1.35 }
.head-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px }
.head-header h3 { font-size: 1.2rem; margin: 0 }
.head-header small { opacity: .78 }
.swatch { width: 36px; height: 36px; flex: 0 0 36px; border: 1px solid #999; border-radius: 50% }
.head-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; margin-top:8px }
.color-input { display: flex; align-items: center; gap: 8px; font-size: .85rem }
.color-controls { display:flex; align-items:center; gap:8px; min-width:0 }
.palette-toggle { height:34px !important; min-width:0 !important; padding:0 10px !important; font-size:11px; letter-spacing:0; text-transform:none }
.head-fields + .palette + .head-actions { margin-top:8px }
.color-picker-swatch { position: relative; width: 32px; height: 32px; flex: 0 0 32px; border: 1px solid #999; border-radius: 50% }
.color-picker-swatch:focus-within { outline: 2px solid currentColor; outline-offset: 3px }
.color-picker-swatch input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer }
.tags { margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(127,127,127,.22) }
.palette { display:flex; gap:6px; flex-wrap:wrap; margin-block:8px !important }
.palette button { width:26px; height:26px; border:1px solid #999; border-radius:50% }
.palette button[aria-pressed="true"] { outline: 2px solid currentColor; outline-offset: 2px }
@media (max-width: 480px) {
  .head-fields { grid-template-columns: 1fr }
  .workspace-section { padding-inline: 10px }
  .head-card { padding: 10px }
  .head-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)) }
  .head-actions .v-btn { padding-inline:4px; font-size:11px }
}
.qr-label { background:white; color:black; padding:16px; text-align:center; width:fit-content; max-width:100%; margin:16px auto; display:flex; align-items:center; justify-content:center; flex-wrap:wrap }
.qr-quiet { padding:32px; background:white }
.camera-frame { position:relative; width:100%; overflow:hidden }
.qr-video { display:block; width:100%; max-height:420px; object-fit:contain }
</style>

<style>
.usage-actions-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; margin-bottom:12px }
.usage-actions-grid > div { display:contents }
.usage-actions-grid .v-alert { grid-column:1 / -1 }
.usage-actions-grid .v-btn { width:100%; min-width:0; height:44px !important; margin:0 !important; padding:6px 8px !important; border-radius:4px; letter-spacing:.01em; text-transform:none; font-size:14px; font-weight:500 }
.usage-actions-grid .v-btn .v-btn__content { white-space:normal; flex-shrink:1; line-height:1.2; text-align:center }
@media(max-width:600px) { .usage-actions-grid .v-btn { font-size:12px } }
.u1-dialog input[type="file"] { display:block; max-width:100%; margin-top:8px; font-size:14px; color:inherit }
.u1-dialog input[type="file"]::file-selector-button { background:#36363c; color:#fff; border:1px solid #929298; border-radius:8px; padding:10px 14px; margin-right:10px; font:inherit; font-weight:600; cursor:pointer }
.u1-dialog input[type="file"]:focus-visible { outline:2px solid var(--v-primary-base); outline-offset:3px }
.u1-dialog input[type="file"]:disabled::file-selector-button { opacity:.5; cursor:default }
.library-actions .v-btn { padding-inline: 8px; letter-spacing: .01em; text-transform: none; touch-action: manipulation }
@media (max-width: 480px) {
  .head-actions .v-btn__content { flex-shrink: 1; white-space: normal; text-align: center; line-height: 1.2 }
}
.u1-spool-color-menu .v-list-item__title { white-space: normal; font-size: .875rem; line-height: 1.3 }
.u1-spool-color-menu .spool-swatch { flex-shrink: 0 }

@media (max-width: 600px) {
  .v-dialog.u1-dialog:not(.v-dialog--fullscreen) { margin: 5px; max-height: calc(100% - 10px); font-size: .875rem; touch-action: manipulation }
  .u1-dialog > .v-card.pa-4,
  .u1-dialog > .v-card.pa-5 { padding: 5px !important }
  .u1-dialog > .v-card > .v-card__title { padding: 8px 5px; font-size: 1.1rem; line-height: 1.35 }
  .u1-dialog > .v-card > .v-card__text { padding: 0 5px 8px; line-height: 1.4 }
  .u1-dialog > .v-card > .v-card__actions { padding: 6px 5px }
  .u1-dialog h2 { font-size: 1.15rem; line-height: 1.3; margin-bottom: 6px }
  .u1-dialog p { margin-bottom: 8px }
  .u1-dialog input,
  .u1-dialog textarea,
  .filament-page .v-input input,
  .filament-page .v-input textarea { font-size: 16px }
  .u1-dialog .v-select__selection,
  .u1-dialog .v-input .v-label { font-size: .875rem }
  .u1-dialog .v-expansion-panel-header { padding: 8px 10px; min-height: 40px; font-size: .875rem }
  .u1-dialog .v-expansion-panel-content__wrap { padding: 0 6px 8px }
  .u1-spool-color-menu .v-list-item { min-height: 40px; padding-inline: 8px }
  .u1-spool-color-menu .v-list-item__content { padding-block: 6px }
}
</style>


<style scoped>
.gpt-collapse >>> .u1-close-button { width:96px;min-width:96px;height:36px;font-size:12px }.companion-main-menu { flex-wrap:nowrap }
@media(min-width:701px) { .head-secondary-actions .v-btn:last-child { font-size:15px } }
</style>

<style scoped>
.companion-gpt-panel { max-width:900px;margin:0 auto 12px;padding:8px }.gpt-collapse { margin-bottom:0;height:36px }.companion-gpt-panel >>> .ai-header { margin-top:-30px;margin-right:105px;min-height:30px }
</style>

<style scoped>.main-gpt-button { width:44px !important;height:44px !important;min-width:44px !important;min-height:44px !important;border-radius:6px }</style>

<style scoped>.connection-sections >>> .v-expansion-panel { border-bottom:1px solid #8885 }.connection-sections >>> .v-expansion-panel-header { min-height:44px;font-size:14px;padding:10px 6px }</style>
