import { beforeEach, expect, it, vi } from 'vitest'
import axios from 'axios'
import { checkCompanionVersion, rememberedCompanionVersion, rememberCompanionVersion } from './u1UpdateClient'

vi.mock('axios', () => ({default:{get:vi.fn()}}))
vi.mock('@/plugins/i18n', () => ({u1t:(text:string) => text}))
beforeEach(() => { vi.mocked(axios.get).mockReset(); localStorage.clear() })

it('checks public metadata directly without queuing a printer request', async () => {
  vi.mocked(axios.get).mockResolvedValueOnce({data:{version:'v0.1.1-alpha.13'}}).mockResolvedValueOnce({data:'VERSION=v0.1.1-alpha.15\n'})
  expect(await checkCompanionVersion()).toMatchObject({updateAvailable:true,latest:'v0.1.1-alpha.15'})
  expect(axios.get).toHaveBeenCalledTimes(2)
  expect(vi.mocked(axios.get).mock.calls[0][0]).toBe('/u1-filaments-ui/addon-status.json')
  expect(vi.mocked(axios.get).mock.calls[1][0]).toBe('https://raw.githubusercontent.com/manwhocode/u1-companion/main/install.sh')
  expect(rememberedCompanionVersion()).toMatchObject({installed:'v0.1.1-alpha.13',latest:'v0.1.1-alpha.15',updateAvailable:true})
})

it('retains a known update through reload and an empty or stale backend cache until it is installed', () => {
  const known = {installed:'v0.1.1-alpha.17',latest:'v0.1.1-alpha.18',updateAvailable:true,checking:false,checkFailed:false}
  rememberCompanionVersion(known)
  // A new page reads durable browser storage before its first service response.
  expect(rememberedCompanionVersion()).toMatchObject({updateAvailable:true,latest:known.latest})
  expect(rememberCompanionVersion({...known,latest:known.installed,updateAvailable:false,checking:true})).toMatchObject({updateAvailable:true,latest:known.latest})
  expect(rememberCompanionVersion({...known,checkFailed:true})).toMatchObject({updateAvailable:true})
  expect(rememberCompanionVersion({...known,installed:known.latest})).toMatchObject({updateAvailable:false})
  expect(rememberedCompanionVersion()?.updateAvailable).toBe(false)
})

it('ignores corrupt stored version data', () => {
  localStorage.setItem('u1-companion-update-v1','{"installed":"broken","latest":"latest"}')
  expect(rememberedCompanionVersion()).toBeNull()
})

it('does not offer a downgrade and rejects an invalid version response', async () => {
  vi.mocked(axios.get).mockResolvedValueOnce({data:{version:'v0.1.1-alpha.15'}}).mockResolvedValueOnce({data:'VERSION=v0.1.1-alpha.14\n'})
  expect((await checkCompanionVersion()).updateAvailable).toBe(false)
  vi.mocked(axios.get).mockResolvedValueOnce({data:{version:'v0.1.1-alpha.15'}}).mockResolvedValueOnce({data:'<html>connection failed</html>'})
  await expect(checkCompanionVersion()).rejects.toThrow()
})
