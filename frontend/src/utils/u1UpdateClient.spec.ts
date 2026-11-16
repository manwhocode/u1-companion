import { beforeEach, expect, it, vi } from 'vitest'
import axios from 'axios'
import { checkCompanionVersion } from './u1UpdateClient'

vi.mock('axios', () => ({default:{get:vi.fn()}}))
vi.mock('@/plugins/i18n', () => ({u1t:(text:string) => text}))
beforeEach(() => vi.mocked(axios.get).mockReset())

it('checks public metadata directly without queuing a printer request', async () => {
  vi.mocked(axios.get).mockResolvedValueOnce({data:{version:'v0.1.1-alpha.13'}}).mockResolvedValueOnce({data:'VERSION=v0.1.1-alpha.15\n'})
  expect(await checkCompanionVersion()).toMatchObject({updateAvailable:true,latest:'v0.1.1-alpha.15'})
  expect(axios.get).toHaveBeenCalledTimes(2)
  expect(vi.mocked(axios.get).mock.calls[0][0]).toBe('/u1-filaments-ui/addon-status.json')
  expect(vi.mocked(axios.get).mock.calls[1][0]).toBe('https://raw.githubusercontent.com/manwhocode/u1-companion/main/install.sh')
})

it('does not offer a downgrade and rejects an invalid version response', async () => {
  vi.mocked(axios.get).mockResolvedValueOnce({data:{version:'v0.1.1-alpha.15'}}).mockResolvedValueOnce({data:'VERSION=v0.1.1-alpha.14\n'})
  expect((await checkCompanionVersion()).updateAvailable).toBe(false)
  vi.mocked(axios.get).mockResolvedValueOnce({data:{version:'v0.1.1-alpha.15'}}).mockResolvedValueOnce({data:'<html>connection failed</html>'})
  await expect(checkCompanionVersion()).rejects.toThrow()
})
