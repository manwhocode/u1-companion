/** Owner's Snapmaker EU partner links. Preserve product paths and variant IDs. */
export function snapmakerReferralUrl (address: string): string {
  const url = new URL(address)
  if (url.protocol !== 'https:' || !['eu.snapmaker.com', 'snapmaker-eu.myshopify.com'].includes(url.hostname) || url.username || url.password || url.port) {
    throw new Error('Нужна ссылка магазина Snapmaker EU.')
  }
  url.hostname = 'snapmaker-eu.myshopify.com'
  url.searchParams.set('ref', 'i_v')
  return url.href
}
