<template><div :class="compact ? '' : 'mt-3'"><v-btn outlined :icon="compact" :class="compact ? 'main-gpt-button' : ''" :title="$u1t('Проверить обновление')" :aria-label="$u1t('Проверить обновление')" :loading="busy" :disabled="busy" @click="check"><v-icon v-if="compact">{{ updateIcon }}</v-icon><span v-else>{{ $u1t('Проверить обновление') }}</span></v-btn><template v-if="!compact"><v-alert v-if="result" dense class="mt-3" :type="result.checkFailed ? 'warning' : 'info'">{{ result.checkFailed ? $u1t('Не удалось проверить обновления. Повторите позже.') : result.updateAvailable ? $u1t('Доступна новая версия') + ': ' + result.latest : $u1t('Установлена последняя версия') }}</v-alert><v-alert v-if="error" dense type="warning">{{ error }}</v-alert></template><v-dialog v-else :value="!!(result || error)" max-width="520" scrollable content-class="u1-dialog u1-unified-dialog" @input="result = null; error = ''"><v-card><u1-dialog-close @close="result = null; error = ''" /><v-card-title>{{ $u1t('Проверить обновление') }}</v-card-title><v-card-text><v-alert v-if="result" dense class="mt-3" :type="result.checkFailed ? 'warning' : 'info'">{{ result.checkFailed ? $u1t('Не удалось проверить обновления. Повторите позже.') : result.updateAvailable ? $u1t('Доступна новая версия') + ': ' + result.latest : $u1t('Установлена последняя версия') }}</v-alert><v-alert v-if="error" dense type="warning">{{ error }}</v-alert></v-card-text></v-card></v-dialog></div></template>
<script lang="ts">
import Vue from 'vue'
import { mdiUpdate } from '@mdi/js'
import { Component, Prop } from 'vue-property-decorator'
import { checkCompanionVersion } from '@/utils/u1UpdateClient'
interface Info {installed:string;latest:string;updateAvailable:boolean;checkFailed:boolean;checking:boolean}
@Component
export default class U1UpdateCheck extends Vue {
  @Prop({default:false}) readonly compact!: boolean
  updateIcon = mdiUpdate
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

<style scoped>.main-gpt-button {width:44px!important;height:44px!important;min-width:44px!important;min-height:44px!important;border-radius:6px}</style>
