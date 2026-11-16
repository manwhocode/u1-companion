#!/bin/bash
# Portable macOS Terminal launcher. Uses Apple's SSH, no password storage.
set -eu
cd "$(dirname "$0")"
printf '\nU1 Companion — macOS\nInstall / Update / Uninstall over SSH\n\n'
printf 'Enable Root Access / SSH on U1 first. Keep the printer idle with heaters off.\n'
printf 'Read LICENSE and AGREEMENT.en.txt bundled beside this launcher.\n'
cat AGREEMENT.en.txt
printf '\nI have read the license, warranty disclaimer and liability limits [yes/NO]: '
read -r consent
case "$consent" in yes|YES) ;; *) echo 'Cancelled'; exit 1;; esac
printf 'Printer IP or hostname: '
read -r printer_host
if [[ ! "$printer_host" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]]; then echo 'Invalid address'; exit 1; fi
printf '\n1 Install\n2 Update\n3 Uninstall\nChoose [1/2/3]: '
read -r choice
case "$choice" in 1) action=install;; 2) action=update;; 3) action=uninstall;; *) echo 'Cancelled';exit 1;; esac
printf '\nSSH login: root. Factory password: snapmaker (or your changed password).\nVerify the SSH host fingerprint before accepting it. Password input is hidden.\n'
ssh -t -o StrictHostKeyChecking=ask -o ConnectTimeout=15 "root@$printer_host" "python3 -c 'import pathlib,urllib.request; p=pathlib.Path(\"/userdata/u1-companion-macos-bootstrap.sh\"); assert not p.is_symlink(); data=urllib.request.urlopen(\"https://raw.githubusercontent.com/manwhocode/u1-companion/main/install.sh\",timeout=30).read(65537); assert len(data)<=65536; p.write_bytes(data); p.chmod(0o700)' && sh /userdata/u1-companion-macos-bootstrap.sh --$action"
printf '\nFinished. Press Enter to close. '
read -r done
