'use strict'
const {phrases}=require('./events.cjs')
const catalogs=require('./speech-phrases.json')
const locales=[['en-US','English (US)'],['en-GB','English (UK)'],['en-CA','English (Canada)'],['en-AU','English (Australia)'],['en-IN','English (India)'],['de-DE','Deutsch'],['fr-FR','Français (France)'],['fr-CA','Français (Canada)'],['it-IT','Italiano'],['es-ES','Español (España)'],['es-MX','Español (México)'],['es-US','Español (US)'],['pt-BR','Português (Brasil)'],['ja-JP','日本語'],['hi-IN','हिन्दी'],['ar-SA','العربية']].map(([value,text])=>({value,text}))
const valid=language=>language==='auto'||locales.some(row=>row.value===language)
const defaults=language=>{if(!valid(language))throw new Error('invalid_configuration');return {...phrases,...(catalogs[language.split('-')[0]]||{})}}
const tests={en:'Your Snapmaker U one printer is connected. This is a test voice message.',de:'Ihr Snapmaker U eins Drucker ist verbunden. Dies ist eine Testnachricht.',fr:'Votre imprimante Snapmaker U un est connectée. Ceci est un test vocal.',it:'La stampante Snapmaker U uno è collegata. Questo è un messaggio di prova.',es:'La impresora Snapmaker U uno está conectada. Este es un mensaje de prueba.',pt:'A impressora Snapmaker U um está conectada. Esta é uma mensagem de teste.',ja:'スナップメーカーのプリンターが接続されました。これはテストメッセージです。',hi:'आपका स्नैपमेकर प्रिंटर कनेक्ट हो गया है। यह एक परीक्षण संदेश है।',ar:'تم توصيل طابعة سناب ميكر. هذه رسالة صوتية تجريبية.'}
function sequence(auth,id,text,language){
 if(!valid(language))throw new Error('invalid_configuration')
 if(language==='auto')return null
 const node=auth.createSequenceNode('speak',text,id)
 if(!node||node.type!=='Alexa.Speak'||!node.operationPayload)throw new Error('invalid_configuration')
 node.operationPayload.locale=language
 return {'@type':'com.amazon.alexa.behaviors.model.Sequence',startNode:node}
}
module.exports={locales,valid,defaults,sequence,testText:language=>tests[language.split('-')[0]]||tests.en,catalogs:{en:phrases,...catalogs}}
