<template>
<div class="mb-3">
  <v-btn @click="open">{{ $u1t("Сушка филамента") }}</v-btn>
  <v-dialog v-model="opened" content-class="u1-maintenance-dialog u1-unified-dialog" max-width="780" scrollable>
    <v-card>
      <u1-dialog-close @close="opened = false" />
      <v-card-title>{{ $u1t("Сушка филамента · U1") }}<v-spacer /></v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" dense>{{ error }}</v-alert>
        <v-alert v-if="state" dense :type="state.state === 'paused' || state.state === 'interrupted' ? 'warning' : 'info'">{{ state.message }}<br>{{ $u1t("Стол:") }} {{ state.bedTemperature == null ? '—' : state.bedTemperature.toLocaleString($i18n.locale, {minimumFractionDigits: 1, maximumFractionDigits: 1}) }} {{ $u1t("°C · камера:") }} {{ state.chamberTemperature == null ? '—' : state.chamberTemperature.toLocaleString($i18n.locale, {minimumFractionDigits: 1, maximumFractionDigits: 1}) }} °C<br>{{ $u1t("Осталось:") }} {{ remaining }}</v-alert>
        <v-select v-model="material" :items="materials" :label="$u1t('Материал')" outlined dense :disabled="active" @change="selectMaterial" />
        <v-autocomplete v-model="colorId" :items="colorItems" clearable :label="$u1t('Филамент из библиотеки (необязательно)')" outlined dense :disabled="active" @change="selectColor" />
        <p>{{ reference }}</p>
        <v-alert dense type="warning">{{ $u1t("Выбирайте температуру и время по рекомендациям производителя филамента. Здесь задаётся температура стола: воздух и сама катушка могут быть холоднее. Проверьте термостойкость катушки и подставки; эффективность сушки зависит от прогрева и вентиляции.") }}</v-alert>
        <v-select v-model="mode" :items="[{value:'bed',text:$u1t('Температура стола')},{value:'chamber',text:$u1t('Максимальная температура камеры')}]" :label="$u1t('Режим сушки')" :disabled="active" outlined dense />
        <v-text-field v-if="mode === 'chamber'" v-model.number="chamberTarget" type="number" min="25" :max="Math.min(55,limit-3)" :label="$u1t('Максимальная температура камеры')" :hint="$u1t('Нагрев стола выключается у цели и возобновляется после снижения на 2 °C. Защитный порог остаётся отдельным.')" persistent-hint outlined dense :disabled="active" />
        <v-text-field v-model.number="temperature" type="number" min="30" max="80" :label="$u1t('Температура стола, °C (30–80)')" outlined dense :disabled="active" />
        <v-text-field v-model.number="hours" type="number" min="0.017" max="8" step="0.25" :label="$u1t('Таймер, часов (до 8)')" outlined dense :disabled="active" />
        <v-switch :input-value="true" disabled :label="$u1t('Контролировать температуру камеры — обязательно')" />
        <v-text-field v-model.number="limit" type="number" min="25" max="60" :label="$u1t('Порог камеры, °C (25–60)')" outlined dense :disabled="active" />
        <v-switch :input-value="state?.alexaNotifications" :disabled="busy || !state || (!state.alexaAvailable && !state.alexaNotifications)" :label="$u1t('Alexa: озвучивать окончание и паузу сушки')" @change="setNotifications" />
        <p v-if="state && !state.alexaAvailable">{{ $u1t("Для озвучивания подключите Amazon и включите уведомления на проверенном устройстве в «Настройках дополнения → Alexa».") }}</p>
        <v-btn small outlined :disabled="busy || active" @click="saveProfile">{{ $u1t("Сохранить параметры") }} {{ colorId ? $u1t("филамента") : $u1t("материала") }}</v-btn>
        <p class="mt-3">{{ $u1t("Разместите катушку без контакта с горячим столом на термостойкой подставке, вне зоны головок. Проверьте термостойкость пластиковой/бумажной тары и указания производителя. Не выполняйте перемещения и калибровку с катушкой внутри. Для удаления влаги нужен подходящий путь вентиляции.") }}</p>
        <v-checkbox v-model="confirmed" :label="$u1t('Размещение, термостойкость катушки и свободная зона проверены. Разрешаю нагрев только стола.')" />
        <div class="dryer-actions">
          <v-btn color="primary" :disabled="busy || active || !confirmed || !state" :loading="busy" @click="action('start')">{{ $u1t("Начать сушку") }}</v-btn>
          <v-btn v-if="state && ['heating','running'].includes(state.state)" outlined :disabled="busy" @click="action('pause')">{{ $u1t("Пауза · выключить нагрев") }}</v-btn>
          <v-btn v-if="state?.state === 'paused'" color="primary" outlined :disabled="busy || !confirmed" @click="action('resume')">{{ $u1t("Продолжить") }}</v-btn>
          <v-btn v-if="active" color="error" outlined :disabled="busy" @click="action('cancel')">{{ $u1t("Отменить · выключить нагрев") }}</v-btn>
        </div>
        <p class="mt-3">{{ $u1t(mode === 'chamber' ? "Таймер идёт при нагретой камере; жёсткий предел всей сессии — 8 часов, включая ожидания. При пороге камеры, ошибке, пропавшем датчике или связи со службой нагрев отключается. Продолжение только вручную после охлаждения камеры ниже порога на 3 °C. После перезапуска сушка не возобновляется. Закрытие окна не останавливает сушку." : "Таймер идёт при нагретом столе; жёсткий предел всей сессии — 8 часов, включая ожидания. При пороге камеры, ошибке, пропавшем датчике или связи со службой нагрев отключается. Продолжение только вручную после охлаждения камеры ниже порога на 3 °C. После перезапуска сушка не возобновляется. Закрытие окна не останавливает сушку.") }}</p>
        <p>{{ $u1t("Печать блокируется модулем Klipper во время нагрева и паузы сушки. Перед печатью отмените сушку и уберите катушку из камеры. Штатные термозащиты не отключаются.") }}</p>
      </v-card-text>
      
    </v-card>
  </v-dialog>
