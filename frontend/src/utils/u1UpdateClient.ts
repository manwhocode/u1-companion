import axios from 'axios'
import { u1t } from '@/plugins/i18n'
import { gt, valid } from 'semver'

export interface CompanionVersion { installed: string; latest: string; updateAvailable: boolean; checkFailed: boolean; checking: boolean }

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
  return {installed,latest,updateAvailable,checkFailed:false,checking:false}
}
