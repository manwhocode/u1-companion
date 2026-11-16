<template><v-alert v-if="info?.updateAvailable" dense type="info" class="mt-2 mb-1">{{ $u1t('Доступна новая версия') }}: U1 Companion {{ info.latest }}</v-alert></template>
<script lang="ts">
import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
@Component
export default class U1UpdateNotice extends Vue {
  info: {latest:string;updateAvailable:boolean} | null = null
  pending = false
  timer: ReturnType<typeof setInterval> | null = null
  onVisibility = () => { if (document.visibilityState === 'visible') void this.check() }
  onChecked (info: {latest:string;updateAvailable:boolean}) { this.info = info }
  mounted () { void this.check(); this.timer = setInterval(() => { void this.check() }, 60000); document.addEventListener('visibilitychange', this.onVisibility); this.$root.$on('u1-update-checked', this.onChecked) }
  beforeDestroy () { if (this.timer) clearInterval(this.timer); document.removeEventListener('visibilitychange', this.onVisibility); this.$root.$off('u1-update-checked', this.onChecked) }
  async check () { if (this.pending) return; this.pending = true; try { this.info = await u1DataRequest('companion_info', {}, 12000) } catch { /* Retry without blocking the printer UI. */ } finally { this.pending = false } }
}
</script>
