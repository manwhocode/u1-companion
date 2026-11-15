<template>
<div>
  <v-btn v-if="!inline && !hideLauncher" small outlined :aria-label="$u1t('Профили печати — инструкция и статус')" @click="open">{{ $u1t("Профили печати") }}</v-btn>
  <u1-settings-content :inline="inline" v-model="opened" content-class="u1-dialog u1-unified-dialog" max-width="620" scrollable>
    <v-card :flat="inline">
      <u1-dialog-close v-if="!inline" @close="opened = false" />
      <v-card-title>{{ $u1t("Температуры и K") }}<v-spacer /></v-card-title>
      <v-card-text>
        <p>{{ $u1t("Укажите температуру сопла и стола в «Моих цветах». Катушка по умолчанию наследует значения своей основы. В «Моих катушках» можно задать свои температуры сопла и стола; пустое поле возвращает наследование. Назначьте физическую катушку нужной головке перед печатью.") }}</p>
        <p>{{ $u1t("Пустые температуры остаются из слайсера. Заданная температура сопла используется для первого и следующих слоёв; температуры очистки и предварительного прогрева, выключение нагрева и ручное управление сохраняются.") }}</p>
        <p>{{ $u1t("Сохранённый K применяется к нужной головке после подготовки к печати. Если включена штатная калибровка перед печатью, K управляет сам U1.") }}</p>
        <p>{{ $u1t("Стол общий: при разных заданных температурах используемых катушек запуск блокируется. Снимок настроек фиксируется при старте; правки базы относятся к следующей печати.") }}</p>
        <p>{{ $u1t("Поддерживается G-code Snapmaker Orca и OrcaSlicer с сохранёнными настройками. Исходный файл не переписывается. Восстановление после отключения питания использует штатное сохранённое состояние U1.") }}</p>
        <v-alert v-if="message" dense :type="failed ? 'warning' : 'info'">{{ message }}</v-alert>
        <template v-if="status">
          <p>{{ $u1t("Модуль подключён ·") }} {{ phase }}</p>
          <p v-for="(profile, head) in status.heads" :key="head">{{ $u1t("Головка") }} {{ Number(head) + 1 }}{{ $u1t(": сопло") }} {{ profile.nozzleTemperature ?? $u1t("из слайсера") }} {{ $u1t("· стол") }} {{ profile.bedTemperature ?? $u1t("из слайсера") }} · K {{ status.nativeCalibration ? $u1t("штатная калибровка U1") : (profile.pressureAdvance ?? $u1t("штатный")) }}</p>
        </template>
        <v-btn small outlined :loading="loading" @click="refresh">{{ $u1t("Обновить статус") }}</v-btn>
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
import { httpClientActions as http } from '@/api/httpClientActions'

interface ProfileStatus { version: number; nativeCalibration?: boolean; state: string; message: string; heads: Record<string, { nozzleTemperature?: number; bedTemperature?: number; pressureAdvance?: number }> }

@Component({components:{U1SettingsContent}})
export default class U1PrintProfiles extends Vue {
  @Prop({default:false,type:Boolean}) readonly inline!: boolean
  @Prop({default:false,type:Boolean}) readonly hideLauncher!: boolean
  mounted () { if (this.inline) this.open() }
  opened = false
  loading = false
  status: ProfileStatus | null = null
  failed = false
  message = ''
  get phase () { return ({ ready: u1t("ожидание печати"), prepared: u1t("профили подготовлены"), active: u1t("профили применяются"), finished: u1t("печать завершена"), error: u1t("проверьте сообщение"), 'stock-recovery': u1t("штатное восстановление") } as Record<string, string>)[this.status?.state || ''] || this.status?.state }
  async open () { this.opened = true; await this.refresh() }
  async refresh () {
    if (this.loading) return
    this.loading = true
    try {
      const response = await http.get<{ result: { status: { u1_filament_profiles?: ProfileStatus } } }>('/printer/objects/query?u1_filament_profiles')
      const status = response.data.result.status.u1_filament_profiles
      if (!status || status.version !== 1) throw new Error(u1t("Модуль профилей не подключён. Автоматическое применение не подтверждено."))
      this.status = status
      this.failed = status.state === 'error'
      this.message = status.message
    } catch (error) { this.status = null; this.failed = true; this.message = String(error) } finally { this.loading = false }
  }
}
</script>
