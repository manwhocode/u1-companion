<template><div v-if="inline" class="u1-inline-settings-content"><slot /></div><v-dialog v-else :value="value" v-bind="$attrs" @input="$emit('input', $event)"><slot /></v-dialog></template>
<script lang="ts">
import Vue from 'vue'
export default Vue.extend({ inheritAttrs:false, props:{ inline:Boolean, value:Boolean } })
</script>
<style scoped>.u1-inline-settings-content >>> .v-card { background:transparent;box-shadow:none }.u1-inline-settings-content >>> .v-card__text { padding:0 }.u1-inline-settings-content >>> .v-card__title { padding:8px 0;font-size:16px }</style>
