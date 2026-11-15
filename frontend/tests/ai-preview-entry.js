import Vue from 'vue'
import Vuetify from 'vuetify'
import VueI18n from 'vue-i18n'
import 'vuetify/dist/vuetify.min.css'
import U1AI from '@/views/U1AI.vue'
import U1DialogClose from '@/components/U1DialogClose.vue'
Vue.use(Vuetify);Vue.use(VueI18n);Vue.component('u1-dialog-close',U1DialogClose)
new Vue({vuetify:new Vuetify({theme:{dark:true,themes:{dark:{primary:'#9bcc45'}}}}),i18n:new VueI18n({locale:'ru',messages:{ru:{}}}),render:h=>h('v-app',[h('div',{style:'padding:10px;background:#725813;color:white;text-align:center'},'Локальная проверка интерфейса · без связи с принтером и OpenAI'),h('div',{style:'padding:20px'},[h(U1AI)])])}).$mount('#app')
