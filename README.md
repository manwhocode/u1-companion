# U1 Companion

Spools, printing and maintenance for Snapmaker U1. Unofficial companion UI built on Snapmaker Fluidd, with local Python services.

**Full SSH installer, early access.** Installation and rollback are tested in an isolated Linux simulation. A clean install on another physical U1 has not yet been verified; unsupported firmware or conflicting custom setups are rejected before installation.

[Русский](README.ru.md) · [Installation guide](INSTALL.md) · [Установка по-русски](INSTALL.ru.md)

## Install

Enable SSH/root access on your U1, keep it idle with heaters off, and connect from Windows Terminal or macOS Terminal:

```sh
ssh root@PRINTER_IP
```

Replace `PRINTER_IP` with your printer's address and enter its SSH password. Then paste **inside that SSH session**:

```sh
curl -fL https://raw.githubusercontent.com/manwhocode/u1-companion/main/install.sh -o /userdata/u1-companion-install.sh && sh /userdata/u1-companion-install.sh
```

Confirm the displayed plan once. The installer downloads all components, checks their hashes, backs up replaced files, installs the UI/services, restarts idle Klipper and prints the browser address. You do not need npm, Python or a desktop installer on your PC. See [INSTALL.md](INSTALL.md) for prerequisites, verification and rollback.

**Fresh user libraries are empty.** Only the public Snapmaker catalog is built in. Configure your own GPT/Amazon accounts and external access after installation; no owner's email, spools, print history or credentials are shipped.

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
- `installer/` and `install.sh`: the complete guided SSH installer, release builder and simulated tests.
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

The installer includes the full UI, accounting and maintenance, profiles/calibration services, layer pauses, drying, cover-fan controls, and all dependencies for optional Alexa, Codex and external access. Integrations remain disconnected until you configure them. Services target `/home/lava/u1-addons/filament-ui` and private state under `/userdata/u1-addons/`. Runtime binaries are checksum-pinned release assets with upstream licenses, not Git source files. Do not expose port 7125 directly.

## Contributions

Everyone may submit a Pull Request from a fork. The owner controls merges and repository write access. See CONTRIBUTING.md and SECURITY.md. Redistribution and modifications of copies are governed by GPL-3.0, not by repository permissions.

## License

GPL-3.0; see LICENSE and NOTICE.md. Snapmaker and Fluidd retain their names and upstream copyrights.

---

## Support development

Enjoying U1 Companion? Buy me a coffee! Your support helps me keep improving the product, add useful features, fix bugs and make it easier for everyone to use. Thank you for supporting the project!

<a href="https://www.buymeacoffee.com/snapIV"><picture><source srcset="frontend/src/assets/buy-me-a-coffee.svg" type="image/svg+xml"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=snapIV&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff" /></picture></a>

Follow my projects and models: [Instagram](https://www.instagram.com/3dlabstorex/) · [MakerWorld](https://makerworld.com/ru/@user_110109506) · [Snapmaker Space](https://space.snapmaker.com/en/creator/75133?tab=models).
