import { u1t } from '@/plugins/i18n'
export function isTemporaryRemoteOrigin () { return window.location.protocol === 'https:' && /^[a-z0-9-]+\.trycloudflare\.com$/.test(window.location.hostname) }
let checking:Promise<void>|null = null
let checkedUntil = 0
let expired = false
// Never follow API redirects into the PIN broker: polling an expired session
// would otherwise create a new login attempt for every pending read.
export async function ensureRemoteSession () {
  if (!isTemporaryRemoteOrigin()) return
  if (expired) throw new Error(u1t('Сессия внешнего доступа истекла. Откройте внешнюю ссылку заново.'))
  if (Date.now() < checkedUntil) return
  if (!checking) checking = (async () => {
    const response = await fetch('/u1-remote/check', {redirect:'manual',credentials:'same-origin',cache:'no-store'})
    if (response.type === 'opaqueredirect' || [0,401,403].includes(response.status)) {
      expired = true
      throw new Error(u1t('Сессия внешнего доступа истекла. Откройте внешнюю ссылку заново.'))
    }
    if (!response.ok) throw new Error(u1t('Сервис внешнего доступа не отвечает.'))
    checkedUntil = Date.now() + 5000
  })().finally(() => { checking = null })
  return checking
}
