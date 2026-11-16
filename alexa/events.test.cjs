const test = require('node:test'), assert = require('node:assert/strict')
const {reduce} = require('./events.cjs')
const baseline = () => ({job:'job1',print:{state:'printing'},errors:[],maintenance:{due:false},bed:{due:false}})
test('does not announce an old completed print on initial connection',()=>assert.deepEqual(reduce(null,{...baseline(),print:{state:'complete'}},100).events,[]))
test('announces completion once for the same known job',()=>{const a=reduce(null,baseline(),100);const b=reduce(a.state,{...baseline(),print:{state:'complete'}},110);assert.deepEqual(b.events.map(e=>e.kind),['finished']);assert.deepEqual(reduce(b.state,{...baseline(),print:{state:'complete'}},115).events,[])})
test('a different history job cannot finish the previously observed job',()=>{const a=reduce(null,baseline(),100);assert.deepEqual(reduce(a.state,{...baseline(),job:'job2',print:{state:'complete'}},110).events,[])})
test('active error, one reminder after 15 minutes, then recovery',()=>{let s=baseline();s.errors=[{code:'cover'}];let a=reduce(null,s,100);assert.deepEqual(a.events.map(e=>e.kind),['error']);a=reduce(a.state,s,999);assert.equal(a.events.length,0);a=reduce(a.state,s,1000);assert.deepEqual(a.events.map(e=>e.kind),['repeat']);a=reduce(a.state,s,2000);assert.equal(a.events.length,0);a=reduce(a.state,baseline(),2001);assert.deepEqual(a.events.map(e=>e.kind),['recovered'])})
test('shortage requires a deficit and estimate, is suppressed while paused',()=>{const s={...baseline(),shortages:[{head:1,seconds:1600,shortage:2}]};let a=reduce(null,{...s,paused:true},100);assert.equal(a.events.length,0);a=reduce(a.state,s,101);assert.deepEqual(a.events.map(e=>e.kind),['shortage']);assert.equal(reduce(a.state,s,102).events.length,0);assert.equal(reduce(null,{...s,shortages:[{head:1,seconds:null,shortage:2}]},100).events.length,0)})
test('maintenance warnings do not repeat every polling cycle',()=>{const s={...baseline(),maintenance:{due:true,revision:'due'}};const a=reduce(null,s,100);assert.deepEqual(a.events.map(e=>e.kind),['maintenance']);assert.equal(reduce(a.state,s,105).events.length,0);assert.deepEqual(reduce(a.state,{...s,job:'job2'},110).events.map(e=>e.kind),['started','maintenance'])})
test('dryer pause and completion are distinct transitions',()=>{let a=reduce(null,{...baseline(),dryer:{state:'running'}},100);a=reduce(a.state,{...baseline(),dryer:{state:'paused'}},105);assert.deepEqual(a.events.map(e=>e.kind),['dryerPaused']);a=reduce(a.state,{...baseline(),dryer:{state:'completed'}},110);assert.deepEqual(a.events.map(e=>e.kind),['dryerDone'])})


test('disabled dryer notifications do not replay when enabled later',()=>{let a=reduce(null,{...baseline(),dryer:{state:'running'}},100);a=reduce(a.state,{...baseline(),dryerNotify:false,dryer:{state:'completed'}},105);assert.equal(a.events.length,0);a=reduce(a.state,{...baseline(),dryerNotify:true,dryer:{state:'completed'}},110);assert.equal(a.events.length,0)})

test('announces each new print start once, not after restart or resume',()=>{
 let r=reduce(null,{job:'old',print:{state:'printing'}},1);assert.deepEqual(r.events,[])
 r=reduce(r.state,{job:'new',print:{state:'printing'}},2);assert.deepEqual(r.events.map(e=>e.kind),['started'])
 r=reduce(r.state,{job:'new',print:{state:'printing'}},3);assert.deepEqual(r.events,[])
 r=reduce(r.state,{job:'new',print:{state:'paused'}},4)
 r=reduce(r.state,{job:'new',print:{state:'printing'}},5);assert.deepEqual(r.events.map(e=>e.kind),['resumed'])
})
test('calibration notifications follow a new queue and a single terminal result',()=>{
 let r=reduce(null,{calibration:{id:'old',state:'completed'}},1);assert.deepEqual(r.events,[])
 r=reduce(r.state,{calibration:{id:'new',state:'starting'}},2);assert.deepEqual(r.events.map(e=>e.kind),['calibrationStarted'])
 r=reduce(r.state,{calibration:{id:'new',state:'calibrating'}},3);assert.deepEqual(r.events,[])
 r=reduce(r.state,{calibration:{id:'new',state:'completed'}},4);assert.deepEqual(r.events.map(e=>e.kind),['calibrationCompleted'])
 r=reduce(r.state,{calibration:{id:'new',state:'completed'}},5);assert.deepEqual(r.events,[])
 r=reduce(r.state,{calibration:{id:'failed-run',state:'starting'}},6)
 r=reduce(r.state,{calibration:{id:'failed-run',state:'failed'}},7);assert.deepEqual(r.events.map(e=>e.kind),['calibrationStopped'])
})

 test('Companion update speaks once per version, rejects stale and failed checks',()=>{
 let r=reduce(null,{companionUpdate:{updateAvailable:true,latest:'v2',updatedAt:100}},101);assert.deepEqual(r.events.map(e=>e.kind),['companionUpdate']);
 r=reduce(r.state,{companionUpdate:{updateAvailable:true,latest:'v2',updatedAt:100}},102);assert.deepEqual(r.events,[]);
 r=reduce(r.state,{companionUpdate:{updateAvailable:true,latest:'v3',updatedAt:100}},103);assert.deepEqual(r.events.map(e=>e.kind),['companionUpdate']);
 assert.deepEqual(reduce(null,{companionUpdate:{updateAvailable:true,latest:'v4',updatedAt:0}},10000).events,[]);
 assert.deepEqual(reduce(null,{companionUpdate:{updateAvailable:true,checkFailed:true,latest:'v4',updatedAt:100}},101).events,[]);
 })