</div>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { readU1Item, u1DataRequest } from '@/utils/u1DataClient'
interface Preset { mode?: 'bed' | 'chamber'; chamberTarget?: number; temperature: number; seconds: number; limit: number }
interface Profiles { revision: string; entries: Record<string, Preset> }
interface State { state: string; message: string; remaining: number; bedTemperature: number | null; chamberTemperature: number | null; alexaNotifications: boolean; alexaAvailable: boolean }
interface Color { id: string; name: string; material: string; manufacturer?: string }
@Component
export default class U1Dryer extends Vue {
  opened = false
  busy = false
  loading = false
  error = ''
  confirmed = false
  material = 'PLA'
  colorId: string | null = null
  mode: 'bed' | 'chamber' = 'bed'
  chamberTarget = 40
  temperature = 40
  hours = 4
  limit = 60
  state: State | null = null
  profiles: Profiles = { revision: '', entries: {} }
  colors: Color[] = []
  timer: number | null = null
  materials = ['PLA', 'PETG', 'TPU', 'ABS', 'ASA', 'PA', 'PC', 'PVA']
  get active () { return !!this.state && ['heating', 'running', 'paused', 'interrupted'].includes(this.state.state) }
  get remaining () { return this.state ? Math.ceil(this.state.remaining / 60) + u1t(" мин") : '—' }
  get key () { return this.colorId ? 'color:' + this.colorId : 'material:' + this.material }
  get colorItems () { return this.colors.filter(c => c.material === this.material).map(c => ({ value: c.id, text: `${c.manufacturer || ''} · ${c.name}` })) }
  get reference () { return ({ PLA: u1t("Материал: 40–45 °C, 4–6 ч."), PETG: u1t("Материал: 55–60 °C, 4–6 ч."), TPU: u1t("Материал: 40–50 °C, 4–6 ч."), ABS: u1t("Материал: 60–70 °C, 4–6 ч."), ASA: u1t("Материал: 60–70 °C, 4–6 ч."), PA: u1t("Материал: 70–80 °C, 6–8 ч. Нагревом стола такие температуры в катушке могут быть недостижимы.") } as Record<string, string>)[this.material] || u1t("Используйте параметры производителя. Для этого материала предварительного ориентира в ТЗ нет.") }
  selectMaterial () { this.colorId = null; this.selectColor() }
  selectColor () { const p = this.profiles.entries[this.key]; this.mode = p?.mode ?? 'bed'; this.chamberTarget = p?.chamberTarget ?? 40; this.temperature = p?.temperature ?? 40; this.hours = p ? p.seconds / 3600 : 4; this.limit = p?.limit ?? 60; this.confirmed = false }
  async open () {
    this.opened = true
    await this.load()
    try { this.profiles = await u1DataRequest<Profiles>('dryer_profiles'); this.colors = (await readU1Item<{entries: Color[]}>('u1_filament_library_v1')).data.result.value.entries; if (!this.active) this.selectColor() } catch (error) { this.error = (error as Error).message }
  }
  async setNotifications (enabled: boolean) { this.busy = true; try { this.state = await u1DataRequest<State>('dryer_notifications', { enabled }); this.error = '' } catch (error) { this.error = (error as Error).message } finally { this.busy = false } }
  async saveProfile () {
    this.busy = true
    try { this.profiles = await u1DataRequest<Profiles>('dryer_profile_save', { revision: this.profiles.revision, key: this.key, mode: this.mode, chamberTarget: this.chamberTarget, temperature: this.temperature, seconds: this.hours * 3600, limit: this.limit }); this.error = '' } catch (error) { this.error = (error as Error).message } finally { this.busy = false }
  }
  async action (action: string) {
    this.busy = true
    try { this.state = await u1DataRequest<State>('dryer_action', { action, confirmed: this.confirmed, mode: this.mode, chamberTarget: this.chamberTarget, temperature: this.temperature, seconds: this.hours * 3600, limit: this.limit }); this.error = ''; this.confirmed = false } catch (error) { this.error = (error as Error).message } finally { this.busy = false }
  }
  async load () {
    if (this.loading || this.busy) return
    this.loading = true
    try { this.state = await u1DataRequest<State>('dryer_state'); this.error = '' } catch (error) { this.error = (error as Error).message } finally { this.loading = false }
  }
  mounted () { this.timer = window.setInterval(() => { if (this.opened) this.load() }, 5000) }
  beforeDestroy () { if (this.timer !== null) window.clearInterval(this.timer) }
}
</script>
<style scoped>.dryer-actions { display:flex;flex-wrap:wrap;gap:8px }</style>
