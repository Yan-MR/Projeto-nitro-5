# ForcaNitro Compatibility Diagnostic

This folder contains a read-only diagnostic for investigating safe ForcaNitro compatibility on Acer Nitro, Nitro V, Predator, and related Acer notebooks.

The diagnostic is separate from the main application. It does not control the fans.

## Main Script

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\diagnostics\collect_forcanitro_compatibility.ps1
```

It creates:

```text
diagnostics\ForcaNitro-Compatibility-Diagnostic.json
```

The older `collect_acer_wmi_readonly.ps1` script is kept as a compatibility wrapper and now calls the main diagnostic above.

## Safety And Privacy

The script:

- Calls only Acer WMI methods whose names start with `Get`.
- Lists available `Set*` method names only so maintainers can understand the firmware surface, but never invokes them.
- Runs selected `ec-probe.exe read` commands only.
- Never runs `ec-probe.exe write`.
- Never runs `ec-probe.exe dump`.
- Does not change fan speed, platform profile, power mode, keyboard lighting, or fan tables.
- Does not access the internet or upload the report.
- Does not read serial numbers, SNID, usernames, personal files, tokens, browser data, or private paths.
- Writes a local JSON report that the user can review before sharing.

## What It Collects

System compatibility fields:

- Notebook manufacturer and model reported by Windows.
- BIOS version and BIOS manufacturer.
- Windows caption/version.
- Baseboard manufacturer/product/version, without serial number.

Acer WMI fields:

- Whether `root\wmi:AcerGamingFunction` exists.
- Available Acer WMI methods and their parameter shapes.
- Names of `Set*` methods present, clearly marked as not invoked.
- Selected read-only results from:
  - `GetGamingFanSpeed`
  - `GetGamingFanBehavior`
  - `GetGamingFanTable`
  - `GetGamingMiscSetting`
  - `GetGamingSysInfo`

Embedded-controller fields:

- Whether `ec-probe.exe` was found.
- Selected read-only EC bytes for known ForcaNitro AN515-58 fan registers.
- Selected read-only EC bytes in the `0xA0` through `0xAF` candidate temperature range.

NVIDIA fields, when available:

- GPU name.
- NVIDIA driver version.
- GPU temperature.
- GPU utilization.

## Why Administrator Is Required

On many Acer notebooks, Windows blocks access to `root\wmi:AcerGamingFunction` and embedded-controller reads unless PowerShell is elevated.

Administrator access is needed for local hardware read access, not for changing settings. The script still does not call any write/control command.

## How To Share A Report

1. Run the script as Administrator.
2. Open `diagnostics\ForcaNitro-Compatibility-Diagnostic.json`.
3. Confirm that you are comfortable sharing the fields.
4. Attach or paste the report in a GitHub issue or Reddit reply.

Recommended context to include with the report:

- Exact notebook model, for example `AN515-55-73GS`.
- BIOS version.
- What worked in ForcaNitro.
- What did not work, for example CPU temperature, GPU RPM, fan control, Acer profile switching.

## Current Research Status

ForcaNitro is fully validated only on the Acer Nitro 5 AN515-58-54UH / NH.QJCAL.004 family.

Community reports currently suggest:

- `AN515-55`: fan control may work, but CPU temperature likely uses a different EC register than AN515-58.
- `ANV15-41`: community member available for testing; needs read-only diagnostic first.
- `ANV15-51`: Acer WMI path looks promising; needs read-only diagnostic first.
- `AN517-54`: current AN515-58 EC profile did not work; likely needs a different model profile.

Future support should be added through explicit model profiles after read-only evidence, not by guessing EC addresses.

---

# PT-BR

Esta pasta contem um diagnostico somente leitura para investigar compatibilidade segura do ForcaNitro em notebooks Acer Nitro, Nitro V, Predator e modelos Acer relacionados.

O diagnostico e separado do aplicativo principal. Ele nao controla as ventoinhas.

## Script Principal

Execute:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\diagnostics\collect_forcanitro_compatibility.ps1
```

Ele cria:

