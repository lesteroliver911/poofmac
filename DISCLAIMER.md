# PoofMac — Disclaimer

**PoofMac is provided "as is", without warranty of any kind**, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and non-infringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

## What PoofMac does

PoofMac uses an AI language model (local via Ollama or a cloud API) to analyse your Mac's disk usage and *propose* files or directories for deletion. Every proposed deletion is shown to you for explicit approval before anything is removed. **PoofMac never deletes files without your confirmation.**

## Your responsibility

- **Always maintain a current backup** (Time Machine, iCloud, or a third-party cloud backup) before running any disk-cleaning operation. The app will ask you to confirm this before you can proceed.
- Review every item in the deletion list carefully. Once a file is deleted it may not be recoverable.
- Do not run PoofMac as root (`sudo`). The safety guardrails in [`mac_cleaner/safety.py`](mac_cleaner/safety.py) are designed for normal user-level access.

## Not affiliated with Apple

PoofMac is an independent open-source project. It is **not affiliated with, endorsed by, or in any way associated with Apple Inc.** "macOS", "Mac", "Time Machine", and "iCloud" are trademarks of Apple Inc.

## Safety guardrails

Hard-coded protected paths (system directories, kernel extensions, user home directory dotfiles, etc.) are defined in [`mac_cleaner/safety.py`](mac_cleaner/safety.py). The LLM is also instructed in its system prompt to refuse operations on protected paths. Neither layer is infallible — your own judgement is the final safety check.

## Licence

MIT — see [LICENSE](LICENSE) for full text.
