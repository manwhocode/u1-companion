const config={revision:'preview',enabled:true,consent:true,model:'Выбранная модель GPT',access:'control',instructions:'',keepHistory:true,contextChars:24000,maxOutputTokens:2000,hasKey:true}
export async function aiRequest<T>(path:string,payload?:any):Promise<T>{
 if(path==='state')return {settings:config,busy:false,chats:[],usage:{requests:0,inputTokens:0,outputTokens:0},audit:[],printer:{webhooks:{state:'ready'},print_stats:{state:'standby',filename:''}}} as T
 if(path==='chat')return {job:'00000000-0000-4000-8000-000000000001'} as T
 if(path.startsWith('jobs/'))return {state:'completed',result:{message:{role:'assistant',content:'Это локальная проверка чата. В рабочей версии я прочитаю актуальные данные U1 через разрешённые инструменты. Любое управление потребует отдельного подтверждения.',reads:['get_printer_status']}}} as T
 if(path==='settings')return {...config,...payload} as T
 throw new Error('В локальной проверке этот запрос отключён.')
}
