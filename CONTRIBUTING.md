# Contributing to NimbleGuard

Thank you for helping improve NimbleGuard.

## Before you begin

- Search existing Issues before opening a new one.
- Do not attach suspicious executable files to an Issue, pull request, or discussion.
- Do not report a potential security vulnerability publicly; follow [SECURITY.md](SECURITY.md).
- Keep suggestions aligned with NimbleGuard's scope: a lightweight companion to Microsoft Defender, not a replacement antivirus engine.

## Report a bug

Include the following information:

1. NimbleGuard version and Windows version.
2. What you expected to happen and what happened instead.
3. Safe steps that reproduce the issue.
4. A screenshot or harmless log excerpt, with personal paths, names, and tokens removed.

## Suggest a feature

Explain the user problem first, then suggest a possible solution. Features that automatically delete files, disable protection, or send private data to an external service need a strong safety case.

## Development setup

```powershell
py -m pip install -r requirements.txt
py nimbleguard.py
```

## Pull requests

- Create a focused branch and keep each pull request limited to one purpose.
- Use clear Python names, type hints where useful, and Arabic comments for safety-sensitive logic.
- Preserve the app's safety defaults: no automatic deletion, no silent network upload, and clear confirmations before destructive actions.
- Explain how you tested the change on Windows.

By contributing, you agree that your contribution may be distributed under the license selected for this repository in the future.
