<template>
<div>
  <v-btn v-if="!inline && !hideLauncher" small outlined @click="open">{{ $u1t("Данные и резервные копии") }}</v-btn>
  <u1-settings-content :inline="inline" v-model="opened" content-class="u1-dialog u1-unified-dialog" max-width="650" scrollable>
    <v-card :flat="inline">
      <u1-dialog-close v-if="!inline" @close="opened = false" />
      <v-card-title>{{ $u1t("Данные и резервные копии") }}</v-card-title>
      <v-card-text>
        <v-alert v-if="message" dense :type="failed ? 'error' : 'info'">{{ message }}</v-alert>
        <p>{{ $u1t("Цвета, катушки, корзины, расход и история ошибок сохраняются на U1. Экспортируйте копию на телефон или ПК перед обновлением прошивки.") }}</p>
        <v-select v-model="exportScope" :items="scopes" :label="$u1t('Что экспортировать')" outlined dense :disabled="!!busy" @change="clearExport" />
        <div class="backup-actions">
          <v-btn outlined :loading="busy === 'export'" :disabled="!!busy" @click="exportData">{{ $u1t("Экспортировать JSON") }}</v-btn>
          <v-btn outlined :disabled="!!busy || !exported" @click="share">{{ $u1t("Поделиться файлом") }}</v-btn>
        </div>
        <a v-if="downloadUrl" :href="downloadUrl" :download="downloadName">{{ $u1t("Скачать подготовленный JSON") }}</a>
        <v-alert v-if="shareHelp" outlined type="info" class="mt-3">
          <p>{{ shareHelp }}</p>
          <p><strong>iPhone:</strong> {{ $u1t("скачайте файл, откройте «Файлы → Загрузки», удерживайте файл и выберите «Поделиться».") }}</p>
          <p><strong>Android:</strong> {{ $u1t("скачайте файл, откройте «Файлы → Загрузки», выберите файл и нажмите «Поделиться».") }}</p>
          <a v-if="downloadUrl" :href="downloadUrl" :download="downloadName">{{ $u1t("Скачать файл для отправки") }}</a>
          <v-btn v-if="!secureContext" small outlined class="mt-3" :href="httpsUrl" target="_blank" rel="noopener">{{ $u1t("Открыть HTTPS") }}</v-btn>
          <p v-if="!secureContext" class="mt-2 mb-0">{{ $u1t("Для системной отправки из браузера нужен доверенный сертификат. В HTTPS-вкладке подготовьте экспорт заново.") }}</p>
        </v-alert>
        <v-divider class="my-3" />
        <h3>{{ $u1t("Импорт") }}</h3>
        <label class="d-block my-2">{{ $u1t("Выбрать файл данных (.json или .json.txt)") }} <input ref="file" type="file" accept="application/json,text/plain,.json,.txt" :disabled="!!busy" @change="readFile"></label>
        <p v-if="sourceName">{{ sourceName }}</p>
        <v-select v-model="importScope" :items="scopes" :label="$u1t('Что импортировать из файла')" outlined dense :disabled="!!busy || !imported" @change="preview = null" />
        <p>{{ $u1t("При частичном импорте расход, история и остальные разделы сохраняются. Файл катушек содержит их текущий остаток и связанные цвета/типы пустых катушек; недостающие справочники будут добавлены. Привязки к головкам из другого принтера не переносятся.") }}</p>
        <v-radio-group v-model="mode" :disabled="!!busy" hide-details class="my-2" @change="preview = null">
          <v-radio value="merge" :label="$u1t('Объединить с текущими данными')" />
          <v-radio value="replace" :label="importScope === 'full' ? $u1t('Восстановить данные из файла') : $u1t('Заменить выбранный раздел')" />
        </v-radio-group>
        <p>{{ mode === 'merge' ? $u1t("При совпадении ID сохраняются текущие карточки и привязки. Расход объединяется без повторного сложения одинаковых заданий.") : (importScope === 'full' ? $u1t("Полный бэкап заменит цвета, катушки, корзины, расход и привязки головок. Для частичного файла изменится только его раздел.") : $u1t("Будет заменён только выбранный раздел. Используемые катушками цвета и типы пустых катушек сохранятся.")) + $u1t(" Перед записью создаётся бэкап.") }}</p>
        <p>{{ $u1t("Наработка и подтверждения обслуживания объединяются без повторного сложения заданий. Старый файл без этих данных не сбрасывает текущие счётчики.") }}</p>
        <v-btn outlined :disabled="!!busy || !imported" :loading="busy === 'preview'" @click="makePreview">{{ $u1t("Предварительный просмотр") }}</v-btn>
        <template v-if="preview">
          <p><strong>{{ $u1t("Импорт:") }} {{ scopeName(preview.scope || 'full') }}</strong></p>
          <v-simple-table dense class="my-3">
            <thead><tr><th>{{ $u1t("Данные") }}</th><th>{{ $u1t("Сейчас") }}</th><th>{{ $u1t("После импорта") }}</th></tr></thead>
            <tbody><tr v-for="row in summaryFields" :key="row.key"><td>{{ row.label }}</td><td>{{ preview.before[row.key] }}</td><td>{{ preview.after[row.key] }}</td></tr></tbody>
          </v-simple-table>
          <p v-if="preview.conflicts">{{ $u1t("Различающихся записей с одинаковыми ID —") }} {{ preview.conflicts }}{{ $u1t(". Сохранены текущие значения.") }}</p>
          <v-btn block color="primary" :disabled="!!busy" :loading="busy === 'import'" @click="applyImport">{{ $u1t("Подтвердить импорт") }}</v-btn>
        </template>
        <v-divider class="my-3" />
        <h3>{{ $u1t("Копии на принтере") }}</h3>
        <p>{{ $u1t("Копии хранятся в пользовательском разделе. Для защиты от потери устройства скачайте JSON за его пределы.") }}</p>
        <v-btn small outlined :disabled="!!busy" @click="loadBackups">{{ $u1t("Обновить список копий") }}</v-btn>
        <v-select v-model="backupName" :items="backups" :label="$u1t('Резервная копия')" :disabled="!!busy" dense />
        <v-btn small outlined :disabled="!!busy || !backupName" @click="loadBackup">{{ $u1t("Выбрать для просмотра") }}</v-btn>
      </v-card-text>
      
    </v-card>
  </u1-settings-content>
