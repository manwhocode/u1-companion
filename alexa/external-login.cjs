'use strict'
// Upstream example/example.js: Western regions authenticate at amazon.com;
// amazonPage remains the account's regional Alexa endpoint.
function loginDomain (region) { return region === 'amazon.co.jp' ? 'amazon.co.jp' : 'amazon.com' }
function returnShape (value) {
  try {
    const url = new URL(value)
    const known = ['openid.mode','openid.return_to','openid.assoc_handle','openid.oa2.authorization_code','openid.oa2.response_type','openid.oa2.error','code','access_token','error','error_description']
    return { host: ['www.amazon.com','www.amazon.co.jp','www.amazon.de'].includes(url.hostname) ? url.hostname : '(other)', landing: url.pathname === '/ap/maplanding', hasQuery: !!url.search, hasFragment: !!url.hash, parameters: known.filter(key => url.searchParams.has(key)) }
  } catch { return { invalid: true } }
}
// Parse a returned Amazon URL locally. Do not fetch it or accept cookies from the user.
function authorizationCode (value, region) {
  if (typeof value !== 'string' || value.length > 8000) throw new Error('invalid_return_url')
  const url = new URL(value)
  if (url.protocol !== 'https:' || url.hostname !== 'www.' + region || url.port || url.username || url.password || url.pathname !== '/ap/maplanding') throw new Error('invalid_return_url')
  const codes = url.searchParams.getAll('openid.oa2.authorization_code')
  if (codes.length !== 1 || codes[0].length < 8 || codes[0].length > 4096 || /[\s\x00-\x1f<>]/.test(codes[0])) throw new Error('missing_authorization_code')
  return codes[0]
}
module.exports = { authorizationCode, loginDomain, returnShape }
