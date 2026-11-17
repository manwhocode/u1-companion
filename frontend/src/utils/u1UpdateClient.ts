import axios from 'axios'
import { u1t } from '@/plugins/i18n'
import { gt, valid } from 'semver'

export interface CompanionVersion { installed: string; latest: string; updateAvailable: boolean; checkFailed: boolean; checking: boolean }
const CACHE_KEY = 'u1-companion-update-v1'

// Keep a known update across page reloads and temporary service/network failures.
// Only public version numbers are stored, scoped to this printer's browser origin.
export function rememberedCompanionVersion (): CompanionVersion | null {
  try {
    const value = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null') as CompanionVersion | null
    if (!value || typeof value.installed !== 'string' || typeof value.latest !== 'string' || !valid(value.installed) || !valid(value.latest)) return null
    return {...value, updateAvailable:gt(value.latest,value.installed), checking:false}
  } catch { return null }
}

export function rememberCompanionVersion (value: CompanionVersion, authoritative = false): CompanionVersion {
  const previous = rememberedCompanionVersion()
  const latest = !authoritative && previous && gt(previous.latest,value.latest) ? previous.latest : value.latest
  const result = {...value,latest,updateAvailable:gt(latest,value.installed)}
  try { localStorage.setItem(CACHE_KEY,JSON.stringify(result)) } catch { /* Storage can be disabled. */ }
  return result
}

export async function readInstalledCompanionVersion (): Promise<string> {
  const response = await axios.get<{version:string}>('/u1-filaments-ui/addon-status.json', {baseURL:window.location.origin,timeout:15000,params:{check:Date.now()}})
  if (!valid(response.data.version)) throw new Error('Invalid installed version')
  return response.data.version
}

// A version check reads public metadata; it must not enter the printer command queue.
export async function checkCompanionVersion (): Promise<CompanionVersion> {
  const [installedResponse, releaseResponse] = await Promise.all([
    axios.get<{version:string}>('/u1-filaments-ui/addon-status.json', {baseURL:window.location.origin,timeout:15000,params:{check:Date.now()}}),
    axios.get<string>('https://raw.githubusercontent.com/manwhocode/u1-companion/main/install.sh', {timeout:15000,responseType:'text',params:{check:Date.now()}})
  ])
  const installed = installedResponse.data.version
  const latest = /^VERSION=(v[0-9A-Za-z.-]+)\r?$/m.exec(releaseResponse.data)?.[1]
  if (!valid(installed) || !latest || !valid(latest)) throw new Error(u1t('Не удалось проверить обновления. Повторите позже.'))
  const updateAvailable = gt(latest,installed)
  return rememberCompanionVersion({installed,latest,updateAvailable,checkFailed:false,checking:false},true)
}
