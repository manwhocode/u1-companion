<template>
  <v-card tag="footer" outlined class="u1-support-panel">
    <h2>{{ $u1t("Поддержать разработку") }}</h2>
    <p>{{ $u1t("Ваша поддержка помогает мне развивать U1 Companion, добавлять новые функции и исправлять ошибки. Спасибо!") }}</p>
    <div class="support-actions">
      <div class="support-donation">
        <a href="https://www.buymeacoffee.com/snapIV"><picture><source :srcset="coffeeButton" type="image/svg+xml"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=snapIV&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff" /></picture></a>
      </div>
      <nav :aria-label="$u1t('Ссылки автора')" class="support-socials">
        <v-btn small outlined href="https://www.instagram.com/3dlabstorex/" target="_blank" rel="noopener noreferrer"><v-icon left small>{{ instagramIcon }}</v-icon>Instagram</v-btn>
        <v-btn small outlined href="https://makerworld.com/ru/@user_110109506" target="_blank" rel="noopener noreferrer"><v-icon left small>{{ modelsIcon }}</v-icon>MakerWorld</v-btn>
        <v-btn small outlined href="https://space.snapmaker.com/en/creator/75133?tab=models" target="_blank" rel="noopener noreferrer"><v-icon left small>{{ printerIcon }}</v-icon>Snapmaker Space</v-btn>
      </nav>
    </div>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { mdiInstagram, mdiCubeOutline, mdiPrinter3dNozzleOutline } from '@mdi/js'
import coffeeButton from '@/assets/buy-me-a-coffee.svg'

@Component
export default class U1Support extends Vue {
  coffeeButton = coffeeButton
  instagramIcon = mdiInstagram
  modelsIcon = mdiCubeOutline
  printerIcon = mdiPrinter3dNozzleOutline
}
</script>

<style scoped>
.u1-support-panel { margin-top:12px; padding:14px 16px; border-radius:16px; min-width:0 }
.u1-support-panel h2 { margin:0 0 6px; font-size:1rem }
.u1-support-panel p { margin:0 0 10px; font-size:.875rem; line-height:1.5; opacity:.8 }
.support-actions, .support-socials { display:flex; flex-wrap:wrap; align-items:center; gap:8px }
.support-actions { column-gap:16px }
.support-donation a { display:inline-flex; vertical-align:middle; max-width:100% }
.support-donation img { display:block; height:44px; width:auto; max-width:100%; object-fit:contain }
.support-socials .v-btn { margin:0; min-height:36px; letter-spacing:0; text-transform:none }
@media(max-width:600px) {
  .u1-support-panel { padding:12px 10px }
  .support-socials { width:100%; gap:6px }
  .support-socials .v-btn { flex:1 1 auto; padding:0 9px; font-size:12px }
}
</style>
