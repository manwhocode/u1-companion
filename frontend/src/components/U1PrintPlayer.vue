<template>
<v-card outlined class="u1-print-player">
  <div class="player-track">
    <div class="player-track-info">
      <span class="player-label">{{ $u1t("Управление печатью") }}</span>
      <strong class="player-filename" :title="state?.filename">{{ state?.filename || $u1t("Выберите файл на принтере") }}</strong>
      <span class="player-state">{{ stateLabel }}<template v-if="printing || paused"> · {{ elapsed }} · {{ percent }}%</template></span>
    </div>
    <div class="player-buttons" role="group" :aria-label="$u1t('Управление печатью')">
      <u1-cover-fans />
      <v-btn icon class="player-secondary" :disabled="busy || !state?.canStart" :aria-label="$u1t('Выбрать файл для печати')" :title="$u1t('Выбрать файл для печати')" @click="openStart"><v-icon>$folder</v-icon></v-btn>
      <v-btn fab depressed color="primary" class="player-play" :disabled="busy || (!state?.canStart && !state?.canResume)" :loading="action === 'resume' || action === 'start'" :aria-label="paused ? $u1t('Продолжить печать') : $u1t('Запустить печать')" :title="paused ? $u1t('Продолжить печать') : $u1t('Запустить печать')" @click="play"><v-icon large>$play</v-icon></v-btn>
      <v-btn icon class="player-secondary" :disabled="busy || !state?.canPause" :loading="action === 'pause'" :aria-label="$u1t('Пауза печати')" :title="$u1t('Пауза печати')" @click="send('pause')"><v-icon>$pause</v-icon></v-btn>
      <v-btn icon class="player-secondary" :disabled="busy || !state?.canCancel" :loading="action === 'cancel'" :aria-label="$u1t('Отменить текущую печать')" :title="$u1t('Отменить текущую печать')" @click="confirm('cancel')"><v-icon>$stop</v-icon></v-btn>
      <v-btn icon class="player-secondary" :disabled="busy || (!printing && !paused)" :aria-label="$u1t('Открыть таймер паузы')" :title="$u1t('Пауза с таймером')" @click="$emit('timer')"><v-icon>$clock</v-icon></v-btn>
    </div>
  </div>
  <v-progress-linear :value="percent" height="5" rounded :color="paused ? 'warning' : 'primary'" class="mt-3" :aria-label="$u1t('Прогресс печати')" />
  <u1-favorite-models class="mt-2" @choose="chooseFavorite" />
  <u1-magnet-pause><slot /></u1-magnet-pause>
  <v-alert v-if="connectionError || error" dense type="error" class="mt-3 mb-0">{{ connectionError || error }}</v-alert>
  <p v-if="notice" class="player-notice mb-0 mt-2" role="status">{{ notice }}</p>
  <p v-if="(printing || paused) && state?.reason" class="player-notice mb-0 mt-2">{{ state.reason }}</p>
  <v-btn v-if="state?.canAcknowledgeBed" outlined color="primary" class="mt-3" :disabled="busy" @click="confirm('ack_bed')">{{ $u1t("Стол очищен — продолжить") }}</v-btn>

  <v-dialog v-model="startOpen" content-class="u1-dialog u1-unified-dialog" max-width="700" scrollable>
    <v-card>
      <u1-dialog-close @close="startOpen = false" />
      <v-card-title>{{ $u1t("Запустить печать") }}</v-card-title>
      <v-card-text>
        <v-alert v-if="error" dense type="error">{{ error }}</v-alert>
        <v-autocomplete v-model="filename" :items="files" :label="$u1t('G-code на принтере')" outlined dense :loading="filesLoading" :disabled="busy" @change="resetPlan" />
        <v-row dense><v-col v-for="(_, i) in mapping" :key="i" cols="6" sm="3"><v-select v-model="mapping[i]" :items="heads" :label="$u1t('Филамент T') + (i + 1)" outlined dense :disabled="busy" @change="resetPlan" /></v-col></v-row>
        <v-checkbox v-model="bedLevel" :label="$u1t('Штатное выравнивание стола перед печатью')" :disabled="busy" @change="resetPlan" />
        <v-checkbox v-model="flowCalibration" :label="$u1t('Штатная калибровка K перед печатью')" :disabled="busy" @change="resetPlan" />
        <v-btn outlined :disabled="busy || !filename || !state?.canStart" :loading="action === 'prepare'" @click="prepare">{{ $u1t("Проверить файл и катушки") }}</v-btn>
        <template v-if="plan">
          <v-card outlined class="pa-3 mt-3">
            <strong>{{ plan.filename }}</strong>
            <p v-for="row in plan.rows" :key="row.logical" class="mb-1 mt-2">T{{ row.logical + 1 }} {{ $u1t("→ головка") }} {{ row.head + 1 }} · {{ row.name }} · {{ row.material }} {{ row.hex }}<br>{{ $u1t("Нужно") }} {{ grams(row.required) }} {{ $u1t("г · осталось") }} {{ grams(row.remaining) }} {{ $u1t("г") }}</p>
          </v-card>
          <v-checkbox v-model="confirmed" :label="$u1t('Стол свободен, модель снята, зона движения проверена. Разрешаю штатный запуск с нагревом и движениями.')" :disabled="busy" />
          <v-btn color="primary" :disabled="busy || !confirmed || !state?.canStart" :loading="action === 'start'" @click="start">{{ $u1t("Запустить сейчас") }}</v-btn>
        </template>
        <p class="mt-4">{{ $u1t("Используются файлы, уже загруженные на принтер. Привяжите свои катушки к используемым головкам. Перед запуском повторно проверяются файл, остаток филамента, профили и готовность U1.") }}</p>
      </v-card-text>
    </v-card>
  </v-dialog>
  <v-dialog v-model="confirmOpen" content-class="u1-dialog u1-unified-dialog" max-width="520">
    <v-card>
      <u1-dialog-close @close="confirmOpen = false" />
      <v-card-title>{{ pendingAction === 'ack_bed' ? $u1t("Модель со стола снята?") : pendingAction === 'cancel' ? $u1t("Отменить печать?") : $u1t("Продолжить печать?") }}</v-card-title>
      <v-card-text>
        <p>{{ state?.filename }}</p>
        <p v-if="pendingAction === 'ack_bed'">{{ $u1t("U1 остановился при проверке стола до первого слоя. Уберите старую модель и посторонние предметы. Подтверждение запустит штатное продолжение U1 с нагревом, подачей филамента и движением. Остальные ошибки и защиты не сбрасываются.") }}</p>
        <p>{{ pendingAction === 'cancel' ? $u1t("Обычная отмена U1 удалит штатную точку восстановления. Чтобы продолжить позже, выберите паузу вместо отмены. Таймер продолжения также отключится.") : $u1t("Проверьте модель и свободную зону движения. U1 выполнит штатное продолжение; таймер этой паузы будет отключён.") }}</p>
        <v-alert v-if="error" dense type="error">{{ error }}</v-alert>
        <v-btn v-if="pendingAction === 'cancel' && state?.canPause" outlined color="primary" class="mb-2" :disabled="busy || pendingJob !== state?.currentJob" @click="send('pause')">{{ $u1t("Пауза вместо отмены — продолжить позже") }}</v-btn>
        <v-btn :color="pendingAction === 'cancel' ? 'error' : 'primary'" :disabled="busy || !pendingJob || pendingJob !== state?.currentJob" :loading="busy" @click="send(pendingAction)">{{ pendingAction === 'cancel' ? $u1t("Отменить печать") : $u1t("Продолжить печать") }}</v-btn>
      </v-card-text>
    </v-card>
  </v-dialog>
