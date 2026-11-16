'use strict'
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), http = require('node:http')
const { phrases, reduce, hash } = require('./events.cjs')
const { maintenanceStatus } = require('./maintenance-status.cjs')
const { loginDomain, returnShape } = require('./external-login.cjs')
const Alexa = require('alexa-remote2')
const speech = require('./speech.cjs')
const { eventText } = require('./error-details.cjs')
const DIR = process.env.U1_ALEXA_PRIVATE || '/userdata/u1-addons/alexa-private'
fs.mkdirSync(DIR, { recursive: true, mode: 0o700 }); process.umask(0o077)
const reqDir = path.join(DIR, 'requests'); fs.mkdirSync(reqDir, { recursive: true, mode: 0o700 })
const file = name => path.join(DIR, name + '.json')
function read (name, fallback) { try { return JSON.parse(fs.readFileSync(file(name), 'utf8')) } catch { return fallback } }
function write (name, value) { const target = file(name); const tmp = target + '.next'; const fd = fs.openSync(tmp, 'w', 0o600); try { fs.writeFileSync(fd, JSON.stringify(value)); fs.fsyncSync(fd) } finally { fs.closeSync(fd) }; fs.renameSync(tmp, target) }
let config = read('config', { region: 'amazon.de', enabled: false, targets: [], confirmed: [], phrases, method: 'speak' })
if (config.method !== 'speak') { config = { ...config, method: 'speak', enabled: false, confirmed: [] }; write('config', config) }
config.language = speech.valid(config.language) ? config.language : 'auto'
let testHistory = read('tests', {})
let model = read('events', null), previousEnabled = false, busy = false, sourceBusy = false, auth = null, generation = 0, timer = null, externalComplete = null
let publicState = { phase: 'disconnected', message: 'Amazon не подключён.', devices: [], loginUrl: null, test: null, lastEvent: null }
function publish () { write('status', { ...publicState, config: { ...config, phrases: { ...speech.defaults(config.language), ...config.phrases } }, speechLocales:speech.locales, speechCatalogs:speech.catalogs, updatedAt: Date.now()/1000, pid: process.pid }) }
function resetAuth () { generation++; publicState.loginDiagnostic = null; externalComplete = null; publicState.externalLoginUrl = null; if (timer) clearTimeout(timer); timer = null; if (auth) { try { auth.stopProxyServer(); auth.stop() } catch {} }; auth = null; publicState.devices = []; publicState.loginUrl = null; publicState.test = null }
const permittedRegions = ['amazon.de', 'amazon.com', 'amazon.co.uk', 'amazon.fr', 'amazon.it', 'amazon.es', 'amazon.co.jp', 'amazon.com.au', 'amazon.ca']
function call (fn, seconds = 20) { return new Promise((resolve,reject) => { let settled = false; const timeout = setTimeout(() => { settled = true; reject(new Error('timeout')) }, seconds*1000); fn((error,result) => { if (settled) return; settled = true; clearTimeout(timeout); error ? reject(new Error('request_failed')) : resolve(result) }) }) }
function devices () {
  return Object.values(auth?.serialNumbers || {}).filter(d => ['ECHO','FIRE_TV','ROOK','KNIGHT'].includes(d.deviceFamily) || d.capabilities?.includes('AUDIO_PLAYER')).map(d => ({ id: d.serialNumber, name: String(d.accountName || 'Alexa device').slice(0,100), family: d.deviceFamily, online: d.online !== false, confirmed: config.confirmed.includes(d.serialNumber) }))
}
async function refreshDevices () {
  if (!auth || publicState.phase !== 'connected') return
  const current = auth, stamp = generation
  const result = await call(done => current.httpsGet('/api/devices-v2/device?cached=false', done), 10)
  if (stamp !== generation || current !== auth) return
  for (const device of result?.devices || []) {
    const known = current.serialNumbers[device.serialNumber]
    if (known && typeof device.online === 'boolean') known.online = device.online
  }
  publicState.devices = devices(); publicState.devicesUpdatedAt = Date.now()/1000; publish()
}
function connect (host, manual = false, external = false) {
  let externalSubmitted = false
  resetAuth(); publicState.authTrace = []; const stamp = generation; const remote = auth = new Alexa()
  const saved = read('auth', null)
  if (!manual && !saved) { publicState.phase = 'disconnected'; publicState.message = 'Нажмите «Подключить Amazon».'; publish(); return }
  if (manual && (!/^([a-zA-Z0-9-]+\.)*[a-zA-Z0-9-]+$/.test(host) || host.length > 253)) throw new Error('invalid_host')
  const token = crypto.randomBytes(32).toString('hex'); const expires = Date.now()+600000
  publicState.phase = manual ? 'awaiting_login' : 'connecting'; publicState.message = manual ? 'Откройте защищённое окно входа. Ссылка действительна 10 минут.' : 'Подключение Amazon…'
  publicState.loginUrl = manual ? `https://${host}:3443/connect/${token}` : null; publish()
  remote.on('cookie', () => { if (stamp === generation && remote.cookieData) write('auth', remote.cookieData) })
  const options = { cookie: saved || undefined, amazonPage: config.region, baseAmazonPage: loginDomain(config.region), acceptLanguage: 'en-US', useWsMqtt: false, usePushConnection: false, bluetooth: false, notifications: false, logger: () => {}, cookieRefreshInterval: 4*86400000, formerDataStorePath: path.join(DIR, 'registration.json'),
    setupProxy: manual, proxyOnly: true, proxyOwnIp: host || '127.0.0.1', proxyListenBind: '127.0.0.1', proxyPort: 3457, proxyExternalPort: 3443, proxyProtocol: 'https', u1LoginToken: token, u1LoginExpires: expires, proxyLogLevel: 'silent', proxyCloseWindowHTML: '<html><meta charset="utf-8"><title>U1 Alexa</title><p>Вход выполнен. Закройте это окно и вернитесь к настройкам U1.</p></html>' }
  options.u1AuthDiagnostic = data => { if (stamp !== generation) return; publicState.authTrace = [...(publicState.authTrace || []), data].slice(-12); publish() }
  if (manual) { delete options.cookie; options.formerRegistrationData = saved || undefined }
  if (external) {
    publicState.loginUrl = null
    options.u1ExternalLogin = (url, complete) => {
      if (stamp !== generation) return
      externalComplete = value => { complete(value); externalSubmitted = true }
      publicState.externalLoginUrl = url
      publicState.message = 'Откройте Amazon и войдите ключом доступа. Затем вставьте адрес страницы после входа. Ссылка действительна 10 минут.'
      publish()
    }
  }
  remote.init(options, error => {
    if (stamp !== generation) return
    if (error) {
      publicState.phase = externalSubmitted || !manual ? 'login_required' : 'awaiting_login'
      publicState.message = externalSubmitted ? 'Amazon не подтвердил подключение по возвращённому коду. Начните вход ключом заново; этот способ пока требует проверки с вашим аккаунтом.' : manual ? 'Ожидается вход Amazon в отдельном окне.' : 'Сессия Amazon недоступна. Подключите аккаунт заново.'
      publish(); return
    }
    if (timer) clearTimeout(timer); timer = null
    externalComplete = null; publicState.externalLoginUrl = null
    publicState.phase = 'connected'; publicState.message = 'Amazon подключён. Выберите устройство и проверьте звук.'; publicState.devices = devices(); publicState.loginUrl = null; publish()
  })
  timer = setTimeout(() => { if (stamp === generation && publicState.phase !== 'connected') { resetAuth(); publicState.phase = 'login_required'; publicState.message = 'Время входа истекло. Повторите подключение.'; publish() } }, manual ? 600000 : 45000)
}
async function speak (id, text) {
  if (publicState.phase !== 'connected' || !auth?.serialNumbers[id]) throw new Error('not_connected')
  if (typeof text !== 'string' || !text.trim() || text.length > 500 || /[<>]/.test(text)) throw new Error('invalid_text')
  const node = speech.sequence(auth, id, text, config.language)
  return call(done => node ? auth.sendSequenceCommand(id, node, done) : auth.sendSequenceCommand(id, 'speak', text, done))
}
async function command (request) {
  const p = request.payload || {}
  switch (request.action) {
    case 'login': connect(p.host, true); break
    case 'passkey': config.enabled = false; write('config',config); connect(p.host, true, true); break
    case 'complete_passkey': {
      if (!externalComplete || publicState.phase !== 'awaiting_login') throw new Error('login_expired')
      // The parser owns the PKCE verifier. Never fetch or log the submitted URL.
      publicState.loginDiagnostic = returnShape(p.url)
      externalComplete(p.url)
      externalComplete = null; publicState.externalLoginUrl = null
      publicState.message = 'Завершаем подключение Amazon…'
      break
    }
    case 'logout': resetAuth(); config.enabled = false; config.confirmed = []; config.targets = []; write('config', config); if (fs.existsSync(file('auth'))) fs.unlinkSync(file('auth')); publicState.phase = 'disconnected'; publicState.message = 'Локальная сессия удалена. Для отзыва доступа проверьте устройства в аккаунте Amazon.'; break
    case 'save': {
      const language = p.language ?? config.language
      if (!speech.valid(language)) throw new Error('invalid_configuration')
      const languageChanged = language !== config.language
      if (languageChanged && p.enabled) throw new Error('test_required')
      if (!permittedRegions.includes(p.region) || p.method !== 'speak' || typeof p.enabled !== 'boolean' || !Array.isArray(p.targets) || p.targets.length > 8) throw new Error('invalid_configuration')
      const available = new Set([...publicState.devices.map(d => d.id), ...(!p.enabled ? config.targets : [])])
      if (p.targets.some(id => typeof id !== 'string' || !available.has(id))) throw new Error('unknown_device')
      if (p.enabled && (publicState.phase !== 'connected' || !p.targets.length || p.targets.some(id => !config.confirmed.includes(id)))) throw new Error('test_required')
      const phraseLanguages = { ...(config.phraseLanguages || {}), [config.language]: { ...config.phrases } }
      const languagePhrases = languageChanged ? phraseLanguages[language] || speech.defaults(language) : config.phrases
      const nextPhrases = {}; for (const key of Object.keys(phrases)) { const text = p.phrases?.[key] ?? languagePhrases?.[key] ?? speech.defaults(language)[key]; if (typeof text !== 'string' || !text.trim() || text.length > 500 || /[<>]/.test(text)) throw new Error('invalid_text'); nextPhrases[key] = text }
      if (p.method !== config.method || languageChanged) { if (p.enabled) throw new Error('test_required'); config.confirmed = []; publicState.test = null; testHistory = {}; write('tests',testHistory) }
      if (p.region !== config.region) { resetAuth(); if (fs.existsSync(file('auth'))) fs.unlinkSync(file('auth')); config.confirmed = []; p.enabled = false; publicState.phase = 'disconnected' }
      config = { ...config, language, phraseLanguages: { ...phraseLanguages, [language]:nextPhrases }, region: p.region, method: p.method, targets: [...new Set(p.targets)], enabled: p.enabled, phrases: nextPhrases }; write('config', config); if (auth && publicState.phase === 'connected') publicState.devices = devices(); break
    }
    case 'test': {
      publicState.test = { id: p.id, language: config.language, phase: 'sending', time: Date.now()/1000 }; publish()
      try { await speak(p.id, speech.testText(config.language)); publicState.test.phase = 'accepted'; publicState.message = 'Amazon принял запрос. Подтвердите, слышали ли вы голосовое сообщение.' } catch { publicState.test.phase = 'failed'; publicState.message = 'Запрос голосового сообщения не подтверждён. Проверьте устройство и подключение.' }
      testHistory[p.id] = { ...publicState.test, method: config.method }; write('tests',testHistory)
      break
    }
    case 'heard': {
      const test = testHistory[p.id] || publicState.test
      if (!test || test.id !== p.id || test.phase !== 'accepted' || (test.method && test.method !== config.method) || (test.language || 'auto') !== config.language || Date.now()/1000-test.time>3600 || p.confirmed !== true) throw new Error('test_required')
      config.confirmed = [...new Set([...config.confirmed, p.id])]; write('config', config); publicState.devices = devices(); break
    }
    default: throw new Error('unknown_action')
  }
  publish()
}
function api (pathname) { return new Promise((resolve,reject) => { const req = http.get({hostname:'127.0.0.1',port:7125,path:pathname,timeout:4000},res => { let data='';res.on('data',chunk => { data+=chunk; if(data.length>8*1024*1024) req.destroy(new Error('large_response')) });res.on('end',() => { try { const value=JSON.parse(data); if(res.statusCode!==200 || !value.result) throw new Error('source_failed'); resolve(value.result) } catch { reject(new Error('source_failed')) } }) });req.on('timeout',()=>req.destroy(new Error('timeout')));req.on('error',reject) }) }
async function collect () {
  const [status,usage,maintenance,history,notice,companionUpdate] = await Promise.all([
    api('/printer/objects/query?print_stats&exception_manager&u1_dryer'),api('/server/database/item?namespace=fluidd&key=u1_spool_usage_v1'),api('/server/database/item?namespace=fluidd&key=u1_maintenance_v1'),api('/server/history/list?limit=1'),api('/server/database/item?namespace=fluidd&key=u1_maintenance_status_v1').catch(()=>null),api('/server/database/item?namespace=fluidd&key=u1_companion_update_v1').catch(()=>null)])
  const s=status.status,u=usage.value,m=maintenance.value
  const marker=m.service,bed=m.bed
  const dueState=maintenanceStatus(m,notice?.value)
  const schedule=(()=>{try{return JSON.parse(fs.readFileSync('/userdata/u1-addons/filament-ui-data/schedule/state.json'))}catch{return {}}})()
  const dryerNotify=(()=>{try{return JSON.parse(fs.readFileSync('/userdata/u1-addons/filament-ui-data/drying/notifications.json')).enabled===true}catch(error){return error.code==='ENOENT'}})()
  const calibration=(()=>{try{const c=JSON.parse(fs.readFileSync('/userdata/u1-addons/filament-ui-data/calibration-jobs/state.json'));return {id:c.id,state:c.state}}catch{return {}}})()
  return {companionUpdate:companionUpdate?.value,calibration,dryerNotify,print:s.print_stats,job:history.jobs[0] ? hash([history.jobs[0].job_id,history.jobs[0].start_time]) : null,errors:s.exception_manager?.exceptions || [],dryer:s.u1_dryer,dryerSession:hash([s.u1_dryer?.deadline]),schedule,scheduleVersion:hash([schedule.id,schedule.state,schedule.updatedAt]),shortages:u.active?.changed ? [] : u.active?.rows || [],paused:!!u.active?.paused,
    maintenance:{due:dueState.serviceDue,revision:hash([marker?.time,m.periods?.service])},bed:{due:dueState.bedDue,revision:hash([bed?.time,m.periods?.bed])}}
}
async function poll () {
  if (sourceBusy) return
  if (!config.enabled || publicState.phase !== 'connected') { previousEnabled = false; return }
  sourceBusy = true
  try {
    const snapshot=await collect();const now=Date.now()/1000
    const baseline = previousEnabled ? model : {previous:null,errors:{},once:{},lastCompanionUpdate:model?.lastCompanionUpdate}
    const result=reduce(baseline,snapshot,now);model=result.state;previousEnabled=true;write('events',model)
    for (const event of result.events.slice(0,8)) {
      if (!config.enabled) break
      // Persist reservation before submission. A lost response is never retried automatically.
      publicState.lastEvent={kind:event.kind,time:event.time,phase:'sending'};publish()
      let accepted=0
      for(const id of config.targets) { if(!config.enabled)break;if(!config.confirmed.includes(id))continue;try{await speak(id,eventText(event,config.language,config.phrases[event.kind] || speech.defaults(config.language)[event.kind] || phrases[event.kind]));accepted++}catch{} }
      publicState.lastEvent.phase=accepted?'accepted':'failed';publish()
    }
  } catch { publicState.message='Нет свежего статуса принтера или связи. Пропущенные объявления не воспроизводятся задним числом.';publish() } finally {sourceBusy=false}
}
async function requests () {
  if(busy)return;busy=true
  try {
    const names=fs.readdirSync(reqDir).filter(n=>/^[0-9a-f-]{36}\.json$/.test(n)).sort().slice(0,10)
    for(const name of names) {
      const target=path.join(reqDir,name);let request
      try{request=JSON.parse(fs.readFileSync(target));fs.unlinkSync(target)}catch{continue}
      if(!Number.isFinite(request.time) || Math.abs(Date.now()/1000-request.time)>120)continue
      try {await command(request);publicState.operation={id:request.id,ok:true}}catch(error){publicState.operation={id:request.id,ok:false,error:['invalid_host','invalid_configuration','unknown_device','test_required','invalid_text','invalid_return_url','missing_authorization_code','login_expired'].includes(error.message)?error.message:'request_failed'}}
      publish()
    }
  }finally{busy=false}
}
process.on('uncaughtException',()=>{process.stderr.write('Alexa bridge stopped after an internal error. No credentials logged.\n');process.exit(1)})
process.on('unhandledRejection',()=>{publicState.message='Ошибка соединения Alexa. Повторите подключение.';publish()})
process.on('SIGTERM',()=>{resetAuth();process.exit(0)})
publish();if(read('auth',null))connect(null,false)
setInterval(requests,500);setInterval(poll,5000);setInterval(publish,15000)
setInterval(() => refreshDevices().catch(() => {}),60000)
