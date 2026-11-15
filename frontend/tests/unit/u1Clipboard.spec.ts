import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { copyU1Text } from '@/utils/u1Clipboard'
beforeEach(()=> { document.body.innerHTML='';vi.stubGlobal('isSecureContext',false) })
afterEach(()=> {vi.restoreAllMocks();vi.unstubAllGlobals();document.body.innerHTML=''})
it('copies the literal code inside a dialog focus trap, never the password mask',async()=>{
 document.body.innerHTML='<div id="dialog"><input type="password" value="masked-field"><section id="scope"></section></div>'
 const dialog=document.getElementById('dialog')!,container=document.getElementById('scope')!,password=dialog.querySelector('input')!
 password.focus()
 const trap=(event:FocusEvent)=> { if(!dialog.contains(event.target as Node)) password.focus() }
 document.addEventListener('focusin',trap)
 let copied=''
 Object.defineProperty(document,'execCommand',{configurable:true,value:vi.fn(()=>{ const event=new Event('copy',{cancelable:true});Object.defineProperty(event,'clipboardData',{value:{setData:(_type:string,value:string)=>{copied=value}}});document.dispatchEvent(event);return event.defaultPrevented })})
 try { await copyU1Text('AB12CD34-EF56AB78-90CD12EF-34AB56CD',container);expect(copied).toBe('AB12CD34-EF56AB78-90CD12EF-34AB56CD');expect(container.querySelector('textarea')).toBeNull();expect(document.activeElement).toBe(password) }
 finally { document.removeEventListener('focusin',trap) }
})
it('reports failure instead of pretending a blocked copy succeeded',async()=>{
 const container=document.createElement('div');document.body.appendChild(container)
 Object.defineProperty(document,'execCommand',{configurable:true,value:vi.fn(()=>false)})
 await expect(copyU1Text('text',container)).rejects.toThrow('copy_failed');expect(container.querySelector('textarea')).toBeNull()
})
it('falls back inside the caller after clipboard permission rejection',async()=>{
 vi.stubGlobal('isSecureContext',true)
 Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:vi.fn().mockRejectedValue(new Error('denied'))}})
 const container=document.createElement('div');document.body.appendChild(container);let copied=''
 Object.defineProperty(document,'execCommand',{configurable:true,value:vi.fn(()=>{const event=new Event('copy',{cancelable:true});Object.defineProperty(event,'clipboardData',{value:{setData:(_type:string,value:string)=>{copied=value}}});document.dispatchEvent(event);return event.defaultPrevented})})
 await copyU1Text('https://example.test/u1-remote/open',container);expect(copied).toBe('https://example.test/u1-remote/open')
})