</v-card>
</template>
<script lang="ts">
import { u1t } from '@/plugins/i18n'



import Vue from 'vue'
import U1MagnetPause from '@/components/U1MagnetPause.vue'
import U1CoverFans from '@/components/U1CoverFans.vue'
import U1FavoriteModels from '@/components/U1FavoriteModels.vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
import { httpClientActions as http } from '@/api/httpClientActions'
interface State { ready: boolean; state: string; filename: string; progress: number; duration: number; currentJob: string | null; reason: string; canStart: boolean; canPause: boolean; canResume: boolean; canCancel: boolean; canAcknowledgeBed?: boolean }
interface Plan { token: string; filename: string; rows: { logical: number; head: number; name: string; material: string; hex: string; required: number; remaining: number }[] }
@Component({ components: { U1FavoriteModels, U1MagnetPause, U1CoverFans } })
export default class U1PrintPlayer extends Vue {
  state: State | null = null
  action = ''
  loading = false
  error = ''
  connectionError = ''
  notice = ''
  timer: number | null = null
  startOpen = false
  confirmOpen = false
  pendingAction: 'resume' | 'cancel' | 'ack_bed' = 'resume'
  pendingJob: string | null = null
  files: string[] = []
  filesLoading = false
  filename = ''
  mapping = [0, 1, 2, 3]
  heads = [0, 1, 2, 3].map(value => ({ value, text: u1t("Головка ") + (value + 1) }))
  bedLevel = true
  flowCalibration = false
  confirmed = false
  plan: Plan | null = null
  get busy () { return this.action !== '' }
  get printing () { return this.state?.state === 'printing' }
  get paused () { return this.state?.state === 'paused' }
  get percent () { return Math.round((this.state?.progress || 0) * 100) }
  get stateLabel () { if (this.connectionError || !this.state?.ready) return u1t("Нет готового соединения с принтером"); return ({ standby: u1t("Готов к печати"), complete: u1t("Печать завершена"), cancelled: u1t("Печать отменена"), printing: u1t("Печать"), paused: u1t("Пауза"), error: u1t("Ошибка") } as Record<string, string>)[this.state.state] || this.state.state }
  get elapsed () { const s = Math.max(0, Math.floor(this.state?.duration || 0)); return Math.floor(s / 3600) + ':' + String(Math.floor(s % 3600 / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0') }
  grams (value: number) { return value.toLocaleString(this.$i18n.locale, { maximumFractionDigits: 1 }) }
  resetPlan () { this.plan = null; this.confirmed = false }
  async load () {
    if (this.loading || this.busy) return
    this.loading = true
    try { this.state = await u1DataRequest<State>('print_player_state', {}, 12000); this.connectionError = '' } catch (error) { this.connectionError = (error as Error).message; this.state = null } finally { this.loading = false }
  }
  play () { if (this.paused) this.confirm('resume'); else this.openStart() }
  confirm (action: 'resume' | 'cancel' | 'ack_bed') { this.error = ''; this.pendingAction = action; this.pendingJob = this.state?.currentJob || null; this.confirmOpen = true }
  async chooseFavorite (filename: string) { await this.openStart(); this.filename = filename; this.resetPlan() }
  async openStart () {
    this.startOpen = true; this.error = ''; this.resetPlan(); this.filesLoading = true
    try { const result = await http.get<{result: {path: string}[]}>('/server/files/list?root=gcodes'); this.files = result.data.result.filter(f => f.path.toLowerCase().endsWith('.gcode')).map(f => f.path); if (!this.filename && this.state?.filename && this.files.includes(this.state.filename)) this.filename = this.state.filename } catch (error) { this.error = (error as Error).message } finally { this.filesLoading = false }
  }
  async prepare () {
    this.action = 'prepare'; this.error = ''; this.resetPlan()
    try { this.plan = await u1DataRequest<Plan>('print_player_prepare', { filename: this.filename, mapping: this.mapping, bedLevel: this.bedLevel, flowCalibration: this.flowCalibration }) } catch (error) { this.error = (error as Error).message } finally { this.action = '' }
  }
  async start () {
    if (!this.plan || !this.confirmed || this.busy) return
    this.action = 'start'; this.error = ''
    try { const result = await u1DataRequest<{message: string}>('print_player_start', { token: this.plan.token, confirmed: true }); this.notice = result.message; this.startOpen = false } catch (error) { this.error = (error as Error).message } finally { this.resetPlan(); this.action = ''; this.load() }
  }
  async send (action: 'pause' | 'resume' | 'cancel' | 'ack_bed') {
    if (this.busy) return
    const currentJob = action === 'pause' ? this.state?.currentJob : this.pendingJob
    if (!currentJob) return
    this.action = action; this.error = ''
    try { const result = await u1DataRequest<{message: string}>('print_player_action', { action, currentJob, confirmed: action !== 'pause' }); this.notice = result.message; this.confirmOpen = false } catch (error) { this.error = (error as Error).message } finally { this.action = ''; this.load() }
  }
  mounted () { this.load(); this.timer = window.setInterval(() => this.load(), 3000) }
  beforeDestroy () { if (this.timer !== null) window.clearInterval(this.timer) }
}
</script>
<style scoped>
.u1-print-player { padding:14px 16px; margin-bottom:12px; border-radius:16px; background:linear-gradient(110deg,rgba(127,127,127,.09),transparent) }
.player-track { display:flex; align-items:center; justify-content:space-between; gap:16px }
.player-track-info { display:flex; flex-direction:column; gap:3px; min-width:0 }
.player-label { font-size:11px; letter-spacing:.08em; text-transform:uppercase; opacity:.65 }
.player-filename { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:15px }
.player-state, .player-notice { font-size:12px; opacity:.8 }
.player-buttons { display:flex; align-items:center; gap:8px; flex-shrink:0 }
.player-play { width:56px; height:56px }
.player-secondary { width:40px; height:40px; border:1px solid rgba(127,127,127,.25); border-radius:50% }
@media(max-width:600px) { .u1-print-player { padding:12px } .player-track { flex-direction:column; align-items:stretch; gap:12px } .player-buttons { justify-content:center } .player-filename { font-size:14px } }
</style>
