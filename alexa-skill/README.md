# Personal Alexa voice control

[Инструкция на русском](README.ru.md)

This skill receives commands. The existing Alexa bridge speaks notifications; the two connections are independent. No GPT key or Home Assistant is required. Voice control is disabled by default. The relay runs inside your own Alexa-hosted skill, not on the author's server. Amazon determines hosting availability and quotas for your account.

1. Update Companion to alpha.15 or newer. Enable external access and verify the printer's public HTTPS URL. Do not forward the Moonraker port on your router.
2. Sign in at https://developer.amazon.com/alexa/console/ask with the account that owns the Echo. Complete developer registration and review any terms yourself if prompted.
3. Create a Custom skill, Alexa-hosted (Python), in English (US) or German (DE). Development testing does not require publishing it in the store.
4. Copy the Skill ID into Companion → Settings → Alexa → Voice control. The endpoint is your external URL followed by `/u1-alexa/skill`.
5. Set up the connection and download skill settings. This generates a **private config.json containing the HMAC secret**. Never publish it in GitHub, messages or library exports. Setting up again rotates the key, disables commands and clears the old account binding.
6. In Amazon's Code tab, use `lambda/lambda_function.py` and `lambda/voice_messages.json` and put the downloaded private `config.json` beside it. Handler: `lambda_function.lambda_handler`. No dependencies are needed. Save and Deploy. The empty public config.json is only a template.
7. In Build → Interaction Model → JSON Editor import the matching locale JSON from `models/`. Save and Build Model. Set Test to Development. Echo must use the same account and the model's language.
8. Enable voice control in Companion, then get a pairing code. Within five minutes say “Alexa, open Printer Helper”, then “link printer with code [six digits]”. For German: “Alexa, öffne Druck Helfer”, then “Drucker verbinden mit [code]”. Wait for the spoken pairing acknowledgement.
9. Start with “printer status” and “time remaining”. Test movement/printing only while at the printer with a separate test model.

The package contains 326 sample phrases across nine languages (regional copies excluded), with 16 locale models in `models/`. They cover resume, repeat last print, cancel, pause, pause with lowered bed, timed pause, cancel resume timer, favorite model by name, cover-fan night mode on/off, status/progress, estimated remaining time, errors and maintenance.

Launches, resumes, cancellations, bed movement and timed automatic resumption require Yes/No confirmation. Confirmations expire after a minute and are bound to the current Alexa session. Repeat/favorite starts use T1–T4 → heads 1–4 and bed leveling; the skill names the file before asking to confirm the clear bed and loaded spools. Use the normal UI for a different mapping. Existing Companion checks revalidate the job, file, spools and motion state.

“Alexa Stop” ends the dialogue; use the explicit “cancel the print” command for print cancellation. Stop is different from pause. No voice emergency-stop replacement is provided. Night mode affects only cover fans and retains temperature protections; switching it off restores native fan control.

Requests are signed, paired to the Amazon account, timestamp-checked and deduplicated. A timeout never automatically retries a command; check the printer before issuing another command. A spoken “request sent” does not mean motion has completed. Pairing authenticates an account, not an individual voice; other people near devices on that account can speak commands.

Queued control commands expire after six seconds, so a stalled service cannot execute an old command much later. The verified stock filament-tangling warning permits manually confirmed resumption after the cause is fixed; other active faults remain blocked. Timed automatic resumption does not bypass this warning.

If the tunnel URL changes, update only `url` in your private skill config.json and Deploy again. Disable voice control and external access before updating or uninstalling Companion. Physical Echo recognition, Amazon deployment and real printer command tests still require user verification; automated tests do not prove those steps.


## Languages / Языки

| Language | Locales | Invocation |
|---|---|---|
| en | en-AU, en-CA, en-GB, en-IN, en-US | printer helper |
| de | de-DE | druck helfer |
| fr | fr-CA, fr-FR | assistant imprimante |
| es | es-ES, es-MX, es-US | ayudante impresora |
| it | it-IT | assistente stampante |
| pt | pt-BR | assistente impressora |
| nl | nl-NL | printer assistent |
| ja | ja-JP | プリントヘルパー |
| ar | ar-SA | مساعد الطابعة |

Use Language Settings → Sync Locales to share one model across regional variants. Dutch favorites use a number in the order of the favorite-model list (for example, “druk favoriet nummer één af”); Alexa does not support free-name SearchQuery slots in Dutch. The filename is always read back before confirmation. Other languages support the model name.

These public translations, models and empty configuration templates can be shared and reused. Each user creates their own hosted skill and private connection/pairing; never share the generated key, Amazon account or printer URL as a preset. UI translations remain independent of Amazon wording. UI-only languages cannot be made into Alexa recognition languages by translation.
