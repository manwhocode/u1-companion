<template><v-alert v-if="info?.updateAvailable" dense type="info" class="mt-2 mb-1">{{ $u1t('Доступна новая версия') }}: U1 Companion {{ info.latest }}</v-alert></template>
<script lang="ts">
import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
import type { CompanionVersion } from '@/utils/u1UpdateClient'
import { rememberedCompanionVersion, rememberCompanionVersion, readInstalledCompanionVersion } from '@/utils/u1UpdateClient'
@Component
export default class U1UpdateNotice extends Vue {
  info: CompanionVersion | null = rememberedCompanionVersion()
  pending = false
  timer: ReturnType<typeof setInterval> | null = null
  onVisibility = () => { if (document.visibilityState === 'visible') void this.check() }
  onChecked (info: CompanionVersion) { this.info = rememberCompanionVersion(info) }
  mounted () { void this.checkInstalled(); void this.check(); this.timer = setInterval(() => { void this.check() }, 60000); document.addEventListener('visibilitychange', this.onVisibility); this.$root.$on('u1-update-checked', this.onChecked) }
  beforeDestroy () { if (this.timer) clearInterval(this.timer); document.removeEventListener('visibilitychange', this.onVisibility); this.$root.$off('u1-update-checked', this.onChecked) }
  async checkInstalled () {
    try { const installed = await readInstalledCompanionVersion(); if (this.info) this.onChecked({...this.info,installed}) } catch { /* Keep the known update if the local service is unavailable. */ }
  }
  async check () { if (this.pending) return; this.pending = true; try { this.onChecked(await u1DataRequest<CompanionVersion>('companion_info', {}, 12000)) } catch { /* Retry without blocking the printer UI. */ } finally { this.pending = false } }
}
</script>
