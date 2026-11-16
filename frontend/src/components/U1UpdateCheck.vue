<template><div class="mt-3"><v-btn outlined :loading="busy" :disabled="busy" @click="check">{{ $u1t('Проверить обновление') }}</v-btn><v-alert v-if="result" dense class="mt-3" :type="result.checkFailed ? 'warning' : 'info'">{{ result.checkFailed ? $u1t('Не удалось проверить обновления. Повторите позже.') : result.updateAvailable ? $u1t('Доступна новая версия') + ': ' + result.latest : $u1t('Установлена последняя версия') }}</v-alert><v-alert v-if="error" dense type="warning">{{ error }}</v-alert></div></template>
<script lang="ts">
import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { checkCompanionVersion } from '@/utils/u1UpdateClient'
interface Info {installed:string;latest:string;updateAvailable:boolean;checkFailed:boolean;checking:boolean}
@Component
export default class U1UpdateCheck extends Vue {
  busy = false; error = ''; result: Info | null = null
  async check () {
    this.busy = true; this.error = ''; this.result = null
    try {
      const value = await checkCompanionVersion()
      this.result = value; this.$root.$emit('u1-update-checked', value)
    } catch { this.error = this.$u1t('Не удалось проверить обновления. Повторите позже.') } finally { this.busy = false }
  }
}
</script>
