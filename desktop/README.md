# Universal Windows launcher

[Download U1-Companion-Setup.exe](https://github.com/manwhocode/u1-companion/releases/download/windows-installer-v1.0.1/U1-Companion-Setup.exe)

Portable Windows x64 application. Python and SSH dependencies are bundled; Windows administrator access is not required. This EXE does not install an application on the PC: it operates on your U1 over SSH.

1. Enable root SSH on the printer, keep it idle and heaters off.
2. Open the EXE, read the license/warnings and check the acknowledgement box.
3. Enter your printer IP. The factory root password is used automatically. If you changed it, check **I changed the SSH password** and enter your own password. Select **Install**, **Update** or **Uninstall**.
4. On first connection, verify the displayed SSH fingerprint. Review and confirm the operation plan in the console. Keep the window/power open until completion.

The module version is **not embedded**. Every operation fetches the current official `main/install.sh` over verified HTTPS; that script selects and verifies the current module release. The same EXE can be used for future compatible module releases. Credentials are not included or saved. Only the printer's public SSH key is saved locally; changed keys are rejected.

Uninstall is available for installations managed by the unified installer. It backs up owned files, removes program components and restores native Fluidd routes. Personal libraries, credentials, logs, certificates and the shared persistence flag remain. It refuses modified owned files and legacy/manual installations without a removal inventory. It never resets printer firmware or performs print/heating/motion commands.

The bundled agreement explains GPL-3.0, no warranty, risks and liability limits subject to applicable law. It cannot exclude mandatory legal rights. Original GPL text and third-party notices are bundled; this acknowledgement adds no restrictions to GPL rights.

The EXE is not code-signed, so Windows may show an unknown-publisher warning. Verify the release checksum and obtain it from this repository. Do not disable security protections. The source remains available here.

To build on Windows in an isolated Python environment:

```sh
python -m pip install -r desktop/requirements-build.txt
python desktop/build_windows.py --output desktop/dist
```

The build runs `--self-test`, which checks packaged dependencies and license resources without accepting the agreement or contacting a printer. The author has successfully tested Windows installation, updating and removal on a physical U1. The macOS Terminal launcher uses the same verified SSH installer; its actual execution still requires a Mac test.

The current launcher resolves the latest published GitHub release with a cache-busting request, verifies the bootstrap checksum and matching release version, and prints the selected version before preflight. Download the new launcher once to replace older launchers that used cached main/install.sh.
