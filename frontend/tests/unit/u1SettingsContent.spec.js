import Vue from 'vue'
import {expect,it} from 'vitest'
import Content from '@/components/U1SettingsContent.vue'
it('renders settings content directly instead of another dialog when inline',()=>{
 const C=Vue.extend(Content);const inline=new C({propsData:{inline:true,value:false}})
 expect(inline._render().tag).toBe('div')
 const modal=new C({propsData:{inline:false,value:true}})
 expect(modal._render().tag).not.toBe('div')
 inline.$destroy();modal.$destroy()
})
