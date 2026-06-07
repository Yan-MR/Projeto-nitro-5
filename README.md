# ForcaNitro

ForcaNitro is a small Windows utility for manual fan control on Acer Nitro notebooks when NitroSense is broken, stuck in the background, or no longer opens correctly.

It was built for a real Acer Nitro 5 setup where the original NitroSense app stopped working, but the embedded controller could still be controlled through `ec-probe.exe`.

> Compatibility note: this project has only been tested on an Acer Nitro 5 AN515-58-54UH / NH.QJCAL.004 notebook, with NitroSense V31 / NitroSense Service 3.01.3052. It may not work on other Acer Nitro, Predator, or Aspire models without changing the EC addresses.

![ForcaNitro dashboard](docs/assets/forcanitro-dashboard.png)

## Download

Download the latest release from:

https://github.com/Yan-MR/Projeto-nitro-5/releases/latest

Release assets usually include:

- `ForcaNitro.exe`: the ForcaNitro app.
- `NoteBookFanControl.1.6.3.setup.exe`: optional NBFC installer, included for convenience because ForcaNitro needs `ec-probe.exe`.

If you prefer, download NBFC directly from the original project:

https://github.com/hirschmann/nbfc

## What It Does

- Provides a NitroSense-inspired PyQt6 interface.
- Controls CPU and GPU fan speed through NoteBook FanControl's `ec-probe.exe`.
- Offers three quick profiles:
  - `Auto`: returns fan control to BIOS/motherboard logic.
  - `Max`: sets CPU and GPU fans to 100%.
  - `Fixed`: sets CPU and GPU fans to 40%.
- Offers a `Custom` profile with separate CPU/GPU fan sliders and a linked mode enabled by default.
- Shows animated fan dials with real RPM readings where available.
- Detects the current EC fan-control state on startup and marks the real `Auto`, `Max`, `Fixed`, or `Custom` mode instead of assuming `Auto`.
- Reads and switches the Acer platform profile between `Balanced` and `Performance` through `AcerGamingFunction` WMI on the tested AN515-58.
- Can redirect the physical NitroSense keyboard button to open/focus ForcaNitro.

## Important Safety Warning

ForcaNitro writes directly to embedded controller registers. This is model-specific and can be risky if used on unsupported hardware.

The current EC writes are:

| Purpose | Address | Value |
| --- | --- | --- |
| Unlock sequence | `0x03` | `0x11` |
| Unlock sequence | `0x22` | `0x0C` |
| Unlock sequence | `0x21` | `0x30` |
| CPU fan speed | `0x37` | percentage as hex |
| GPU fan speed | `0x3A` | percentage as hex |
| Return to BIOS/auto | `0x22` | `0x04` |
| Return to BIOS/auto | `0x21` | `0x10` |

Use this only if you understand the risk. Keep temperatures monitored after changing fan modes.

The Acer `Performance` platform profile may increase power use, temperatures, and fan activity. Switch back to `Balanced` if temperatures or system behavior become abnormal.

## Tested Environment

This is the only tested setup so far:

- Notebook: Acer Nitro 5 AN515-58-54UH / NH.QJCAL.004 family
- OS: Windows 11
- BIOS: `V2.19`
- NitroSense AppX: `AcerIncorporated.NitroSenseV31`
- NitroSense package seen during testing: `3.1.3052.0`
- NitroSense Service: `3.01.3052`
- Quick Access Service: `3.00.3052`
- Fan backend: NoteBook FanControl `ec-probe.exe`
- Expected `ec-probe.exe` path:

```text
C:\Program Files (x86)\NoteBook FanControl\ec-probe.exe
```

## Requirements

- Windows 10/11
- Python 3.13 tested, other Python 3 versions may work
- PyQt6
- NoteBook FanControl installed, with `ec-probe.exe` available
- Optional: NVIDIA driver with `nvidia-smi` available for GPU temperature/load monitoring

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

## Third-Party Credits

