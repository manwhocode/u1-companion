<template><div :class="compact ? '' : 'mt-3'"><v-btn outlined :icon="compact" :class="compact ? 'main-gpt-button' : ''" :title="$u1t('Проверить обновление')" :aria-label="$u1t('Проверить обновление')" :loading="busy" :disabled="busy" @click="check"><v-icon v-if="compact">{{ updateIcon }}</v-icon><span v-else>{{ $u1t('Проверить обновление') }}</span></v-btn><template v-if="!compact"><v-alert v-if="result" dense class="mt-3" :type="result.checkFailed ? 'warning' : 'info'">{{ result.checkFailed ? $u1t('Не удалось проверить обновления. Повторите позже.') : result.updateAvailable ? $u1t('Доступна новая версия') + ': ' + result.latest : $u1t('Установлена последняя версия') }}</v-alert><v-alert v-if="error" dense type="warning">{{ error }}</v-alert></template><v-dialog v-else :value="!!(result || error)" max-width="520" scrollable content-class="u1-dialog u1-unified-dialog" @input="result = null; error = ''"><v-card><u1-dialog-close @close="result = null; error = ''" /><v-card-title>{{ $u1t('Проверить обновление') }}</v-card-title><v-card-text><v-alert v-if="result" dense class="mt-3" :type="result.checkFailed ? 'warning' : 'info'">{{ result.checkFailed ? $u1t('Не удалось проверить обновления. Повторите позже.') : result.updateAvailable ? $u1t('Доступна новая версия') + ': ' + result.latest : $u1t('Установлена последняя версия') }}</v-alert><v-alert v-if="error" dense type="warning">{{ error }}</v-alert><div class="installer-downloads"><v-btn outlined color="primary" :href="installerBase + 'U1-Companion-Setup.exe'" target="_blank" rel="noopener noreferrer">{{ $u1t('Скачать EXE') }}</v-btn><v-btn outlined :href="installerBase + 'U1-Companion-macOS.zip'" target="_blank" rel="noopener noreferrer">{{ $u1t('Скачать установщик macOS') }}</v-btn></div></v-card-text></v-card></v-dialog></div></template>
<script lang="ts">
import Vue from 'vue'
import { mdiUpdate } from '@mdi/js'
import { Component, Prop } from 'vue-property-decorator'
import { checkCompanionVersion } from '@/utils/u1UpdateClient'
interface Info {installed:string;latest:string;updateAvailable:boolean;checkFailed:boolean;checking:boolean}
@Component
export default class U1UpdateCheck extends Vue {
  @Prop({type:Boolean,default:false}) readonly compact!: boolean
  get installerBase () {
    const tag = this.result?.latest || 'v0.1.1-alpha.20'
    const safe = /^v?\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$/.test(tag) ? tag : 'v0.1.1-alpha.20'
    return 'https://github.com/manwhocode/u1-companion/releases/download/' + encodeURIComponent(safe) + '/'
  }
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

<style scoped>.installer-downloads {display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}.installer-downloads .v-btn {flex:1 1 190px;min-height:40px;height:auto;white-space:normal}.installer-downloads >>> .v-btn__content {white-space:normal;padding:8px 0}</style>
