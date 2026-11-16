<template>
<div>
  <v-btn class="companion-settings-button" :aria-label="$u1t('Настройки дополнения')" :title="$u1t('Настройки дополнения')" color="primary" depressed @click="open"><v-icon size="28">$cog</v-icon><span class="settings-button-label">{{ $u1t("Настройки") }}</span></v-btn>
  <v-dialog v-model="opened" eager persistent content-class="u1-dialog u1-unified-dialog" max-width="620" scrollable>
    <v-card>
      <u1-dialog-close @close="opened = false" />
      <v-card-title>{{ $u1t("Настройки дополнения") }}<v-spacer /></v-card-title>
      
      <v-card-text class="settings-content"><v-expansion-panels v-model="section" accordion flat class="settings-accordion" @change="selectSection"><v-expansion-panel><v-expansion-panel-header>{{ sectionNames[0] }}</v-expansion-panel-header><v-expansion-panel-content><section v-show="section === 0"><slot name="connection" /></section></v-expansion-panel-content></v-expansion-panel><v-expansion-panel><v-expansion-panel-header>{{ sectionNames[1] }}</v-expansion-panel-header><v-expansion-panel-content><section v-show="section === 1"><slot name="data" :active="opened && section === 1" /></section></v-expansion-panel-content></v-expansion-panel><v-expansion-panel><v-expansion-panel-header>{{ sectionNames[2] }}</v-expansion-panel-header><v-expansion-panel-content><section v-show="section === 2"><slot name="calibrations" :active="opened && section === 2" /></section></v-expansion-panel-content></v-expansion-panel><v-expansion-panel><v-expansion-panel-header>{{ sectionNames[3] }}</v-expansion-panel-header><v-expansion-panel-content><u1-night-mode v-if="opened" v-show="section === 3" /></v-expansion-panel-content></v-expansion-panel><v-expansion-panel><v-expansion-panel-header>{{ sectionNames[4] }}</v-expansion-panel-header><v-expansion-panel-content><u1-alexa v-if="opened" v-show="section === 4" /></v-expansion-panel-content></v-expansion-panel><v-expansion-panel><v-expansion-panel-header>{{ sectionNames[5] }}</v-expansion-panel-header><v-expansion-panel-content><section v-show="section === 5">
        <h3>{{ $u1t("Входы податчиков U1") }}</h3>
        <p>{{ $u1t("Меняет соответствие входов и головок в printer.cfg. Используйте для подключения сушилки с переставленными трубками.") }}</p>
        <v-alert v-if="message" dense :type="failed ? 'error' : 'info'">{{ message }}</v-alert>
        <v-btn small outlined :disabled="busy" @click="load">{{ $u1t("Обновить настройки") }}</v-btn>
        <template v-if="state">
          <v-checkbox v-model="swap12" :label="$u1t('Поменять входы 1 ↔ 2')" :disabled="busy" hide-details @change="acknowledged = false" />
          <v-checkbox v-model="swap34" :label="$u1t('Поменять входы 3 ↔ 4')" :disabled="busy" hide-details @change="acknowledged = false" />
          <p class="mt-3">{{ swap12 ? $u1t("Левый податчик: входы 1 и 2 переставлены.") : $u1t("Левый податчик: исходная схема.") }}</p>
          <p>{{ swap34 ? $u1t("Правый податчик: входы 3 и 4 переставлены.") : $u1t("Правый податчик: исходная схема.") }}</p>
          <v-alert v-if="state.pendingRestart" dense type="warning">{{ $u1t("Схема в файле отличается от работающего Klipper. Для применения нужен перезапуск.") }}</v-alert>
          <p>{{ $u1t("Сейчас в Klipper: 1↔2 —") }} {{ active(state.activeSwap12) }}; 3↔4 — {{ active(state.activeSwap34) }}.</p>
          <v-btn small outlined :disabled="busy" @click="swap12 = false; swap34 = false; acknowledged = false">{{ $u1t("Исходная схема") }}</v-btn>
          <v-divider class="my-3" />
          <p>{{ $u1t("Перед записью сохраняется копия printer.cfg. Меняются только номера каналов и согласованная последовательность. Применение перезапустит Klipper.") }}</p>
          <v-checkbox v-model="acknowledged" :label="$u1t('Принтер свободен, нагрев выключен. Разрешаю сохранить схему и перезапустить Klipper.')" :disabled="busy || (!changed && !state.pendingRestart)" />
          <p v-if="backup">{{ $u1t("Бэкап:") }} {{ backup }}</p>
        </template>
        </section></v-expansion-panel-content></v-expansion-panel><v-expansion-panel><v-expansion-panel-header>{{ sectionNames[6] }}</v-expansion-panel-header><v-expansion-panel-content><section v-if="opened && section === 6" class="gpt-settings-section"><U1AI settings-only /></section></v-expansion-panel-content></v-expansion-panel><v-expansion-panel><v-expansion-panel-header>{{ sectionNames[7] }}</v-expansion-panel-header><v-expansion-panel-content><u1-remote-access v-if="opened && section === 7" /></v-expansion-panel-content></v-expansion-panel><v-expansion-panel><v-expansion-panel-header>{{ $u1t("О программе") }}</v-expansion-panel-header><v-expansion-panel-content><u1-about v-if="opened && section === 8" /></v-expansion-panel-content></v-expansion-panel></v-expansion-panels></v-card-text>
      <v-card-actions class="settings-actions">
        <v-btn v-if="section === 5" color="primary" :loading="busy" :disabled="busy || !state || !acknowledged || (!changed && !state.pendingRestart)" @click="apply">{{ changed ? $u1t("Сохранить и применить") : $u1t("Применить сохранённое") }}</v-btn>
        
      </v-card-actions>
    </v-card>
  </v-dialog>
