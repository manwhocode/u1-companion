# U1 Companion Alexa skill privacy notice

Last updated: 18 November 2026.

U1 Companion is an independent, self-hosted printer companion. The personal Alexa skill connects an Amazon account to the printer installation chosen by its owner. It is not an Amazon or Snapmaker product.

## Data used by the voice skill

Amazon processes voice recordings and speech recognition under Amazon's own privacy terms. This skill does not receive microphone recordings. Amazon supplies recognized intents and parameters, such as a pairing code, a timer duration or a requested model name, together with account, session and request identifiers and the request language.

The Amazon-hosted relay forwards only the fields needed to route and authenticate the request to the owner's configured printer endpoint over authenticated HTTPS. Alexa API access tokens are not forwarded. The printer stores a hash of the Alexa user identifier to check the account pairing. Requested printer status and action results are returned through Amazon so Alexa can speak them. Status or model requests may reveal printer activity or file/model names to Amazon and people who can hear the device.

The voice relay does not request your name, postal address, email address, phone number, Amazon password, payment details or Alexa microphone recordings. It does not sell personal data, provide advertising or enable purchases.

## Storage and service providers

Pairing configuration and authentication secrets are stored privately on the owner's printer; the relay configuration is stored in the owner's Alexa-hosted project. The printer keeps request identifiers and replies to prevent duplicate actions. Entries older than 24 hours are pruned when new requests are processed; inactive installations may retain the last file until another request or owner deletion. Other printer histories and Companion records have their own local retention and are not erased by disabling the skill.

The supplied relay code does not deliberately log request envelopes, pairing codes, account identifiers or authentication keys. Amazon hosting and any external tunnel provider can process operational and network metadata under their own terms. If the owner uses the optional Cloudflare tunnel, Cloudflare also handles the HTTPS connection to the printer. No central U1 Companion account or developer-operated collection server is required by this implementation.

## Owner control and removal

The printer owner controls the installation and who may pair with it. Disable voice control in Companion and disable the skill in Alexa to stop using it. Disabling access does not automatically delete existing local files or backups. The owner can remove the private voice configuration and request records from their printer and remove the private relay configuration from their Alexa-hosted project. Keep credentials out of public repositories, issues and exports.

For questions about this implementation or removal instructions, contact the project through [GitHub issues](https://github.com/manwhocode/u1-companion/issues). Do not include private identifiers, addresses, pairing codes, credentials or printer files in a public issue. For data held by Amazon or your tunnel provider, use that provider's privacy controls and support.
