# U1 Companion

Spools, printing and maintenance for Snapmaker U1. Unofficial companion UI built on Snapmaker Fluidd, with local Python services.

**Development source snapshot — not a tested one-click installer.** The current system has been exercised on one U1. Fresh installation on another printer and broad firmware compatibility have not been verified. Do not copy a development folder directly over printer firmware. Back up first and test on an idle printer.

## Features

- Color library and physical spool inventory, manufacturers/materials, empty-spool tare weights, remaining filament and cost accounting.
- QR labels and NTAG216 NFC workflows; browser NFC availability depends on phone/browser. iPhone writing uses an NFC app.
- Print controls, delayed start, timed pause and pauses by layer for magnets, with stock U1 methods and safety checks.
- Filament K calibration, profile inheritance, nozzle/bed temperatures, usage/error export, maintenance reminders, cover-fan night mode and bed drying.
- Optional Alexa voice notifications and GPT/Codex assistant, with separately stored credentials and configurable action confirmation.
- Optional temporary HTTPS external access with a locally generated pairing code, protected API and revocable WebSocket sessions.
- U1 Companion translations in 21 supported UI languages.

## Repository layout

- `frontend/`: current Vue 2 / Vuetify / TypeScript source and tests.
- `backend/`: current deployed Python service sources; `backend/u1_ai/` is the assistant sidecar.
- `remote-access/`: public gateway template and static resources. The control-key placeholder must be generated locally during installation.
- `alexa/`: optional unofficial Alexa bridge source and npm lockfile.
- `services/`: current service-launch references; they assume the tested U1 paths and require resource isolation.
- `tools/legacy/`: historical, incomplete installers, retained only as references.

No printer database, user spool data, API key, Amazon cookie, pairing code, TLS key, device backup, log, print model or runtime binary is included.

## Frontend development

Requires Node.js 22 or 24 and npm. From `frontend/`:

```sh
npm ci
npm run type-check
npm run test:unit -- --run tests/unit/u1Clipboard.spec.ts tests/unit/u1LocaleMessages.spec.ts tests/unit/u1ProgramSettings.spec.js
npm run build
```

The frontend host `public/config.json` is a neutral example. Configure your own local printer when running a development server. Do not use a development build to issue unattended printer commands.

## Backend checks

Python 3.11 is the tested printer runtime. From `backend/`, run individual simulated tests, for example:

```sh
python test-u1-ai.py
python test-u1-data-store.py
```

Linux/device-specific checks are separate. A passing unit test or build does not certify safe movement or recovery of a physical print. Print recovery remains experimental; verify adhesion and coordinates before any continuation.

## Installation status

A unified public installer for this full snapshot is not yet validated. Services target `/home/lava/u1-addons/filament-ui` and private state under `/userdata/u1-addons/`. They must be installed with backups, ownership, resource limits, nginx validation and rollback. Do not expose port 7125 directly. Runtime binaries must be obtained from their official sources and verified, not committed here.

## Contributions

Everyone may submit a Pull Request from a fork. The owner controls merges and repository write access. See CONTRIBUTING.md and SECURITY.md. Redistribution and modifications of copies are governed by GPL-3.0, not by repository permissions.

## License

GPL-3.0; see LICENSE and NOTICE.md. Snapmaker and Fluidd retain their names and upstream copyrights.
