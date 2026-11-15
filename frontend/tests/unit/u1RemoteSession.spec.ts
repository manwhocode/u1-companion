import { describe, it, expect, vi, beforeEach } from 'vitest'
vi.mock('@/plugins/i18n', () => ({u1t:(x:string)=>x}))
describe('remote session checks', () => {
 beforeEach(() => { vi.resetModules(); vi.unstubAllGlobals(); vi.stubGlobal('window',{location:{protocol:'https:',hostname:'test.trycloudflare.com'}}) })
 it('shares concurrent checks without following login redirects',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,status:200,type:'basic'});vi.stubGlobal('fetch',fetch)
  const {ensureRemoteSession}=await import('@/utils/u1RemoteSession')
  await Promise.all([ensureRemoteSession(),ensureRemoteSession(),ensureRemoteSession()]);expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch.mock.calls[0][1]).toMatchObject({redirect:'manual',credentials:'same-origin'})
 })
 it('stops repeated broker requests after expiry',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:false,status:0,type:'opaqueredirect'});vi.stubGlobal('fetch',fetch)
  const {ensureRemoteSession}=await import('@/utils/u1RemoteSession')
  await expect(ensureRemoteSession()).rejects.toThrow('Сессия внешнего доступа')
  await expect(ensureRemoteSession()).rejects.toThrow('Сессия внешнего доступа');expect(fetch).toHaveBeenCalledTimes(1)
 })
 it('does not touch local printer access',async()=>{
  vi.stubGlobal('window',{location:{protocol:'http:',hostname:'192.168.1.100'}});const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
  const {ensureRemoteSession}=await import('@/utils/u1RemoteSession');await ensureRemoteSession();expect(fetch).not.toHaveBeenCalled()
 })
})
