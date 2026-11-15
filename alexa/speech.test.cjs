const test=require('node:test'),assert=require('node:assert/strict')
const speech=require('./speech.cjs'),{phrases}=require('./events.cjs')
test('all phrase languages preserve every event',()=>{for(const catalog of Object.values(speech.catalogs))assert.deepEqual(Object.keys(catalog).sort(),Object.keys(phrases).sort())})
test('only allowlisted locales build a plain spoken sequence',()=>{
 const auth={createSequenceNode:(type,text,id)=>({type:'Alexa.Speak',operationPayload:{textToSpeak:text,deviceSerialNumber:id,locale:'de-DE'}})}
 const node=speech.sequence(auth,'device','Test','en-GB');assert.equal(node.startNode.operationPayload.locale,'en-GB');assert.equal(node.startNode.operationPayload.deviceSerialNumber,'device');assert.equal(node.startNode.operationPayload.textToSpeak,'Test')
 assert.equal(speech.sequence(auth,'device','Test','auto'),null);assert.throws(()=>speech.sequence(auth,'device','Test','ru-RU'));assert.equal(speech.defaults('de-DE').started,'Ihr Druck wurde gestartet.');assert.notEqual(speech.testText('ja-JP'),speech.testText('en-US'))
})
test('unsupported node cannot silently change to another device action',()=>{assert.throws(()=>speech.sequence({createSequenceNode:()=>({type:'Alexa.Volume',operationPayload:{}})},'device','Hi','de-DE'))})
