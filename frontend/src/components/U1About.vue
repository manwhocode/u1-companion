<template><div><p>U1 Companion · {{ $u1t('Катушки, печать и обслуживание вашего U1.') }}</p><p v-if="info">{{ $u1t('Версия') }}: {{ info.installed }} · {{ info.latest }}</p><a href="https://github.com/manwhocode/u1-companion" target="_blank" rel="noopener noreferrer">GitHub · U1 Companion</a><p class="mt-3"><v-btn outlined @click="check">{{ $u1t('Обновить') }}</v-btn></p><v-alert v-if="error" type="warning" dense>{{ error }}</v-alert></div></template>
<script lang="ts">
import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { u1DataRequest } from '@/utils/u1DataClient'
@Component
export default class U1About extends Vue {
  info: {installed:string;latest:string} | null = null
  error = ''
  mounted () { void this.check() }
  async check () { try { this.info = await u1DataRequest('companion_info'); this.error = '' } catch (e) { this.error = String(e) } }
}
</script>
