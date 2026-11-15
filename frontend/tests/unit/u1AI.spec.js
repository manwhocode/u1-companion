import { afterEach, expect, it, vi } from 'vitest'
import U1AI from '@/views/U1AI.vue'
import { aiRequest } from '@/utils/u1AIClient'
vi.mock('@/utils/u1AIClient', () => ({ aiRequest: vi.fn() }))
afterEach(() => vi.mocked(aiRequest).mockReset())

it('opening confirmation never sends an action and requires a separate checkbox', async () => {
  const vm = new U1AI()
  vm.ask({ actionId: 'a', summary: 'Pause', expires: Date.now() / 1000 + 120 })
  expect(vm.confirmOpen).toBe(true); expect(vm.confirmed).toBe(false)
  await vm.confirm(); expect(aiRequest).not.toHaveBeenCalled(); vm.$destroy()
})
it('closing or editing a chat is independent from printer controls', () => {
  const vm = new U1AI(); vm.draft = 'Keep my draft'; vm.newChat()
  expect(vm.draft).toBe('Keep my draft'); expect(aiRequest).not.toHaveBeenCalled(); vm.$destroy()
})
it('loading public state never fills an API-key input or resets a visible error', async () => {
  const vm = new U1AI(); vm.error = 'command result unknown'
  vi.mocked(aiRequest).mockResolvedValue({ settings: { hasKey: true }, chats: [], usage: {}, audit: [], printer: {} })
  await vm.load(); expect(vm.key).toBe(''); expect(vm.error).toBe('command result unknown'); vm.$destroy()
})
it('saving settings clears the key from memory and does not send public hasKey metadata', async () => {
  const vm = new U1AI(); vm.key = 'unit-test-key'; vm.edit.hasKey = true
  vi.mocked(aiRequest).mockResolvedValue({ revision: 'new', hasKey: true })
  await vm.save(false)
  expect(aiRequest.mock.calls[0][0]).toBe('settings')
  expect(aiRequest.mock.calls[0][1].apiKey).toBe('unit-test-key')
  expect(aiRequest.mock.calls[0][1]).not.toHaveProperty('hasKey')
  expect(vm.key).toBe(''); vm.$destroy()
})

it('shows model loading failures next to the model controls and releases loading state', async () => {
 const vm = new U1AI(); vi.mocked(aiRequest).mockResolvedValue({job:'test-job'})
 vm.wait = vi.fn().mockRejectedValue(new Error('OpenAI отклонил API-ключ.'))
 await vm.loadModels(); expect(vm.modelError).toBe('OpenAI отклонил API-ключ.')
 expect(vm.modelNotice).toBe(''); expect(vm.modelsLoading).toBe(false); expect(vm.busy).toBe(false); vm.$destroy()
})
it('reports an empty model list instead of silently showing no options', async () => {
 const vm = new U1AI(); vi.mocked(aiRequest).mockResolvedValue({job:'test-job'}); vm.wait=vi.fn().mockResolvedValue({models:[]})
 await vm.loadModels(); expect(vm.modelNotice).toContain('пустой список'); vm.$destroy()
})
it('deletes only a confirmed selected chat and clears it from the visible pane', async () => {
 const vm = new U1AI(); vm.chat='one'; vm.messages=[{role:'user',content:'old'}]; vm.deleteTarget={id:'one',title:'old'}
 vi.mocked(aiRequest).mockResolvedValue({settings:{},chats:[],usage:{},audit:[],printer:{}})
 await vm.deleteChat()
 expect(aiRequest).toHaveBeenCalledWith('chats/delete',{id:'one',confirmed:true})
 expect(vm.chat).not.toBe('one'); expect(vm.messages).toEqual([]); expect(vm.deleteTarget).toBeNull(); vm.$destroy()
})
it('never renders the settings form in the chat, only in the settings instance', () => {
 const find = (v, cls) => !!v && ((v.data?.staticClass || '').split(' ').includes(cls) || (v.children || []).some(c => find(c,cls)))
 const chat = new U1AI({propsData:{settingsOnly:false}})
 expect(find(chat._render(), 'ai-settings-only')).toBe(false)
 const settings = new U1AI({propsData:{settingsOnly:true}})
 expect(find(settings._render(), 'ai-settings-only')).toBe(true)
 expect(find(settings._render(), 'ai-chat-layout')).toBe(false)
 chat.$destroy(); settings.$destroy()
})

it('Enter sends once, Shift+Enter and IME preserve typing', () => {
 const vm=new U1AI();vm.config.enabled=true;vm.draft='hello';vm.send=vi.fn()
 for(const e of [{key:'Enter',shiftKey:true},{key:'Enter',isComposing:true}])vm.composerKey({...e,preventDefault:vi.fn()})
 expect(vm.send).not.toHaveBeenCalled()
 const preventDefault=vi.fn();vm.composerKey({key:'Enter',preventDefault});expect(preventDefault).toHaveBeenCalled();expect(vm.send).toHaveBeenCalledTimes(1);vm.$destroy()
})
