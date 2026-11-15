<template>
<v-btn class="u1-close-button" outlined color="primary" :aria-label="$u1t('Закрыть')" @click="$emit('close')">{{ $u1t("Закрыть") }}</v-btn>
</template>
<script lang="ts">
import Vue from 'vue'
export default Vue.extend({ name: 'U1DialogClose' })
</script>
<style>
.u1-unified-dialog > .v-card { position:relative }
.u1-unified-dialog .u1-close-button.v-btn { position:absolute; top:12px; right:12px; z-index:8; width:96px !important; min-width:96px !important; max-width:96px !important; height:36px !important; min-height:36px !important; padding:0 10px !important; margin:0 !important; border-radius:6px; font-size:12px !important; letter-spacing:.035em; pointer-events:auto }
.u1-unified-dialog .u1-close-button .v-btn__content { white-space:nowrap !important; opacity:1 }
.u1-unified-dialog > .v-card > .v-card__title { min-height:60px; padding-right:124px !important; line-height:1.3; word-break:normal }
.u1-unified-dialog > .v-card > h2 { min-height:40px; padding-right:112px; line-height:1.3 }
.u1-unified-dialog > .v-card > .v-card__actions { flex-wrap:wrap; gap:6px }
</style>