</div>
</template>

<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import U1SettingsContent from './U1SettingsContent.vue'
import { Component, Prop } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'

interface ExportFile { format: string; version: number; createdAt: string; data: unknown }
type Summary = Record<string, number>
interface Preview { scope?: string; previewId: string; mode: string; before: Summary; after: Summary; conflicts: number }

@Component({components:{U1SettingsContent}})
export default class U1DataBackup extends Vue {
  @Prop({default:false,type:Boolean}) readonly inline!: boolean
  @Prop({default:false,type:Boolean}) readonly hideLauncher!: boolean
  mounted () { if (this.inline) this.open() }
  opened = false
  busy = ''
  message = ''
  failed = false
  mode = 'merge'
  exportScope = 'full'
  importScope = 'full'
  get scopes () { return [{ value: 'full', text: u1t("Всё вместе (полный бэкап)") }, { value: 'colors', text: u1t("Только мои цвета") }, { value: 'spools', text: u1t("Только мои катушки") }, { value: 'cores', text: u1t("Только пустые катушки") }] }
  scopeName (scope: string) { return this.scopes.find(item => item.value === scope)?.text || scope }
  clearExport () { if (this.downloadUrl) URL.revokeObjectURL(this.downloadUrl); this.downloadUrl = ''; this.exported = null; this.shareHelp = ''; this.message = '' }
  imported: unknown = null
  sourceName = ''
  preview: Preview | null = null
  exported: ExportFile | null = null
  downloadUrl = ''
  downloadName = ''
  shareHelp = ''
  secureContext = window.isSecureContext
  get httpsUrl () { const url = new URL(window.location.href); url.protocol = 'https:'; if (url.port === '80') url.port = ''; return url.href }
  backups: string[] = []
  backupName = ''
  get summaryFields () { return [
    { key: 'colors', label: u1t("Цвета") }, { key: 'colorTrash', label: u1t("Корзина цветов") },
    { key: 'spools', label: u1t("Мои катушки") }, { key: 'spoolTrash', label: u1t("Корзина катушек") },
    { key: 'cores', label: u1t("Пустые катушки") }, { key: 'records', label: u1t("Задания в истории") },
    { key: 'spentGrams', label: u1t("Общий расход, г") }, { key: 'errors', label: u1t("Сообщения об ошибках печати") },
    { key: 'activeHours', label: u1t("Наработка, ч") }, { key: 'maintenanceEvents', label: u1t("Подтверждения обслуживания") }
  ] }

  open () { this.opened = true }
  setMessage (value: unknown, failed = false) { this.failed = failed; this.message = value instanceof Error ? value.message : String(value) }
  beforeDestroy () { if (this.downloadUrl) URL.revokeObjectURL(this.downloadUrl) }
  prepareDownload (document: ExportFile, filename: string) {
    if (this.downloadUrl) URL.revokeObjectURL(this.downloadUrl)
    this.exported = document
    this.shareHelp = ''
    this.downloadName = filename
    this.downloadUrl = URL.createObjectURL(new Blob([JSON.stringify(document, null, 2)], { type: 'application/json' }))
  }

