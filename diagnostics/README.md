# Acer WMI Read-Only Diagnostic

This diagnostic helps investigate safe ForcaNitro compatibility for Acer models that expose the `AcerGamingFunction` WMI interface.

It is separate from the main application and does not control the fans.

## Safety And Privacy

The script:

- Invokes only Acer WMI methods whose names start with `Get`.
- Never invokes `SetGamingFanSpeed`, `SetGamingFanBehavior`, `SetGamingFanTable`, or any other `Set` method.
- Does not access the internet or upload the report.
- Does not read serial numbers, SNID, usernames, files, or personal data.
- Records the notebook manufacturer/model, BIOS version, Windows version, available `Get` methods, and known read-only fan/sensor responses.

The generated JSON report remains on the computer. Review it before sharing it.

## Run It

1. Open Windows PowerShell as Administrator.
2. Open the cloned ForcaNitro repository folder.
3. Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\diagnostics\collect_acer_wmi_readonly.ps1
```

The report is created at:

```text
diagnostics\ForcaNitro-WMI-Diagnostic.json
```

Reports are ignored by Git so they are not committed accidentally.

## Why Administrator Is Required

On Acer notebooks, Windows may deny access to `root\wmi:AcerGamingFunction` even for read-only methods unless PowerShell is elevated.

## Current Research Status

Community projects indicate that some newer Acer Nitro and Predator models support fan control through `AcerGamingFunction`. This may provide a safer compatibility path than writing unknown embedded-controller addresses.

Read-only validation on an Acer Nitro AN515-58 with BIOS V2.19 successfully returned fan target percentages, CPU/GPU temperatures, CPU/GPU RPM, fan behavior, fan table, and platform profile.

ForcaNitro now uses the validated Acer WMI platform-profile method to switch between `Balanced` and `Performance` on the tested AN515-58. WMI fan writes are still not enabled and will not be added for another model until its read-only and write behavior are safely validated.
