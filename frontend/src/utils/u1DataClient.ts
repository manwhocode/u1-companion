import { localizeU1Result } from '@/utils/u1LocaleMessages'
import { u1t } from '@/plugins/i18n'
import axios from 'axios'
import { v4 as uuid } from 'uuid'
import { httpClientActions as http } from '@/api/httpClientActions'

interface Control { version: number; state: string; revision: string }
interface Result<T> { ok: boolean; value?: T; error?: string }

let controlPending: Promise<Control | null> | null = null
async function fetchControl () {
  try {
    return (await http.serverDatabaseItemGet<Control>('fluidd', 'u1_data_storage_v1')).data.result.value
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null
    throw error
  }
}

// Share only in-flight reads. Revision checks must still fetch fresh control
// after the item completes, so restores/imports cannot return mixed versions.
async function control () {
  if (!controlPending) controlPending = fetchControl().finally(() => { controlPending = null })
  return controlPending
}
const itemReads = new Map<string, Promise<unknown>>()
export function readU1Item<T> (key: string): Promise<Awaited<ReturnType<typeof fetchU1Item<T>>>> {
  const pending = itemReads.get(key)
  if (pending) return pending as Promise<Awaited<ReturnType<typeof fetchU1Item<T>>>>
  const request = fetchU1Item<T>(key).finally(() => { itemReads.delete(key) })
  itemReads.set(key, request)
  return request
}
async function fetchU1Item<T> (key: string) {
  const before = await control()
  if (before && before.state !== 'ready') throw new Error(u1t("Восстановление данных ещё выполняется. Повторите чтение позже."))
  const result = await http.serverDatabaseItemGet<T>('fluidd', key)
  const after = await control()
  if (before?.revision !== after?.revision) throw new Error(u1t("Данные обновились во время чтения. Обновите список."))
  return result
}

export async function u1DataRequest<T> (operation: string, payload: unknown = {}, timeoutMs = 90000): Promise<T> {
  const state = await control()
  if (!state || state.version !== 1 || state.state !== 'ready') {
    throw new Error(u1t("Сервис хранения данных ещё не готов. Повторите после восстановления соединения."))
  }
  const id = uuid()
  await http.serverDatabaseItemPost('u1_addon_requests', id, { operation, payload })
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const response = await http.serverDatabaseItemGet<Result<T>>('u1_addon_results', id)
      const result = response.data.result.value
      if (!result.ok) throw new Error(u1t(result.error) || u1t("Операция с данными не выполнена."))
      return localizeU1Result(result.value as T, u1t)
    } catch (error) {
      if (!axios.isAxiosError(error)) throw error
      if (error.response && error.response.status !== 404) throw error
    }
    await new Promise(resolve => setTimeout(resolve, 650))
  }
  throw new Error(u1t("Сервис пока не ответил. Обновите данные перед повторной записью. Запрос ") + id)
}
