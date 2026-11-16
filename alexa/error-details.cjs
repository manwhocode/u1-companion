'use strict'
// Fixed descriptions for known stock faults; other errors retain their bounded printer message.
const descriptions = {
 en:['Filament tangling detected. Check the spool and filament path.','An object or dirt was detected on the print bed. Check and clear the bed.','Error code','Head'],
 de:['Filamentverwicklung erkannt. Prüfen Sie die Spule und den Filamentweg.','Ein Gegenstand oder Schmutz wurde auf dem Druckbett erkannt. Prüfen und reinigen Sie das Bett.','Fehlercode','Druckkopf'],
 fr:['Un enchevêtrement du filament a été détecté. Vérifiez la bobine et le chemin du filament.','Un objet ou des saletés ont été détectés sur le plateau. Vérifiez et dégagez le plateau.','Code erreur','Tête'],
 it:['Rilevato un groviglio del filamento. Controlla la bobina e il percorso del filamento.','Rilevato un oggetto o dello sporco sul piano di stampa. Controlla e libera il piano.','Codice errore','Testina'],
 es:['Se ha detectado un enredo del filamento. Comprueba la bobina y el recorrido del filamento.','Se ha detectado un objeto o suciedad en la cama de impresión. Comprueba y despeja la cama.','Código de error','Cabezal'],
 pt:['Foi detetado filamento emaranhado. Verifique a bobina e o percurso do filamento.','Foi detetado um objeto ou sujidade na mesa de impressão. Verifique e limpe a mesa.','Código de erro','Cabeça'],
 ja:['フィラメントの絡まりを検出しました。スプールとフィラメントの経路を確認してください。','プリントベッド上に異物または汚れを検出しました。ベッドを確認し、取り除いてください。','エラーコード','ヘッド'],
 hi:['फिलामेंट उलझा हुआ है। स्पूल और फिलामेंट के रास्ते की जाँच करें।','प्रिंट बेड पर कोई वस्तु या गंदगी मिली है। बेड की जाँच करके उसे साफ करें।','त्रुटि कोड','हेड'],
 ar:['تم اكتشاف تشابك في خيط الطباعة. تحقّق من البكرة ومسار الخيط.','تم اكتشاف جسم أو أوساخ على منصة الطباعة. تحقّق من المنصة ونظّفها.','رمز الخطأ','الرأس']
}
const plain = value => String(value || '').replace(/[<>\x00-\x1f\x7f]/g,' ').replace(/\s+/g,' ').trim().slice(0,200)
function detail (error, language) {
 if (!error || typeof error !== 'object') return ''
 const words=descriptions[language.split('-')[0]] || descriptions.en
 const integer = (v,max) => Number.isInteger(v) && v>=0 && v<=max
 if (error.id===523 && error.code===38 && integer(error.index,3)) return `${words[3]} ${error.index+1}. ${words[0]}`
 if (error.id===532 && error.code===1) return words[1]
 const message=plain(error.message || error.msg)
 const code=['level','id','index','code'].every(k=>integer(error[k],9999)) ? `${words[2]} ${error.level}, ${error.id}, ${error.index}, ${error.code}.` : ''
 return [message,code].filter(Boolean).join(' ')
}
function eventText (event, language, base) {
 const description=['error','repeat'].includes(event.kind) ? detail(event.error,language) : ''
 const prefix=String(base || '').slice(0,Math.max(0,499-description.length))
 return [prefix,description].filter(Boolean).join(' ').slice(0,500)
}
module.exports={detail,eventText}
