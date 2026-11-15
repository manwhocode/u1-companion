import { ensureRemoteSession } from '@/utils/u1RemoteSession'
import { u1t } from '@/plugins/i18n'
import axios from 'axios'
import { u1DataRequest } from '@/utils/u1DataClient'

let session = ''
let expires = 0
let acquiring: Promise<void> | null = null
async function authorize () {
  if (session && Date.now() / 1000 < expires - 30) return
  if (!acquiring) acquiring = (async () => {
    const value = /^[a-z0-9-]+\.trycloudflare\.com$/.test(window.location.hostname) && window.location.protocol === 'https:'
      ? (await axios.post<{session:string;expires:number}>('/u1-remote/session', {}, {baseURL:window.location.origin,timeout:15000})).data
      : await u1DataRequest<{session: string; expires: number}>('ai_session', { origin: window.location.origin }, 15000)
    session = value.session; expires = value.expires
  })().finally(() => { acquiring = null })
  await acquiring
}

export async function aiRequest<T> (path: string, payload?: unknown): Promise<T> {
  if (!/^[a-z/-]+(?:[0-9a-f-]{36})?$/.test(path)) throw new Error(u1t("Неизвестный маршрут AI."))
  await ensureRemoteSession()
  await authorize()
  try {
    const result = await axios.request<{ok: boolean; value: T; error?: string}>({
      url: '/u1-ai/api/' + path, baseURL: window.location.origin,
      method: payload === undefined ? 'GET' : 'POST', data: payload, timeout: 15000,
      headers: { 'Content-Type': 'application/json', 'X-U1-AI-Session': session }
    })
    if (!result.data.ok) throw new Error(result.data.error || u1t("Запрос AI не выполнен."))
    return result.data.value
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 403) { session = ''; expires = 0 }
      const message = error.response?.data?.error
      throw new Error(typeof message === 'string' ? message : u1t("Нет подтверждённого ответа AI. Команда автоматически не повторяется."))
    }
    throw error
  }
}
