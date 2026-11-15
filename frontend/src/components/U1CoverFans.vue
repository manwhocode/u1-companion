<template>
<div>
  <v-btn icon class="cover-fan-button" :aria-label="$u1t('Вентиляторы крышки')" :title="$u1t('Вентиляторы крышки')" @click="open"><v-icon>{{ fanIcon }}</v-icon></v-btn>
  <v-dialog v-model="opened" content-class="u1-dialog u1-unified-dialog" max-width="480" scrollable>
    <v-card>
      <u1-dialog-close @close="opened = false" />
      <v-card-title>{{ $u1t("Вентиляторы крышки") }}</v-card-title>
      <v-card-text>
        <v-alert v-if="error" dense type="error" dismissible @input="error = ''">{{ error }}</v-alert>
        <p>{{ $u1t("Только вентиляторы верхнего кожуха. Штатные защиты и автоматическое охлаждение сохраняются и могут повысить скорость, в том числе при выборе 0%.") }}</p>
        <template v-if="cover">
          <p v-if="!cover.power_detected">{{ $u1t("Крышка не подключена.") }}</p>
          <div v-for="row in rows" :key="row.key" class="mb-5">
            <strong>{{ row.label }}</strong><span class="float-right">{{ $u1t("Сейчас") }} {{ actual(row.key) }}%</span>
            <v-slider v-model="values[row.key]" min="0" max="100" step="5" thumb-label :disabled="busy || !cover.power_detected" hide-details />
            <div class="cover-actions"><v-btn outlined :disabled="busy || !cover.power_detected" @click="apply(row.key, 0)">{{ $u1t("0% · выключить") }}</v-btn><v-btn color="primary" :disabled="busy || !cover.power_detected" :loading="busy" @click="apply(row.key, values[row.key])">{{ $u1t("Применить") }} {{ values[row.key] }}%</v-btn></div>
          </div>
          <p v-if="cover.inner_fan.delay">{{ $u1t("Задержка отключения внутреннего вентилятора:") }} {{ cover.inner_fan.delay }} {{ $u1t("с.") }}</p>
        </template>
        <p v-if="notice" role="status">{{ notice }}</p>
      </v-card-text>
    </v-card>
  </v-dialog>
</div>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { mdiFan } from '@mdi/js'
import { httpClientActions as http } from '@/api/httpClientActions'
import { coverCommand, type Cover } from '@/utils/u1CoverFans'
@Component
export default class U1CoverFans extends Vue {
  fanIcon = mdiFan
  opened = false
  busy = false
  error = ''
  notice = ''
  cover: Cover | null = null
  values = { exhaust: 0, inner: 0 }
  get rows (): {key: 'exhaust' | 'inner'; label:string}[] { return [{ key: 'exhaust', label: u1t("Вытяжка") }, { key: 'inner', label: u1t("Циркуляция") }] }
  async read () { const r = await http.get<{result: {status: {purifier: Cover}}}>('/printer/objects/query?purifier'); this.cover = r.data.result.status.purifier; return this.cover }
  actual (key: 'exhaust' | 'inner') { return Math.round((this.cover?.[key === 'inner' ? 'inner_fan' : 'exhaust_fan'].speed || 0) * 100) }
  async open () {
    this.opened = true; this.error = ''; this.notice = ''; this.busy = true
    try { const p = await this.read(); this.values = { exhaust: Math.round(p.exhaust_fan.speed_threshold * 100), inner: this.actual('inner') } } catch (e) { this.error = (e as Error).message } finally { this.busy = false }
  }
  async apply (fan: 'inner' | 'exhaust', percent: number) {
    if (this.busy) return
    this.busy = true; this.error = ''; this.notice = ''
    try {
      const p = await this.read()
      const script = coverCommand(p, fan, percent)
      this.notice = u1t("Команда отправляется. Во время нагрева или перемещений выполнение может ждать штатной очереди U1.")
      await http.post('/printer/gcode/script', { script }, { timeout: 60000 })
      this.values[fan] = percent; await this.read()
      this.notice = u1t("Запрошено {p0}%. Фактически {p1}%. Штатная автоматика и ночной режим имеют приоритет.", { p0: percent, p1: this.actual(fan) })
    } catch (e) { this.notice = ''; this.error = u1t("Не удалось подтвердить выполнение. Команда могла остаться в очереди U1; повторно автоматически не отправляется. ") + (e as Error).message; try { await this.read() } catch { /* Keep the original command result. */ } } finally { this.busy = false }
  }
}
</script>
<style scoped>
.cover-fan-button { width:40px;height:40px;border:1px solid rgba(127,127,127,.25);border-radius:50% }
.cover-actions { display:flex;gap:8px }.cover-actions > * { flex:1;min-width:0;font-size:12px;letter-spacing:0 }
</style>
