<template>
<v-card outlined class="pa-3 mb-4">
  <h3>{{ $u1t("Ночной режим верхней крышки") }}</h3>
  <p>{{ $u1t("Только вентиляторы крышки. Во время печати в штатном режиме охлаждения камеры допускается минимум 0%, но температурная автоматика может повысить скорость. Прогрев и горячая камера остаются под штатным управлением.") }}</p>
  <v-alert v-if="state" dense type="info">{{ state.message }}</v-alert>
  <v-alert v-if="error" dense type="error">{{ error }}</v-alert>
  <v-select v-model="mode" :items="modes" :label="$u1t('Ночной режим')" dense outlined />
  <div class="night-times"><v-text-field v-model="start" type="time" :label="$u1t('Начало')" dense outlined /><v-text-field v-model="end" type="time" :label="$u1t('Окончание')" dense outlined /></div>
  <p>{{ $u1t("Расписание повторяется ежедневно и может пересекать полночь. Часовой пояс:") }} {{ zone }}{{ $u1t(". При окончании возвращается штатный минимум вытяжки; после смены режима камеры приоритет у U1. При простое вентиляторы автоматически не включаются и не выключаются этим дополнением.") }}</p>
  <v-btn outlined color="primary" :disabled="busy || !state" :loading="busy" @click="save">{{ $u1t("Сохранить ночной режим") }}</v-btn>
</v-card>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
interface State { revision: string; mode: string; start: string; end: string; zone: string; message: string }
@Component
export default class U1NightMode extends Vue {
  state: State | null = null
  mode = 'off'
  start = '22:00'
  end = '07:00'
  zone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  busy = false
  error = ''
  get modes () { return [{ text: u1t("Выключен"), value: 'off' }, { text: u1t("Включён вручную"), value: 'on' }, { text: u1t("Ежедневно по расписанию"), value: 'schedule' }] }
  async save () {
    if (!this.state) return
    this.busy = true
    try { this.state = await u1DataRequest<State>('night_configure', { revision: this.state.revision, mode: this.mode, start: this.start, end: this.end, zone: this.zone }); this.error = '' } catch (error) { this.error = (error as Error).message } finally { this.busy = false }
  }
  async mounted () {
    this.busy = true
    try { this.state = await u1DataRequest<State>('night_state'); this.mode = this.state.mode; this.start = this.state.start; this.end = this.state.end; if (this.state.zone !== 'UTC') this.zone = this.state.zone } catch (error) { this.error = (error as Error).message } finally { this.busy = false }
  }
}
</script>
<style scoped>.night-times { display: flex; gap: 12px; flex-wrap: wrap }.night-times > * { min-width: 130px; flex: 1 }</style>
