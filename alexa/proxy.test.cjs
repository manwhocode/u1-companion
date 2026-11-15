const test = require('node:test'), assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path')
const sourceFile=path.join(__dirname,'node_modules/alexa-cookie2/lib/proxy.js')
const middleware=[]; let listener
const app={use:fn=>middleware.push(fn),get:()=>{},listen:(port,host)=>{listener={port,host};const server={on:()=>server,address:()=>({port})};return server}}
const proxyOptions=[]
const memory=new Map()
const context={module:{exports:{}},Buffer,URL,console,__dirname:path.dirname(sourceFile),require:name=>{
 if(name==='express')return ()=>app
 if(name==='http-proxy-middleware')return {createProxyMiddleware:(_ctx,opts)=>{proxyOptions.push(opts);return ()=>{}}}
 if(name==='http-proxy-response-rewrite')return ()=>{}
 if(name==='fs')return {existsSync:()=>false,writeFileSync:(name,value)=>memory.set(name,value)}
 return require(name)
}}
vm.runInNewContext(fs.readFileSync(sourceFile,'utf8'),context)
const options={proxyOwnIp:'printer.local',proxyPort:3457,proxyExternalPort:3443,proxyProtocol:'https',proxyListenBind:'127.0.0.1',baseAmazonPage:'amazon.de',baseAmazonPageHandle:'de',amazonPageProxyLanguage:'de_DE',acceptLanguage:'en-US',proxyLogLevel:'silent',formerDataStorePath:'/private/registration.json',u1LoginToken:'a'.repeat(64),u1LoginExpires:Date.now()+60000}
context.module.exports.initAmazonProxy(options)
function request(url,cookie){let passed=false,status=200,headers={},location;const req={url,headers:{cookie:cookie||''}};const res={status:n=>{status=n;return res},send:()=>{},setHeader:(key,value)=>headers[key]=value,redirect:(code,url)=>{status=code;location=url}};middleware[0](req,res,()=>passed=true);return {passed,status,headers,location,cookie:req.headers.cookie}}
test('login listener binds only loopback on internal port',()=>assert.deepEqual(listener,{port:3457,host:'127.0.0.1'}))
test('requests without a capability cookie are rejected',()=>assert.equal(request('/').status,403))
test('connect creates a secure HttpOnly cookie and discards token URL',()=>{const r=request('/connect/'+'a'.repeat(64));assert.equal(r.status,302);assert.equal(r.location,'/');assert.match(r.headers['Set-Cookie'],/Secure; HttpOnly; SameSite=Lax/)})
test('only correct cookie passes and gate secret is never forwarded to Amazon',()=>{const r=request('/','u1_alexa_login='+'a'.repeat(64)+'; session-id=123');assert.equal(r.passed,true);assert.doesNotMatch(r.cookie,/u1_alexa_login/);assert.match(r.cookie,/session-id=123/);assert.equal(request('/','u1_alexa_login='+'b'.repeat(64)).status,403)})
test('expired login is rejected even with previously valid cookie',()=>{options.u1LoginExpires=Date.now()-1;assert.equal(request('/','u1_alexa_login='+'a'.repeat(64)).status,403)})
