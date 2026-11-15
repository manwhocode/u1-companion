// Remote gateway is online-only. Retire older offline precache workers.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil((async () => { await self.clients.claim(); await self.registration.unregister(); })()));