  async exportData () {
    this.busy = 'export'
    try {
      const result = await u1DataRequest<{document: ExportFile; filename: string}>('export', { scope: this.exportScope })
      this.prepareDownload(result.document, result.filename)
      this.setMessage(u1t("Экспорт готов. Скачайте JSON или отправьте его через «Поделиться файлом»."))
    } catch (error) { this.setMessage(error, true) } finally { this.busy = '' }
  }

  async share () {
    if (!this.exported) return
    this.shareHelp = ''
    if (!this.secureContext || typeof navigator.share !== 'function' || typeof navigator.canShare !== 'function') {
      this.shareHelp = !this.secureContext ? u1t("Страница открыта по HTTP: браузер не разрешает системное меню отправки. Файл можно отправить через загрузки телефона.") : u1t("Этот браузер не поддерживает отправку файлов. Используйте загрузки телефона.")
      return
    }
    try {
      const contents = JSON.stringify(this.exported, null, 2)
      const candidates = [
        new File([contents], this.downloadName, { type: 'application/json' }),
        new File([contents], this.downloadName + '.txt', { type: 'text/plain' })
      ]
      const file = candidates.find(candidate => navigator.canShare({ files: [candidate] }))
      if (!file) { this.shareHelp = u1t("Браузер не разрешает отправку этого файла. Скачайте JSON и отправьте его через загрузки телефона."); return }
      // Keep the native call within this click: awaiting an export here loses user activation.
      await navigator.share({ files: [file], title: u1t("Данные филаментов U1") })
      this.setMessage(u1t("Файл передан в системное меню отправки. Вариант .json.txt содержит те же данные и подходит для импорта."))
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        this.shareHelp = u1t("Браузер не смог отправить файл. Скачайте JSON и отправьте его через загрузки телефона.")
      }
    }
  }

  async readFile (event: Event) {
    this.preview = null
    this.imported = null
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    this.sourceName = file.name
    try {
      if (file.size > 8 * 1024 * 1024) throw new Error(u1t("Файл превышает 8 МБ."))
      this.imported = JSON.parse((await file.text()).replace(/^\uFEFF/, ''))
      const scope = (this.imported as {scope?: string})?.scope
      this.importScope = scope && this.scopes.some(item => item.value === scope) ? scope : 'full'
      this.setMessage(u1t("Файл выбран. Запустите предварительный просмотр для проверки."))
    } catch (error) { this.setMessage(error, true) }
    input.value = ''
  }

  async makePreview () {
    this.preview = null
    this.busy = 'preview'
    try {
      this.preview = await u1DataRequest<Preview>('preview', { document: this.imported, mode: this.mode, scope: this.importScope })
      this.setMessage(u1t("Файл проверен. Импорт доступен на свободном принтере."))
    } catch (error) { this.setMessage(error, true) } finally { this.busy = '' }
  }

  async applyImport () {
    if (!this.preview) return
    this.busy = 'import'
    try {
      const result = await u1DataRequest<{backup: string}>('import', { previewId: this.preview.previewId })
      this.preview = null
      this.setMessage(u1t("Импорт завершён. Предыдущие данные сохранены в копии ") + result.backup)
      this.$emit('imported')
    } catch (error) { this.preview = null; this.setMessage(error, true) } finally { this.busy = '' }
  }

  async loadBackups () {
    this.busy = 'backups'
    try {
      const result = await u1DataRequest<{backups: string[]; current: boolean}>('backups')
      this.backups = result.current ? ['current.json', ...result.backups] : result.backups
      this.setMessage(u1t("Список резервных копий обновлён."))
    } catch (error) { this.setMessage(error, true) } finally { this.busy = '' }
  }

  async loadBackup () {
    this.busy = 'backup'
    try {
      const result = await u1DataRequest<{document: ExportFile}>('load_backup', { name: this.backupName })
      this.imported = result.document
      this.sourceName = this.backupName
      this.preview = null
      this.prepareDownload(result.document, this.backupName)
      this.setMessage(u1t("Копия выбрана. Запустите предварительный просмотр для проверки восстановления."))
    } catch (error) { this.setMessage(error, true) } finally { this.busy = '' }
  }
}
</script>

<style scoped>
.backup-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr)); gap: 6px; margin-bottom: 8px }
.backup-actions .v-btn { text-transform: none; letter-spacing: normal }
</style>