ForcaNitro uses `ec-probe.exe` from [NoteBook FanControl / NBFC](https://github.com/hirschmann/nbfc) by Stefan Hirschmann as the low-level fan control backend.

NBFC is a separate open-source project that provides fan control tooling for notebooks. ForcaNitro does not include or modify NBFC source code; it expects NoteBook FanControl to be installed separately and calls the local `ec-probe.exe` executable to write the EC values used by this project.

Some ForcaNitro releases may include the original unmodified NBFC installer as a convenience asset. Please check the [NBFC repository](https://github.com/hirschmann/nbfc), its source code, and its license before redistributing any NBFC binaries.

The Acer WMI profile and fan-control research was also informed by the open-source [Acer-Predator-Scripts](https://github.com/rafradek/Acer-Predator-Scripts) and [AeroForge NitroSense Alternative](https://github.com/noahcabral/aeroforge-nitrosense-alternative) projects. ForcaNitro currently uses WMI only for the tested AN515-58 platform-profile selector; its existing fan writes still use the documented EC profile above.

## Running From Source

```powershell
python app_ventoinha.py
```

Opening the app does not change fan speed automatically. Fan commands run only when you click a mode button.

The Windows executable requests administrator access when opened because EC writes and Acer WMI access require elevation. Opening ForcaNitro only reads and displays the current fan/profile state; it does not automatically change either mode.

## Building The EXE

Install PyInstaller:

```powershell
pip install pyinstaller
```

Build:

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --uac-admin --name ForcaNitro app_ventoinha.py
```

The generated executable will be:

```text
dist\ForcaNitro.exe
```

## Using The App

1. Install NoteBook FanControl.
2. Confirm `ec-probe.exe` exists at:

```text
C:\Program Files (x86)\NoteBook FanControl\ec-probe.exe
```

3. Run `ForcaNitro.exe` or `python app_ventoinha.py`.
4. Choose a profile:
   - `Auto`: return control to the BIOS.
   - `Max`: run CPU and GPU fans at 100%.
   - `Fixed`: run CPU and GPU fans at 40%.
   - `Custom`: choose CPU and GPU fan targets separately, or keep `Link CPU/GPU` enabled for one shared value.
5. On the tested AN515-58, choose `Balanced` or `Performance` in the Acer profile selector.
6. Watch temperatures after applying any manual fan or performance profile.

The Acer platform-profile selector is separate from fan control. It uses the firmware `AcerGamingFunction.SetGamingMiscSetting` WMI method and confirms the selected profile through a readback. Writes are currently enabled only when Windows reports an `AN515-58` model.

## Monitoring Notes

Older releases used visual/demo values in the monitoring graph. Current builds do not fake temperature or usage data.

- CPU usage is read locally through the Windows API.
- CPU temperature is read locally from the AN515-58 EC profile when available.
- NVIDIA GPU temperature and usage are read locally through `nvidia-smi` when available.
- Fan RPM is read locally from the AN515-58 EC profile when available.
- Unavailable readings are shown as `--` instead of simulated values.

ForcaNitro does not send telemetry anywhere and does not collect serial numbers, SNID, or personal data.

## NitroSense Keyboard Button Redirect

On the tested AN515-58 setup, the physical NitroSense keyboard button is handled by Acer's NitroSense/Quick Access services. When the original NitroSense app is broken, pressing the key can spawn `NitroSense.exe` and leave it stuck in the background.

This project includes a reversible redirect flow:

- `nitrosense_key_redirect.ps1`
  - Keeps Acer's `PSAgent.exe` listener alive.
  - Detects broken `NitroSense.exe` launches.
  - Closes them.
  - Opens or focuses `ForcaNitro.exe`.
- `install_nitrosense_key_redirect.ps1`
  - Installs a scheduled task that starts the redirect watcher at logon.
- `install_nitrosense_task_redirect.ps1`
  - Backs up the original Acer `NitroSense` scheduled task.
  - Redirects that task to the elevated ForcaNitro key launcher.
- `nitrosense_key_launch.ps1`
  - Opens or focuses ForcaNitro through the elevated NitroSense scheduled task.
  - Does not change the fan mode or Acer platform profile.
- `restore_nitrosense_task.ps1`
  - Restores the backed-up Acer scheduled task.
- `uninstall_nitrosense_key_redirect.ps1`
  - Removes the redirect watcher task and related registry leftovers.

Install the keyboard redirect from an elevated PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install_nitrosense_key_redirect.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install_nitrosense_task_redirect.ps1
```

After installation, press the NitroSense key. It should open or focus ForcaNitro.
The redirected key opens ForcaNitro through a highest-privilege scheduled task and does not automatically change fan or Acer platform profiles.

To remove the redirect:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\uninstall_nitrosense_key_redirect.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\restore_nitrosense_task.ps1
```

## Notes For Other Models

If you want to test this on another Acer notebook:

1. Do not assume the EC addresses are the same.
2. Back up your current NitroSense/Quick Access tasks before changing anything.
3. Verify the fan registers for your exact model.
4. Test `Auto` first so you know how to return control to BIOS.
5. Share your model, NitroSense version, and working EC addresses if you confirm compatibility.

Community compatibility notes:

- `AN515-45`: one user reported that fan control worked when running as administrator, but this is not fully validated yet.
- `AN517-54`: one user reported that fan control did not work with the current AN515-58 EC profile. This model likely needs different EC registers.

Future support for other models should be handled through explicit, validated model profiles instead of guessing EC addresses. Compatibility checks may read the non-personal Windows model name locally, but ForcaNitro does not upload machine identifiers.

### Read-Only Compatibility Diagnostic

Some Acer models expose an `AcerGamingFunction` WMI interface with dedicated fan and platform-profile methods, while others may still need model-specific EC addresses. The safest way to expand compatibility is to collect read-only evidence first.

The repository includes an optional diagnostic:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\diagnostics\collect_forcanitro_compatibility.ps1
```

The diagnostic does not change fan settings, access the internet, collect serial/SNID values, or upload anything. It calls only Acer WMI `Get*` methods and selected `ec-probe.exe read` commands, then creates a local JSON report with notebook model, BIOS/Windows versions, available Acer WMI methods, known read-only WMI responses, selected EC bytes, and optional `nvidia-smi` GPU readings.

Review the JSON before choosing to share it.

See [`diagnostics/README.md`](diagnostics/README.md) for the complete field and privacy description.

## Portuguese / PT-BR

ForcaNitro e uma ferramenta pequena para Windows feita para controlar manualmente as ventoinhas de notebooks Acer Nitro quando o NitroSense original para de funcionar, fica preso em segundo plano ou nao abre corretamente.

> Nota de compatibilidade: este projeto foi testado somente em um Acer Nitro 5 AN515-58-54UH / NH.QJCAL.004, com NitroSense V31 / NitroSense Service 3.01.3052. Outros modelos podem usar enderecos EC diferentes.

### Download

Baixe a versao mais recente em:

https://github.com/Yan-MR/Projeto-nitro-5/releases/latest

Os arquivos da release normalmente incluem:

- `ForcaNitro.exe`: aplicativo ForcaNitro.
- `NoteBookFanControl.1.6.3.setup.exe`: instalador opcional do NBFC, incluido por conveniencia porque o ForcaNitro precisa do `ec-probe.exe`.

Se preferir, baixe o NBFC diretamente do projeto original:

https://github.com/hirschmann/nbfc

### O Que Ele Faz

- Interface em PyQt6 inspirada no NitroSense.
- Controle de ventoinhas via `ec-probe.exe` do NoteBook FanControl.
- Perfis rapidos:
  - `Auto`: devolve o controle para a BIOS/placa-mae.
  - `Max`: coloca CPU e GPU em 100%.
  - `Fixo`: coloca CPU e GPU em 40%.
  - `Custom`: permite controlar CPU e GPU separadamente, com opcao de vincular as duas barras.
- Leitura e troca do perfil Acer entre `Balanced` e `Desempenho` via WMI `AcerGamingFunction` no AN515-58 testado.
- Mostradores animados com leitura real de RPM quando disponivel.
- Deteccao do estado EC atual ao abrir, marcando o modo real `Auto`, `Max`, `Fixo` ou `Custom` em vez de assumir `Auto`.
- Redirecionamento opcional da tecla fisica NitroSense para abrir/focar o ForcaNitro.

### Como Usar

1. Instale o NoteBook FanControl.
2. Confirme que o arquivo existe:

```text
C:\Program Files (x86)\NoteBook FanControl\ec-probe.exe
```

3. Rode o app:

```powershell
python app_ventoinha.py
```

Ou gere o executavel:

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --uac-admin --name ForcaNitro app_ventoinha.py
```

4. Abra `dist\ForcaNitro.exe`.
5. Escolha `Auto`, `Max`, `Fixo` ou `Custom`.
6. No AN515-58 testado, escolha `Balanced` ou `Desempenho` no seletor de perfil Acer.
7. Monitore as temperaturas depois de aplicar qualquer perfil manual ou de desempenho.

O seletor de perfil Acer e separado do controle das ventoinhas. Ele usa o metodo WMI de firmware `AcerGamingFunction.SetGamingMiscSetting` e confirma o perfil escolhido por uma leitura posterior. A escrita esta habilitada somente quando o Windows informa um modelo `AN515-58`.

O executavel solicita acesso de administrador ao abrir porque as escritas EC e o acesso Acer WMI exigem elevacao. Abrir o ForcaNitro apenas le e exibe o estado atual das ventoinhas e do perfil Acer; nenhum modo e alterado automaticamente.

### Monitoramento

Versoes antigas usavam valores visuais/demo no grafico. As versoes atuais nao inventam temperatura ou uso.

- Uso da CPU e lido localmente pela API do Windows.
- Temperatura da CPU e lida localmente pelo perfil EC do AN515-58 quando disponivel.
- Temperatura e uso de GPU NVIDIA sao lidos localmente pelo `nvidia-smi`, quando disponivel.
- RPM das ventoinhas e lido localmente pelo perfil EC do AN515-58 quando disponivel.
- Leituras indisponiveis aparecem como `--`, sem valores simulados.

O ForcaNitro nao envia telemetria para nenhum lugar e nao coleta serial, SNID ou dados pessoais.

### Creditos

O ForcaNitro usa o `ec-probe.exe` do [NoteBook FanControl / NBFC](https://github.com/hirschmann/nbfc), projeto open-source criado por Stefan Hirschmann, como backend de baixo nivel para controlar as ventoinhas.

O NBFC e um projeto separado. O ForcaNitro nao inclui nem modifica o codigo-fonte do NBFC; ele espera que o NoteBook FanControl esteja instalado na maquina e chama o `ec-probe.exe` local para aplicar os valores de EC usados por este projeto.

Algumas releases do ForcaNitro podem incluir o instalador original e sem modificacoes do NBFC como arquivo de conveniencia. Antes de redistribuir qualquer binario do NBFC, confira o repositorio, o codigo-fonte e a licenca do projeto original.

As pesquisas sobre perfis e ventoinhas via Acer WMI tambem foram baseadas nos projetos open-source [Acer-Predator-Scripts](https://github.com/rafradek/Acer-Predator-Scripts) e [AeroForge NitroSense Alternative](https://github.com/noahcabral/aeroforge-nitrosense-alternative). Atualmente, o ForcaNitro usa WMI somente no seletor de perfil da plataforma AN515-58 testada; os controles existentes das ventoinhas continuam usando o perfil EC documentado acima.

### Tecla NitroSense

No notebook testado, a tecla NitroSense passa pelos servicos da Acer. O projeto inclui scripts para fazer essa tecla abrir/focar o ForcaNitro.

A tecla redirecionada abre o ForcaNitro por uma tarefa agendada com privilegio elevado e nao altera automaticamente o modo das ventoinhas ou o perfil Acer.

Instalar em PowerShell como administrador:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install_nitrosense_key_redirect.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install_nitrosense_task_redirect.ps1
```

Remover/restaurar:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\uninstall_nitrosense_key_redirect.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\restore_nitrosense_task.ps1
```

### Aviso

Este projeto escreve direto em registradores do embedded controller. Use apenas se voce souber o que esta fazendo e se o seu modelo for compativel. Ate agora, so foi testado no Acer Nitro 5 AN515-58-54UH / NH.QJCAL.004.

O perfil Acer `Desempenho` pode aumentar consumo de energia, temperaturas e atividade das ventoinhas. Volte para `Balanced` caso as temperaturas ou o comportamento do sistema fiquem anormais.

Observacoes da comunidade:

- `AN515-45`: um usuario relatou que funcionou ao executar como administrador, mas ainda nao foi totalmente validado.
- `AN517-54`: um usuario relatou que nao funcionou com o perfil EC atual do AN515-58. Esse modelo provavelmente precisa de registradores EC diferentes.

Suporte futuro para outros modelos deve ser feito por perfis explicitos e validados, sem tentar adivinhar enderecos EC. A verificacao de compatibilidade pode ler localmente o nome nao pessoal do modelo informado pelo Windows, mas o ForcaNitro nao envia identificadores da maquina.

### Diagnostico De Compatibilidade Somente Leitura

Alguns modelos Acer disponibilizam a interface WMI `AcerGamingFunction`, com metodos especificos para ventoinhas e perfis, enquanto outros podem exigir enderecos EC especificos por modelo. O jeito mais seguro de ampliar compatibilidade e coletar evidencias somente leitura primeiro.

O repositorio inclui um diagnostico opcional:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\diagnostics\collect_forcanitro_compatibility.ps1
```

O diagnostico nao altera ventoinhas, nao acessa a internet, nao coleta serial/SNID e nao envia nada. Ele chama somente metodos Acer WMI `Get*` e comandos selecionados `ec-probe.exe read`, entao gera um JSON local com modelo do notebook, versoes da BIOS/Windows, metodos Acer WMI disponiveis, respostas WMI somente leitura, bytes EC selecionados e leituras opcionais de GPU via `nvidia-smi`.

A pessoa pode revisar o JSON antes de decidir compartilha-lo.

Veja [`diagnostics/README.md`](diagnostics/README.md) para a descricao completa dos campos e da privacidade.
