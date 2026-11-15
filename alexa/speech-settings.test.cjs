const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),vm=require('node:vm'),{createRequire}=require('node:module')
const {phrases}=require('./events.cjs')
function setup(){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'u1-speech-'))
 fs.writeFileSync(path.join(dir,'config.json'),JSON.stringify({region:'amazon.de',method:'speak',enabled:false,targets:[],confirmed:['old-proof'],phrases:{...phrases,started:'My custom start'}}))
 const module={exports:{}};const nativeRequire=createRequire(path.join(__dirname,'bridge.cjs'))
 const context={module,require:name=>name==='alexa-remote2'?class{}:nativeRequire(name),process:{env:{U1_ALEXA_PRIVATE:dir},umask:()=>{},on:()=>{}},setInterval:()=>0,setTimeout:()=>0,clearTimeout:()=>{},console}
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'bridge.cjs'),'utf8')+';module.exports={command,getConfig:()=>config};',context)
 return {...module.exports,cleanup:()=>fs.rmSync(dir,{recursive:true,force:true})}
}
test('language switch preserves own phrases per language and invalidates sound confirmation',async()=>{
 const s=setup();const save=payload=>s.command({action:'save',payload:{region:'amazon.de',method:'speak',enabled:false,targets:[],...payload}})
 try{
  await save({language:'de-DE'});assert.equal(s.getConfig().language,'de-DE');assert.equal(s.getConfig().confirmed.length,0);assert.equal(s.getConfig().phrases.started,'Ihr Druck wurde gestartet.')
  await save({language:'de-DE',phrases:{started:'Eigener Starttext'}})
  await save({language:'en-US'});assert.equal(s.getConfig().phrases.started,phrases.started)
  await save({language:'de-DE'});assert.equal(s.getConfig().phrases.started,'Eigener Starttext')
  await save({language:'auto'});assert.equal(s.getConfig().phrases.started,'My custom start')
  const before=JSON.stringify(s.getConfig());await assert.rejects(()=>save({language:'ru-RU'}));assert.equal(JSON.stringify(s.getConfig()),before)
  await assert.rejects(()=>save({language:'de-DE',enabled:true}))
 }finally{s.cleanup()}
})
