<template><v-alert v-if="info?.updateAvailable" dense type="info" class="mt-2 mb-1">{{ $u1t('Доступна новая версия') }}: U1 Companion {{ info.latest }}</v-alert></template>
<script lang="ts">
import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
@Component
export default class U1UpdateNotice extends Vue {
  info: {latest:string;updateAvailable:boolean} | null = null
  dismissed = false
  timer: ReturnType<typeof setInterval> | null = null
  mounted () { void this.check(); this.timer = setInterval(() => { void this.check() }, 3600000) }
  beforeDestroy () { if (this.timer) clearInterval(this.timer) }
  async check () { try { this.info = await u1DataRequest('companion_info', {}, 12000) } catch { /* Optional update notice never blocks printer UI. */ } }
}
</script>