</div>
</template>

<script lang="ts">
import { u1t } from '@/plugins/i18n'

import Vue from 'vue'
import U1RemoteAccess from '@/components/U1RemoteAccess.vue'
import U1AI from '@/views/U1AI.vue'
import U1About from '@/components/U1About.vue'
import U1NightMode from '@/components/U1NightMode.vue'
import U1Alexa from '@/components/U1Alexa.vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
import { SocketActions } from '@/api/socketActions'
interface FeederState { swap12: boolean; swap34: boolean; hash: string; pendingRestart: boolean; activeSwap12: boolean | null; activeSwap34: boolean | null; backup?: string }
@Component({ components: { U1About, U1RemoteAccess, U1NightMode, U1Alexa, U1AI } })
export default class U1ProgramSettings extends Vue {
  get sectionNames () { return [u1t("Подключение и ярлык"), u1t("Данные и резервные копии"), u1t("Калибровки"), u1t("Ночной режим"), 'Alexa', u1t("Податчики"), u1t("Управление через GPT"), u1t("Внешний доступ")] }
  selectSection (index: number) { this.section = index; if (index === 5) void this.load() }
  section = 0
  opened = false
  busy = false
  swap12 = false
  swap34 = false
  acknowledged = false
  state: FeederState | null = null
  message = ''
  failed = false
  backup = ''
  get changed () { return this.state && (this.swap12 !== this.state.swap12 || this.swap34 !== this.state.swap34) }
  active (value: boolean | null) { return value === null ? u1t("не определено") : value ? u1t("переставлены") : u1t("исходная схема") }
  async open () { this.opened = true; this.message = ''; this.failed = false; if (this.section === 5) await this.load() }
  async load () {
    if (this.busy) return
    this.busy = true
    this.acknowledged = false
    this.failed = false
    this.message = ''
    try {
      this.state = await u1DataRequest<FeederState>('feeder_state')
      this.swap12 = this.state.swap12
      this.swap34 = this.state.swap34
    } catch (error) { this.state = null; this.failed = true; this.message = error instanceof Error ? error.message : String(error) } finally { this.busy = false }
  }
  async apply () {
    if (this.busy || !this.state || !this.acknowledged) return
    this.busy = true
    this.failed = false
    let written = false
    try {
      if (this.changed) {
        const plan = await u1DataRequest<{previewId: string}>('feeder_prepare', { hash: this.state.hash, swap12: this.swap12, swap34: this.swap34 })
        this.state = await u1DataRequest<FeederState>('feeder_apply', { previewId: plan.previewId })
        this.backup = this.state.backup || ''
        written = true
      }
      if (this.state.pendingRestart) {
        const checkedAt = Date.now()
        await u1DataRequest('feeder_restart_check', { hash: this.state.hash })
        if (Date.now() - checkedAt > 10000) throw new Error(u1t("Проверка перед перезапуском устарела. Обновите настройки и повторите применение."))
        // Physical restart is never persisted as a queued task or retried.
        await SocketActions.printerRestart()
        this.message = u1t("Перезапуск Klipper запрошен. После восстановления соединения нажмите «Обновить настройки» и проверьте схему.")
      } else this.message = u1t("Схема уже применяется.")
    } catch (error) {
      this.failed = true
      this.message = (written ? u1t("Файл сохранён; применение не подтверждено. После восстановления связи обновите настройки. ") : '') + (error instanceof Error ? error.message : String(error))
    } finally { this.busy = false; this.acknowledged = false }
  }
}
</script>
<style scoped>
.companion-settings-button { height:40px !important; min-width:40px !important; padding:0 12px !important; letter-spacing:0; text-transform:none }.settings-button-label { margin-left:6px }
@media(max-width:600px) { .companion-settings-button { width:40px !important; padding:0 !important }.settings-button-label { display:none } }
.settings-tabs { flex:0 0 44px !important;min-height:44px;max-height:44px }
.settings-tabs >>> .v-tab { font-size:12px;letter-spacing:0;text-transform:none;min-width:85px }
.settings-sections { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;flex:0 0 auto;padding:4px 12px 10px }
.settings-sections .settings-section { width:100%;min-width:0;height:auto;min-height:40px;padding:7px 8px;letter-spacing:0;text-transform:none;font-size:12px }
.settings-sections .settings-section >>> .v-btn__content { white-space:normal;line-height:1.25 }
.settings-sections .settings-section-active { color:var(--v-primary-base);border-color:var(--v-primary-base);background:rgba(154,205,50,.08) }

.companion-settings-button { min-height:40px; width:auto; border-radius:6px; letter-spacing:0 }
.settings-content { height:min(62vh,540px); overflow-y:auto; padding-top:12px !important }
.settings-actions { display:grid; grid-template-columns:minmax(0,1fr) auto; padding:10px 12px !important; gap:8px }
.settings-actions .v-btn { margin:0 !important; min-width:0; width:100%; min-height:44px; height:auto !important; padding:8px 12px; white-space:normal; letter-spacing:.02em; text-transform:none }
.settings-actions .v-btn:last-child { grid-column:2; min-width:88px }
@media (max-width:600px) { .settings-actions { padding:8px 5px !important } .settings-actions .v-btn { font-size:12px; padding-inline:8px } }
.settings-actions .v-btn >>> .v-btn__content { white-space: normal; line-height: 1.2 }
</style>

<style scoped>
.settings-accordion >>> .v-expansion-panel { border-bottom:1px solid #8885 }.settings-accordion >>> .v-expansion-panel-header { min-height:48px;font-weight:600;padding:12px }.companion-settings-button { width:44px !important;height:44px !important;min-width:44px !important;min-height:44px !important;padding:0 !important }.settings-button-label { display:none }
</style>