```text
diagnostics\ForcaNitro-Compatibility-Diagnostic.json
```

O script antigo `collect_acer_wmi_readonly.ps1` foi mantido como atalho de compatibilidade e agora chama o diagnostico principal.

## Seguranca E Privacidade

O script:

- Chama somente metodos Acer WMI que comecam com `Get`.
- Lista nomes de metodos `Set*` apenas para entendermos o que existe no firmware, mas nunca chama esses metodos.
- Executa somente comandos selecionados `ec-probe.exe read`.
- Nunca executa `ec-probe.exe write`.
- Nunca executa `ec-probe.exe dump`.
- Nao altera velocidade das ventoinhas, perfil de desempenho, modo de energia, iluminacao do teclado ou tabelas de ventoinha.
- Nao acessa a internet e nao envia o relatorio.
- Nao coleta serial, SNID, nome de usuario, arquivos pessoais, tokens, dados do navegador ou caminhos privados.
- Gera um JSON local que a pessoa pode revisar antes de compartilhar.

## O Que Ele Coleta

Campos de compatibilidade do sistema:

- Fabricante e modelo do notebook informados pelo Windows.
- Versao da BIOS e fabricante da BIOS.
- Versao do Windows.
- Fabricante/produto/versao da placa base, sem numero de serie.

Campos Acer WMI:

- Se `root\wmi:AcerGamingFunction` existe.
- Metodos Acer WMI disponiveis e formato dos parametros.
- Nomes de metodos `Set*` presentes, marcados claramente como nao chamados.
- Resultados somente leitura selecionados de:
  - `GetGamingFanSpeed`
  - `GetGamingFanBehavior`
  - `GetGamingFanTable`
  - `GetGamingMiscSetting`
  - `GetGamingSysInfo`

Campos do embedded controller:

- Se `ec-probe.exe` foi encontrado.
- Bytes EC somente leitura dos registradores conhecidos do ForcaNitro no AN515-58.
- Bytes EC somente leitura no intervalo candidato de temperatura `0xA0` ate `0xAF`.

Campos NVIDIA, quando disponivel:

- Nome da GPU.
- Versao do driver NVIDIA.
- Temperatura da GPU.
- Uso da GPU.

## Por Que Precisa De Administrador

Em muitos notebooks Acer, o Windows bloqueia acesso a `root\wmi:AcerGamingFunction` e leituras do embedded controller quando o PowerShell nao esta elevado.

O acesso de administrador e necessario para leitura local de hardware, nao para alterar configuracoes. O script continua sem chamar nenhum comando de escrita/controle.

## Como Compartilhar Um Relatorio

1. Rode o script como Administrador.
2. Abra `diagnostics\ForcaNitro-Compatibility-Diagnostic.json`.
3. Confira se voce se sente confortavel em compartilhar os campos.
4. Anexe ou cole o relatorio em uma issue do GitHub ou resposta no Reddit.

Contexto recomendado junto com o relatorio:

- Modelo exato do notebook, por exemplo `AN515-55-73GS`.
- Versao da BIOS.
- O que funcionou no ForcaNitro.
- O que nao funcionou, por exemplo temperatura da CPU, RPM da GPU, controle de ventoinha, troca de perfil Acer.

## Estado Atual Da Pesquisa

O ForcaNitro esta totalmente validado apenas na familia Acer Nitro 5 AN515-58-54UH / NH.QJCAL.004.

Relatos da comunidade sugerem:

- `AN515-55`: o controle de ventoinha pode funcionar, mas a temperatura da CPU provavelmente usa outro registrador EC.
- `ANV15-41`: membro da comunidade disponivel para teste; precisa primeiro do diagnostico somente leitura.
- `ANV15-51`: caminho via Acer WMI parece promissor; precisa primeiro do diagnostico somente leitura.
- `AN517-54`: o perfil EC atual do AN515-58 nao funcionou; provavelmente precisa de perfil especifico.

Suporte futuro deve ser adicionado por perfis explicitos por modelo depois de evidencias somente leitura, sem tentar adivinhar enderecos EC.
