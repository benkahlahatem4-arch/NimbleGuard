# NimbleGuard

**A lightweight Windows security companion.** NimbleGuard brings safe system-maintenance tools, startup review, and Microsoft Defender controls into one clear desktop interface.

واجهة عربية خفيفة لمراجعة الحماية، عناصر بدء التشغيل، وتنظيف الملفات المؤقتة بأمان على Windows.

> [!WARNING]
> NimbleGuard is a companion to Microsoft Defender, not a replacement antivirus engine. It does not promise to detect every threat and it never deletes a file automatically.

## Download

Download the current beta from the [NimbleGuard v0.6 release](https://github.com/benkahlahatem4-arch/NimbleGuard/releases/tag/v0.6):

1. Under **Assets**, download `NimbleGuard_v0_6.exe`.
2. Run the file normally. Python is not required for the packaged application.
3. Windows may show a SmartScreen warning because the application is not code-signed yet. Download only from this repository's official Releases page and verify the SHA-256 hash below before deciding whether to run it.

## Verify the v0.6 download

Expected SHA-256 for `NimbleGuard_v0_6.exe`:

```text
B99056FF64EA87DA93ECDB22CA478D5D26BEDF00D98251B371FEA689D1E8B9B9
```

In PowerShell, run this in the folder that contains the downloaded file:

```powershell
Get-FileHash .\NimbleGuard_v0_6.exe -Algorithm SHA256
```

The result must match exactly. The checksum is also available in [SHA256SUMS.txt](SHA256SUMS.txt).

## Features

- **Microsoft Defender integration:** show protection status, update signatures, and request quick or full Defender scans.
- **Local, explainable file review:** checks selected files or folders for local risk indicators such as extensions, suspicious names, locations, script markers, and SHA-256 hashes.
- **Manual quarantine:** moves a user-selected file to a local quarantine and supports restore. No automatic quarantine or deletion is performed.
- **Startup manager:** displays current-user startup entries and can disable or restore an entry without deleting it.
- **Safe cleanup:** clears only older files from the current user's temporary folder. It does not touch documents, photos, Downloads, the registry, or running processes.
- **Lightweight monitoring:** optional review of new executable files in Downloads; it is disabled by default.
- **System dashboard:** displays CPU, RAM, disk, GPU, and high-memory processes using local system data.

## Safety and privacy

- The app does not upload files or scan results to the internet.
- A risk label is a review signal, not proof that a file is malware.
- Review the file path, source, signature, and Microsoft Defender result before allowing, quarantining, or removing anything.
- Do not add security exclusions for an unknown executable merely to make it run.

## Run from source

Requirements: Windows, Python 3.10+, and PowerShell with Microsoft Defender available for Defender features.

```powershell
py -m pip install -r requirements.txt
py nimbleguard.py
```

You can also double-click [Launch_NimbleGuard.vbs](Launch_NimbleGuard.vbs) after installing the requirements.

## Contributing

Bug reports, UI feedback, translations, documentation, and focused pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request.

For security-sensitive reports, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Roadmap

- More complete Arabic, English, and French translations.
- Automated tests for the risk-scoring and quarantine safeguards.
- Improved accessibility and clearer user guidance.
- Reproducible builds and a code-signing path when funding becomes available.

## License

No open-source license has been selected yet. Until a license is added, normal copyright rules apply to the source code.
