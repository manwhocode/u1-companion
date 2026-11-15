<template>
<div class="u1-log-tools mb-3">
  <div class="log-actions"><v-btn small outlined :disabled="busy" @click="download('json')">{{ $u1t("Экспорт JSON") }}</v-btn><v-btn small outlined :disabled="busy" @click="download('csv')">{{ $u1t("Экспорт CSV") }}</v-btn><v-btn small outlined :disabled="busy" @click="prepare">{{ $u1t("Очистить список") }}</v-btn></div>
  <v-checkbox v-model="archive" dense hide-details :label="$u1t('Показать архив')" @change="$emit('archive', archive)" />
  <p class="text-caption mt-1 mb-0">{{ $u1t("Очистка переносит записи в архив. Остатки катушек, общий расход и статистика сохраняются.") }}</p>
  <v-alert v-if="error" dense type="error" dismissible class="mt-2" @input="error = ''">{{ error }}</v-alert>
  <p v-if="notice" role="status" class="mt-2 mb-0">{{ notice }}</p>
  <v-btn v-if="downloadUrl" small outlined class="mt-2" :href="downloadUrl" :download="downloadName">{{ $u1t("Скачать подготовленный файл") }}</v-btn>
  <v-dialog v-model="opened" content-class="u1-dialog u1-unified-dialog" max-width="550"><v-card><u1-dialog-close @close="opened = false" /><v-card-title>{{ $u1t("Очистить список") }} {{ kind === 'usage' ? $u1t("списаний") : $u1t("ошибок") }}?</v-card-title><v-card-text>
    <p>{{ $u1t("Записей:") }} {{ plan?.count || 0 }}{{ $u1t(". Перед изменением создаётся резервная копия. Новые записи, появившиеся после открытия этого окна, останутся в списке.") }}</p>
    <v-alert v-if="plan?.review" dense type="warning">{{ $u1t("Списаний к проверке:") }} {{ plan.review }}{{ $u1t(". Их можно будет найти через «Показать архив».") }}</v-alert>
    <p>{{ $u1t("Учёт расхода, остатки филамента и сами записи не удаляются. Сообщения об активных ошибках принтера этой кнопкой не снимаются.") }}</p>
    <v-checkbox v-model="confirmed" :label="$u1t('Подтверждаю очистку этого списка')" />
    <v-alert v-if="error" dense type="error">{{ error }}</v-alert>
    <v-btn color="primary" block :disabled="busy || !confirmed || !plan" :loading="busy" @click="clear">{{ $u1t("Очистить список") }}</v-btn>
  </v-card-text></v-card></v-dialog>
</div>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import { Component, Prop } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
interface Plan { token: string; count: number; review: number }
@Component
export default class U1LogTools extends Vue {
  @Prop({ required: true }) readonly kind!: 'usage' | 'errors'
  busy = false
  archive = false
  opened = false
  confirmed = false
  error = ''
  notice = ''
  plan: Plan | null = null
  downloadUrl = ''
  downloadName = ''
  async download (format: 'json' | 'csv') {
    if (this.busy) return
    this.busy = true; this.error = ''; this.notice = ''
    try {
      const result = await u1DataRequest<{content: string; count: number}>('logs_export', { kind: this.kind, format, includeArchived: this.archive })
      if (this.downloadUrl) URL.revokeObjectURL(this.downloadUrl)
      this.downloadName = 'u1-' + this.kind + '-' + new Date().toISOString().slice(0, 10) + '.' + format
      this.downloadUrl = URL.createObjectURL(new Blob([result.content], { type: format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8' }))
      const link = document.createElement('a'); link.href = this.downloadUrl; link.download = this.downloadName; document.body.appendChild(link); link.click(); link.remove()
      this.notice = u1t("Подготовлено записей: ") + result.count + u1t(". Если загрузка не началась, нажмите «Скачать подготовленный файл».")
    } catch (e) { this.error = (e as Error).message } finally { this.busy = false }
  }
  async prepare () {
    if (this.busy) return
    this.busy = true; this.error = ''; this.notice = ''; this.confirmed = false
    try { this.plan = await u1DataRequest<Plan>('logs_prepare_clear', { kind: this.kind }); this.opened = true } catch (e) { this.error = (e as Error).message } finally { this.busy = false }
  }
  async clear () {
    if (!this.plan || !this.confirmed || this.busy) return
    this.busy = true; this.error = ''
    try { await u1DataRequest('logs_clear', { token: this.plan.token, confirmed: true }); this.opened = false; this.archive = false; this.$emit('archive', false); this.$emit('changed'); this.notice = u1t("Список очищен. Записи доступны через «Показать архив».") } catch (e) { this.error = (e as Error).message } finally { this.busy = false }
  }
  beforeDestroy () { if (this.downloadUrl) URL.revokeObjectURL(this.downloadUrl) }
}
</script>
<style scoped>.log-actions { display:flex;gap:6px;flex-wrap:wrap }.log-actions .v-btn { letter-spacing:0;text-transform:none }</style>
