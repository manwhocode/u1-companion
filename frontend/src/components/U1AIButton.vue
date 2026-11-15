<template>
<v-btn fixed bottom right fab small color="primary" class="u1-ai-shortcut" @click="open" :to="{ name: 'u1_filaments', query: { gpt: '1' } }" :aria-label="$u1t('Открыть управление через GPT')" :title="$u1t('Управление через GPT')"><v-icon>{{ icon }}</v-icon></v-btn>
</template>
<script lang="ts">
import Vue from 'vue'
import { mdiChatProcessingOutline } from '@mdi/js'
export default Vue.extend({ data: () => ({ icon: mdiChatProcessingOutline }), methods: { open () { window.dispatchEvent(new Event('u1-open-gpt')) } } })
</script>
<style scoped>.u1-ai-shortcut { bottom:16px !important;right:16px !important;z-index:150 }</style>
