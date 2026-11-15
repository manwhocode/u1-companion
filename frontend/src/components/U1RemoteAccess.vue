<template><section class="remote-access">
<p>{{ $u1t('Код создаётся на принтере. Почта и аккаунт Cloudflare не нужны.') }}</p>
<p>{{ $u1t('Временная ссылка меняется после перезапуска туннеля.') }}</p>
<template v-if="local">
<v-text-field v-if="code" :value="code" :label="$u1t('Код доступа')" :type="showCode ? 'text' : 'password'" readonly outlined dense autocomplete="off"><template #append><v-btn small text class="reveal-code" :aria-label="showCode ? $u1t('Скрыть код') : $u1t('Показать код')" @click="showCode = !showCode">{{ showCode ? $u1t('Скрыть код') : $u1t('Показать код') }}</v-btn></template></v-text-field>
<p v-if="!code" class="text-caption">{{ $u1t('Код доступен только в локальной сети принтера. Новый код отключит все внешние сеансы.') }}</p>
<div class="remote-actions"><v-btn v-if="code" outlined :disabled="busy" @click="copy(code)">{{ $u1t('Копировать код') }}</v-btn><v-btn outlined :disabled="busy" @click="rotate">{{ $u1t('Создать новый код') }}</v-btn></div>
<v-alert v-if="rotateConfirm" type="warning" outlined dense class="mt-3"><p>{{ $u1t('Код доступен только в локальной сети принтера. Новый код отключит все внешние сеансы.') }}</p><div class="remote-actions"><v-btn color="primary" :disabled="busy" @click="run('rotate')">{{ $u1t('Подтвердить') }}</v-btn><v-btn outlined :disabled="busy" @click="rotateConfirm = false">{{ $u1t('Отмена') }}</v-btn></div></v-alert>
</template>
<v-alert v-if="message" :type="copied ? 'success' : 'error'" dense class="mt-3">{{ message }}</v-alert>
<v-alert v-if="state" :type="state.phase === 'running' ? 'success' : 'info'" dense class="mt-3">{{ status }}</v-alert>
<div class="remote-actions"><v-btn color="primary" :disabled="busy || active || !state?.hasCode" :loading="busy" @click="run('start')">{{ $u1t('Включить') }}</v-btn><v-btn outlined :disabled="busy || !active" @click="run('stop')">{{ $u1t('Отключить') }}</v-btn><v-btn outlined :disabled="busy" @click="load">{{ $u1t('Обновить') }}</v-btn><v-btn v-if="!local" outlined @click="logout">{{ $u1t('Выйти') }}</v-btn></div>
<template v-if="link"><p class="remote-link">{{ link }}</p><div class="remote-actions"><v-btn outlined :href="link" target="_blank" rel="noopener noreferrer">{{ $u1t('Открыть') }}</v-btn><v-btn outlined @click="copy(link)">{{ $u1t('Копировать ссылку') }}</v-btn></div></template>
<p v-else>{{ $u1t('Ссылка появится после подключения.') }}</p>
</section></template>
<script lang="ts">
import Vue from 'vue'
import { Component } from 'vue-property-decorator'
import { copyU1Text } from '@/utils/u1Clipboard'
import { aiRequest } from '@/utils/u1AIClient'
import { isTemporaryRemoteOrigin } from '@/utils/u1RemoteSession'
import { u1t } from '@/plugins/i18n'
interface RemoteState { phase:string; url:string; hasCode:boolean; enabled:boolean }
@Component
export default class U1RemoteAccess extends Vue {
 code = ''; showCode = false; rotateConfirm = false; copied = false; state:RemoteState|null = null; busy = false; message = ''; timer:ReturnType<typeof setInterval>|null = null; loading = false
 get local () { return !isTemporaryRemoteOrigin() }
 get active () { return !!this.state && ['starting','running'].includes(this.state.phase) }
 get link () { return this.state?.phase === 'running' && /^https:\/\/[a-z0-9-]+\.trycloudflare\.com$/.test(this.state.url) ? this.state.url + '/u1-remote/open' : '' }
 get status () { return u1t(this.state?.phase === 'running' ? 'Подключено' : this.state?.phase === 'starting' ? 'Подключение…' : this.state?.phase === 'error' ? 'Ошибка' : 'Выключен') }
 mounted () { void this.load(); this.timer = setInterval(() => { if (!this.busy) void this.load() },5000) }
 beforeDestroy () { if (this.timer) clearInterval(this.timer) }
 async load () { if (this.loading) return; this.loading = true; try { this.state = await aiRequest<RemoteState>('remote/state'); if (this.local && !this.code && this.state.hasCode) this.code = (await aiRequest<{code:string}>('remote/code')).code } catch { this.message = u1t('Сервис внешнего доступа не отвечает.') } finally { this.loading = false } }
 async run (action:string) { if (this.busy) return; this.busy = true; this.message = ''; this.copied = false; try { this.state = await aiRequest<RemoteState>('remote/command',{action,confirmed:true}); if (action === 'rotate') this.code = (await aiRequest<{code:string}>('remote/code')).code } catch { this.message = u1t('Не удалось выполнить действие. Обновите статус перед повтором.') } finally { this.busy = false; this.rotateConfirm = false; this.showCode = false } }
 rotate () { if (this.code) this.rotateConfirm = true; else void this.run('rotate') }
 async copy (value:string) { this.copied = false; this.message = ''; try { await copyU1Text(value,this.$el as HTMLElement); this.copied = true; this.message = u1t('Скопировано в буфер обмена.') } catch { if (value === this.code) this.showCode = true; this.message = u1t('Не удалось выполнить действие. Обновите статус перед повтором.') } }
 async logout () { try { const response = await fetch('/u1-remote/logout',{method:'POST',credentials:'same-origin'}); if (!response.ok) throw new Error(); window.location.assign('/u1-remote/login') } catch { this.message = u1t('Не удалось выполнить действие. Обновите статус перед повтором.') } }
}
</script><style scoped>.remote-actions{display:flex;flex-wrap:wrap;gap:6px}.remote-actions .v-btn{margin:0;letter-spacing:0;text-transform:none}.reveal-code{font-size:12px!important;text-transform:none;letter-spacing:0;padding:0 4px!important;height:24px!important;min-width:0!important}.remote-link{overflow-wrap:anywhere;margin-top:12px}</style>
