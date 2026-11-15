const test=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm'), path=require('node:path'), {createRequire}=require('node:module')
const {authorizationCode,loginDomain,returnShape}=require('./external-login.cjs')
const valid='https://www.amazon.com/ap/maplanding?openid.oa2.authorization_code=one-time-code-123'
test('parses a code only from the expected Amazon origin',()=>assert.equal(authorizationCode(valid,'amazon.com'),'one-time-code-123'))
test('rejects arbitrary origin, URL credentials, insecure scheme, and duplicate codes',()=>{
 for(const url of [valid.replace('www.amazon.com','evil.example'),valid.replace('www.amazon.com','www.amazon.com.evil.example'),valid.replace('https:','http:'),valid.replace('www.amazon.com','user:password@www.amazon.com'),valid.replace('/ap/maplanding','/'),valid+'&openid.oa2.authorization_code=another-code'])assert.throws(()=>authorizationCode(url,'amazon.com'))
})
test('external handoff keeps verifier private and accepts a return code once',()=>{
 const sourceFile=path.join(__dirname,'node_modules/alexa-cookie2/lib/proxy.js'), actualRequire=createRequire(sourceFile)
 let handoff,result,complete
 const app={use:()=>{},get:()=>{},listen:()=>{const server={on:()=>server};return server}}
 const sandbox={module:{exports:{}},Buffer,URL,console,__dirname:path.dirname(sourceFile),require:name=>{
  if(name==='express')return ()=>app
  if(name==='http-proxy-response-rewrite')return ()=>{}
  if(name==='http-proxy-middleware')return {createProxyMiddleware:()=>()=>{}}
  if(name==='fs')return {existsSync:()=>false,writeFileSync:()=>{}}
  return actualRequire(name)
 }}
 vm.runInNewContext(fs.readFileSync(sourceFile,'utf8'),sandbox)
 const options={baseAmazonPage:loginDomain('amazon.de'),baseAmazonPageHandle:'',proxyOwnIp:'printer.local',proxyPort:3457,proxyListenBind:'127.0.0.1',u1LoginExpires:Date.now()+60000,u1ExternalLogin:(url,callback)=>{handoff=new URL(url);complete=callback}}
 sandbox.module.exports.initAmazonProxy(options,(_error,data)=>{result=data})
 assert.equal(handoff.hostname,'www.amazon.com');assert.equal(handoff.searchParams.get('openid.oa2.code_challenge_method'),'S256');assert.equal(handoff.searchParams.has('code_verifier'),false)
 assert.throws(()=>complete('https://evil.example/'));complete(valid)
 assert.equal(result.authorization_code,'one-time-code-123');assert.ok(result.verifier.length>=43);assert.ok(result.frc);assert.throws(()=>complete(valid),/login_expired/)
})

test('regional Alexa endpoint and login base are separate per upstream contract',()=>{for(const region of ['amazon.de','amazon.com','amazon.co.uk','amazon.fr','amazon.it','amazon.es','amazon.com.au','amazon.ca'])assert.equal(loginDomain(region),'amazon.com');assert.equal(loginDomain('amazon.co.jp'),'amazon.co.jp')})

test('diagnostics retain structure only and never credentials or URL parameter values',()=>{
 const shape=returnShape('https://www.amazon.com/ap/maplanding?openid.oa2.authorization_code=TOPSECRET&email=PRIVATE#SECRETFRAGMENT')
 assert.equal(shape.landing,true);assert.equal(shape.hasFragment,true);assert.deepEqual(shape.parameters,['openid.oa2.authorization_code']);assert.doesNotMatch(JSON.stringify(shape),/TOPSECRET|PRIVATE|SECRETFRAGMENT|email/)
})
