# Pinned public runtime components

Runtime binaries are release assets, not committed to Git. The release builder checks these hashes before publishing a package; the printer checks the release SHA256SUMS over verified HTTPS before installation.

| Component | Public source | Release asset SHA-256 |
|---|---|---|
| Node.js 22.23.4 ARM64 | https://nodejs.org/dist/v22.23.4/node-v22.23.4-linux-arm64.tar.xz | Recompressed `node-runtime.tar.gz`: `f728182437fc0f67ad80e9904870b857cd36087e2445c938bff17d5386fd9e89` |
| Codex CLI 0.162.1 ARM64 musl | npm `@openai/codex` platform package, version `0.162.1-linux-arm64` | Gzipped CLI `codex-arm64.gz`: `37e96e48cd4635733d7654d126870ab7ae69c5d5a0e686cf46e29f119b9f844d` |
| cloudflared 2026.11.0 ARM64 | https://github.com/cloudflare/cloudflared/releases/tag/2026.11.0 | `cloudflared-linux-arm64`: `abe54a006acf9faf2d19ee9d953cb0d0804e92f59c5382a162e57b84d086f56f` |

The official Node xz SHA-256 is `6287aa46b6c375d816e63ae66d024fbbfd70404825aabdfdf898a970871d2f4b`. The same tar was recompressed locally to gzip because the tested U1 Python lacks lzma. No binary content was changed. Codex was compressed locally for download; the extracted binary SHA-256 is `071cbe8d821cf1b02b6d8ba6c8b7991b228fcb8519dcb68a37d31222bb8cabe5`.

Upstream license/notice texts are retained in LICENSES/ and installed with the application. Alexa npm dependencies are identified by alexa/package-lock.json, with the two public vendor patches in alexa/. No Amazon session, API key, login state, printer data or personal library is part of these components.
