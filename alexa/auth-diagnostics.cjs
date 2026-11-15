'use strict'
const stages = { '/auth/register': 'register', '/api/users/me': 'account', '/ap/exchangetoken/cookies': 'cookies', '/api/language': 'csrf', '/spa/index.html': 'csrf', '/api/devices-v2/device': 'devices', '/api/strings': 'csrf', '/templates/oobe/d-device-pick.handlebars': 'csrf' }
const markers = ['invalid_grant', 'invalid_request', 'invalid_client', 'authorization code', 'code_verifier', 'challenge', 'cookie', 'frc', 'unauthorized', 'captcha']
function diagnostic (options, status, body, error) {
  const route = String(options.path || '').split('?')[0]
  const text = typeof body === 'string' ? body.slice(0,16000).toLowerCase() : ''
  return { stage: stages[route] || 'other', status: Number.isInteger(status) ? status : null, transport: ['ECONNRESET','ETIMEDOUT','ENOTFOUND','ECONNREFUSED','CERT_HAS_EXPIRED','UNABLE_TO_VERIFY_LEAF_SIGNATURE'].includes(error) ? error : error ? 'request_failed' : null, markers: markers.filter(marker => text.includes(marker)) }
}
module.exports = { diagnostic }
