const test=require('node:test'),assert=require('node:assert/strict')
const {diagnostic}=require('./auth-diagnostics.cjs')
test('reports the failing phase and HTTP status without secrets or request headers',()=>{
 const info=diagnostic({path:'/auth/register?code=SECRET',headers:{Cookie:'PRIVATE'}},400,'{"error":"invalid_grant", "email":"PERSONAL", "refreshToken":"TOKEN"}')
 assert.equal(info.stage,'register');assert.equal(info.status,400);assert.deepEqual(info.markers,['invalid_grant']);assert.doesNotMatch(JSON.stringify(info),/SECRET|PRIVATE|PERSONAL|TOKEN|refreshToken/)
})
test('does not expose arbitrary transport error strings or unrecognized paths',()=>{
 const info=diagnostic({path:'/someone/PRIVATE'},null,'','error containing PRIVATE')
 assert.equal(info.stage,'other');assert.equal(info.transport,'request_failed');assert.doesNotMatch(JSON.stringify(info),/PRIVATE/)
})
