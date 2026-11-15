<template>
<div class="mb-3">
  <v-btn small outlined @click="opened = true; load()">{{ $u1t("Восстановление печати") }}</v-btn>
  <v-dialog v-model="opened" content-class="u1-maintenance-dialog u1-unified-dialog" max-width="700" scrollable>
    <v-card>
      <u1-dialog-close @close="opened = false" />
      <v-card-title>{{ $u1t("Восстановление и контрольные точки") }}<v-spacer /></v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="warning" dense>{{ error }} {{ $u1t("Последние данные могут быть устаревшими.") }}</v-alert>
        <template v-if="state">
          <v-alert :type="valid ? 'info' : 'warning'" dense>{{ valid ? $u1t("U1 сообщает о наличии штатного окружения восстановления. Это ещё не подтверждение безопасного продолжения.") : $u1t("U1 не подтверждает штатную точку восстановления. Продолжение из этого окна недоступно.") }}</v-alert>
          <p>{{ $u1t("Проверено:") }} {{ checkedAt }}<br>Klipper: {{ state.webhooks?.state || $u1t("неизвестно") }}<br>{{ $u1t("Печать:") }} {{ printState }}<br>{{ $u1t("Наличие окружения:") }} {{ state.virtual_sdcard?.pl_env_valid === true ? $u1t("подтверждено U1") : state.virtual_sdcard?.pl_env_valid === false ? $u1t("не подтверждено") : $u1t("неизвестно") }}</p>
          <p>{{ $u1t("Текущий файл:") }} {{ state.virtual_sdcard?.file_path || state.print_stats?.filename || $u1t("не открыт") }}<br>{{ $u1t("Текущая позиция файла:") }} {{ state.virtual_sdcard?.file_position ?? $u1t("неизвестно") }} {{ $u1t("байт") }}<br>{{ $u1t("Текущий слой:") }} {{ state.print_stats?.info?.current_layer ?? $u1t("неизвестно") }}</p>
          <p>{{ $u1t("Позиция и слой выше относятся к текущему состоянию печати. Они не определяют позицию сохранённой точки после отключения питания.") }}</p>
          <v-alert v-if="reasons.length" dense type="warning"><div v-for="reason in reasons" :key="reason">{{ reason }}</div></v-alert>
          <p v-else>{{ $u1t("Явных препятствий в доступном статусе нет. Перед штатным продолжением на экране U1 проверьте сохранность модели и её крепление, стол, головки, филаменты и свободную зону движения.") }}</p>
        </template>
        <v-alert dense type="warning">{{ $u1t("Обычный «Стоп / Отмена» удаляет штатную точку U1. Архивы ниже сохраняются, но пока не позволяют безопасно продолжить отменённую печать. Чтобы оставить возможность продолжения без выключения питания, используйте паузу.") }}</v-alert>
        <v-btn outlined color="primary" :disabled="loading || submitting || !valid" :loading="preparing" @click="prepare">{{ $u1t("Проверить штатную точку") }}</v-btn>
        <template v-if="plan">
          <p class="mt-3">{{ $u1t("Исходный файл:") }} {{ plan.filename }}</p>
          <v-checkbox v-model="confirmed" :label="$u1t('Модель и стол не перемещались, модель прочно закреплена, головки и филаменты проверены. Разрешаю штатное восстановление с нагревом и движением.')" :disabled="submitting" />
          <v-btn color="primary" :disabled="!confirmed || submitting" :loading="submitting" @click="resume">{{ $u1t("Восстановить штатную точку") }}</v-btn>
        </template>
        <v-alert v-if="notice" dense type="info" class="mt-3">{{ notice }}</v-alert>
        <h3 class="mt-4">{{ $u1t("Сохранённые снимки наблюдения") }}</h3>
        <p>{{ $u1t("Сохраняются автоматически на U1 при печати и остаются после отмены или перезапуска. Позиция файла может опережать физическое движение. Это история состояния, а не точки отката модели.") }}</p>
        <p v-if="!points.length">{{ $u1t("Пока нет снимков. Они появятся при следующей печати.") }}</p>
        <v-card v-for="point in points.slice(0, 6)" :key="point.id" outlined class="pa-2 mb-2">
          <strong>{{ point.filename }}</strong><br>
          {{ new Date(point.time * 1000).toLocaleString('ru-RU') }} {{ $u1t("· слой") }} {{ point.layer ?? $u1t("неизвестен") }} · {{ point.filePosition }} {{ $u1t("байт") }}
          <span v-if="point.endedAs"> · {{ point.endedAs === 'cancelled' ? $u1t("печать отменена") : point.endedAs === 'complete' ? $u1t("завершена") : $u1t("ошибка") }}</span>
        </v-card>
        <p>{{ $u1t("Для продолжения после отключения питания используется только текущая точка, подтверждённая U1 и микроконтроллерами. Не запускайте исходный файл заново поверх модели.") }}</p>
        <v-btn outlined :loading="loading" :disabled="submitting" @click="load">{{ $u1t("Обновить состояние") }}</v-btn>
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
interface Checkpoint { id: string; time: number; filename: string; layer: number | null; filePosition: number; endedAs?: string }
interface Plan { token: string; filename: string }
interface Status {
  webhooks?: { state?: string }; virtual_sdcard?: { pl_env_valid?: boolean; file_path?: string | null; file_position?: number; is_active?: boolean };
  print_stats?: { state?: string; filename?: string; info?: { current_layer?: number | null } };
  exception_manager?: { exceptions?: unknown[] }; purifier?: { power_detected?: boolean };
}
@Component
export default class U1Recovery extends Vue {
  opened = false
  loading = false
  state: Status | null = null
  error = ''
  checkedAt = ''
  points: Checkpoint[] = []
  plan: Plan | null = null
  confirmed = false
  preparing = false
  submitting = false
  notice = ''
  get valid () { return this.state?.virtual_sdcard?.pl_env_valid === true }
  get printState () { const value = this.state?.print_stats?.state || ''; return ({ standby: u1t("ожидание"), printing: u1t("печать"), paused: u1t("пауза"), complete: u1t("завершена"), cancelled: u1t("отменена"), error: u1t("ошибка") } as Record<string, string>)[value] || value || u1t("неизвестно") }
  get reasons () {
    const reasons: string[] = []
    if (this.state?.webhooks?.state !== 'ready') reasons.push(u1t("Klipper не готов или его состояние неизвестно."))
    if (!this.valid) reasons.push(u1t("Нет подтверждённого окружения восстановления."))
    if (this.state?.virtual_sdcard?.is_active || this.state?.print_stats?.state === 'printing') reasons.push(u1t("Сейчас выполняется печать."))
    if (this.state?.print_stats?.state === 'paused') reasons.push(u1t("Текущая печать на паузе: это отличается от восстановления после потери питания."))
    if (!Array.isArray(this.state?.exception_manager?.exceptions)) reasons.push(u1t("Не удалось определить активные ошибки."))
    else if (this.state!.exception_manager!.exceptions!.length) reasons.push(u1t("Есть активные сообщения об ошибках U1. Проверьте их на экране принтера."))
    if (this.state?.purifier?.power_detected !== true) reasons.push(u1t("Подключение верхнего кожуха не подтверждено."))
    return reasons
  }
  async load () {
    if (this.loading) return
    this.loading = true
    try {
      const response = await u1DataRequest<{status: Status; points: Checkpoint[]}>('recovery_state')
      this.state = response.status
      this.points = response.points
      this.checkedAt = new Date().toLocaleString('ru-RU')
      this.error = ''
    } catch { this.error = u1t("Не удалось получить состояние U1.") } finally { this.loading = false }
  }
  async prepare () {
    if (this.preparing || this.submitting) return
    this.preparing = true; this.error = ''; this.plan = null; this.confirmed = false
    try { this.plan = await u1DataRequest<Plan>('recovery_prepare') } catch (error) { this.error = (error as Error).message } finally { this.preparing = false }
  }
  async resume () {
    if (!this.plan || !this.confirmed || this.submitting) return
    this.submitting = true; this.error = ''
    const token = this.plan.token; this.plan = null; this.confirmed = false
    this.notice = u1t("Запрос отправляется U1. Закрытие окна не отменяет штатное восстановление. При потере ответа не повторяйте запрос; проверьте экран принтера.")
    try { await u1DataRequest('recovery_resume', { token, confirmed: true }, 1800000); this.notice = u1t("U1 принял штатное восстановление. Проверьте состояние печати.") } catch (error) { this.error = (error as Error).message } finally { this.submitting = false; this.load() }
  }
}
</script>
