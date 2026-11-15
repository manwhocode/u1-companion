<template>
<div>
  <v-btn small outlined @click="open">{{ $u1t("Пауза с таймером") }}</v-btn>
  <v-alert v-if="job && active" dense type="info" class="mt-2">{{ job.message }} · {{ countdown }} <v-btn small outlined @click="open">{{ $u1t("Открыть") }}</v-btn></v-alert>
  <v-dialog v-model="opened" content-class="u1-dialog u1-unified-dialog" max-width="600" scrollable>
    <v-card>
      <u1-dialog-close @close="opened = false" />
      <v-card-title>{{ $u1t("Пауза с таймером") }}</v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" dense>{{ error }}</v-alert>
        <v-alert v-if="job && job.state !== 'idle'" dense :type="active ? 'info' : 'warning'">{{ job.message }}<br v-if="job.resumeAt">{{ job.resumeAt ? $u1t("Продолжение: ") + date(job.resumeAt) : '' }}</v-alert>
        <p v-if="job?.currentFilename">{{ $u1t("Текущая печать:") }} <strong>{{ job.currentFilename }}</strong></p>
        <p>{{ $u1t("Поставьте текущую печать на штатную паузу и продолжите её автоматически через выбранный интервал. Для уже приостановленной печати можно установить только таймер.") }}</p>
        <v-alert v-if="job && !job.eligible && !active" dense type="warning">{{ job.reason }}</v-alert>
        <v-text-field v-model.number="minutes" type="number" min="1" max="1440" :label="$u1t('Продолжить через, минут')" outlined dense :disabled="busy || active" @input="plan = null; confirmed = false" />
        <v-btn v-if="!active" outlined :disabled="busy || !job?.eligible" :loading="busy" @click="prepare">{{ $u1t("Проверить таймер") }}</v-btn>
        <template v-if="plan">
          <p class="mt-3">{{ plan.filename }} · {{ plan.alreadyPaused ? $u1t("Печать уже на паузе") : $u1t("Сначала будет выполнена штатная пауза") }}{{ $u1t(". Продолжение через") }} {{ plan.minutes }} {{ $u1t("мин после подтверждения паузы принтером.") }}</p>
          <v-checkbox v-model="confirmed" :label="$u1t('Разрешаю автоматическое продолжение этой печати. Зона движения свободна.')" />
          <v-btn color="primary" :disabled="busy || !confirmed" :loading="busy" @click="arm">{{ plan.alreadyPaused ? $u1t("Включить таймер") : $u1t("Пауза и таймер") }}</v-btn>
        </template>
        <v-btn v-if="active" outlined color="warning" :disabled="busy || ['resuming','checking_resume'].includes(job?.state || '')" @click="cancel">{{ $u1t("Отменить только таймер") }}</v-btn>
        <p class="mt-4">{{ $u1t("Таймер работает на принтере при закрытом браузере. Принтер должен оставаться включённым. Штатное управление нагревом сохраняется; при паузе стол может оставаться горячим.") }}</p>
        <p>{{ $u1t("После перезапуска, ошибки, изменения задания, потери позиции или остывания стола автоматическое продолжение отключается. Таймер не восстанавливает печать после отключения питания. Команды не повторяются при потере ответа. При ручном продолжении таймер снимается после обнаружения изменения состояния.") }}</p>
      </v-card-text>
      
    </v-card>
  </v-dialog>
</div>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
interface Job { id?: string; state: string; message: string; now: number; eligible: boolean; reason: string; currentFilename?: string; resumeAt?: number }
interface Plan { token: string; minutes: number; filename: string; alreadyPaused: boolean }
@Component
export default class U1TimedPause extends Vue {
  opened = false
  busy = false
  loading = false
  error = ''
  minutes = 30
  confirmed = false
  job: Job | null = null
  plan: Plan | null = null
  timer: number | null = null
  get active () { return !!this.job && ['pausing','waiting_pause','armed','resuming','checking_resume'].includes(this.job.state) }
  get countdown () { return Math.max(0, Math.ceil(((this.job?.resumeAt || 0) - (this.job?.now || 0)) / 60)) + u1t(" мин") }
  date (value: number) { return new Date(value * 1000).toLocaleString('ru-RU') }
  open () { this.opened = true; this.plan = null; this.confirmed = false; this.load() }
  async load () {
    if (this.loading || this.busy) return
    this.loading = true
    try { this.job = await u1DataRequest<Job>('timed_pause_state') } catch (error) { this.error = (error as Error).message } finally { this.loading = false }
  }
  async prepare () { this.plan = null; this.confirmed = false; this.busy = true; try { this.plan = await u1DataRequest<Plan>('timed_pause_prepare', { minutes: this.minutes }); this.error = '' } catch (error) { this.error = (error as Error).message } finally { this.busy = false } }
  async arm () { if (!this.plan) return; this.busy = true; try { this.job = await u1DataRequest<Job>('timed_pause_arm', { token: this.plan.token, confirmed: this.confirmed }); this.error = '' } catch (error) { this.error = (error as Error).message } finally { this.plan = null; this.confirmed = false; this.busy = false } }
  async cancel () { this.busy = true; try { this.job = await u1DataRequest<Job>('timed_pause_cancel', { id: this.job?.id }); this.error = '' } catch (error) { this.error = (error as Error).message } finally { this.busy = false } }
  mounted () { this.load(); this.timer = window.setInterval(() => { if (this.opened || this.active) this.load() }, 5000) }
  beforeDestroy () { if (this.timer !== null) window.clearInterval(this.timer) }
}
</script>
