# Full SSH installation

The installer runs on **Snapmaker U1**, not on your computer. Windows/macOS only provide the SSH terminal. Installation, uninstallation and updating have been successfully tested by the author on a physical U1. Most features have also been tested and work. Automated isolated Linux tests cover installation and rollback. This remains an early-access release.

## Three steps

1. Enable SSH/root access using your U1 firmware settings. Keep the printer idle, with all heater targets at zero. Finish/cancel any scheduled job, drying session or calibration; turn night mode and external access off before updating. Keep other controllers idle until installation finishes.
2. Open Windows Terminal or macOS Terminal and run `ssh root@PRINTER_IP`, replacing `PRINTER_IP` with the printer's LAN address. Use your printer's SSH password. Verify the SSH host fingerprint belongs to your printer when connecting for the first time.
3. Paste this command in the SSH session, review the plan, and type `y`:

```sh
curl -fL https://raw.githubusercontent.com/manwhocode/u1-companion/main/install.sh -o /userdata/u1-companion-install.sh && sh /userdata/u1-companion-install.sh
```

If the printer has wget but no curl, use this download command instead:

```sh
wget -O /userdata/u1-companion-install.sh https://raw.githubusercontent.com/manwhocode/u1-companion/main/install.sh && sh /userdata/u1-companion-install.sh
```

Wait for `Installation verified` and open the printed HTTP address. The installed settings contain the HTTPS certificate/trust instructions. Certificates and remote pairing codes are generated separately on each printer. Never install a certificate supplied by someone else's printer.

## What is installed

One complete package: Companion UI with all 21 existing translations and built-in Snapmaker catalog; spool/color/empty-spool libraries and accounting; print controls and pauses; maintenance, K calibration and temperature profiles; drying and cover-fan controls; Alexa bridge, Codex runtime and protected external-access dependencies. Amazon/OpenAI login and enabling external access remain your own setup steps in Companion settings. They are off/disconnected on a fresh installation.

No personal library is preloaded. The release contains no owner's email, account, key, printer address, certificate, NFC tag, private spool/color, print file, history, chat, log or backup. Third-party license/copyright notices are retained. The author's explicitly configured Snapmaker referral link remains in the public product catalog.

## Requirements and automatic checks

- Linux ARM64 U1 with root SSH access, stock Python 3.11+, nginx, OpenSSL and start-stop-daemon; internet access with valid system CA certificates.
- CPU/memory cgroup isolation must already be available. AI, Alexa and the external-access service receive separate CPU/memory limits; printer services stay outside these groups.
- At least 1.5 GiB free under `/userdata` for downloads, staging and backup. No automatic deletion of your existing files or old backups. Temporary runtime downloads are removed after success.
- Four-head U1 API and known native pause implementation. The installer refuses firmware variants that have not been checked; it does not silently omit features.
- Existing hand-installed HTTPS/provisioning sites require review/migration. Updates from this unified installer are supported; arbitrary historical development installations are not automatically migrated.
- If `/oem/.debug` is absent, the installation plan explains that it will enable persistence across reboots. This also retains other system-layer changes. The single confirmation covers this change.

No print, heater or motion command is sent by the installer. It adds marked configuration includes and owned modules, validates nginx, restarts idle Klipper, then verifies fresh service heartbeats, resource limits and the protected gateway. Original stock Fluidd JS, native pause macros, virtual_sdcard.py and user data are not replaced.

## Check without installing

After downloading the current bootstrap, use `sh /userdata/u1-companion-install.sh --update` to update or `sh /userdata/u1-companion-install.sh --uninstall` to remove an inventoried installation. Removal backs up owned files and preserves personal state/certificates and the shared `/oem/.debug` flag. Historical manual installations require migration review before automatic removal.

After downloading the script, run:

```sh
sh /userdata/u1-companion-install.sh --check
```

This downloads/verifies the small installer and checks the U1 API, safety state and known firmware without installing application files or restarting services.

## Backup and rollback

The installer prints a unique backup directory under `/userdata/u1-addons-backups/unified-...`. It contains the replaced files, transaction journal, prior service list and a separate read-only snapshot of library/inventory/accounting records. Keep it private. Normal file rollback preserves current user libraries and credentials; it does not import the data snapshot automatically.

When the printer is idle, use the **exact path printed during your installation**:

```sh
sh /userdata/u1-companion-install.sh --rollback /userdata/u1-addons-backups/unified-YOUR-BACKUP
```

On an installation failure, automatic rollback is attempted. If a target has changed concurrently, a print started, or the previous files cannot be safely restored, rollback stops and prints the backup path for review. Do not blindly overwrite printer.cfg or repeat an installation while the printer is busy. Loss of power during installation requires reviewing that transaction/backup; this alpha installer does not promise unattended crash recovery.

## For maintainers

`python -m unittest discover -s installer/tests -v` exercises an isolated filesystem and fake APIs. It does not control hardware. The release builder uses tracked source, a clean neutral frontend build and pinned runtime archives; it rejects private paths/key patterns and generates SHA256SUMS. See [RUNTIMES.md](installer/RUNTIMES.md) for binary provenance.
