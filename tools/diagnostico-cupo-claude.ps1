<#
  diagnostico-cupo-claude.ps1  —  SOLO LECTURA. No mata, no borra, no modifica nada.

  Qué hace:
    1. Procesos claude/node/n8n/python/codex: inicio, CPU (total y % en 3 s), RAM, línea de comando.
    2. Logs .jsonl de Claude Code (~\.claude\projects, incluidos subagentes) y de Claude Desktop
       modificados desde -Since: por sesión → proyecto, inicio/fin, modelo, nº mensajes,
       tokens (input, output, cache_read, cache_creation), Task/Agent lanzados, nº de subagentes.
    3. TOP 5 por peso de tokens, tabla por horas, las 2 ventanas de 60 min con más consumo,
       y avisos de sesiones que se relanzan solas / bucle / automatizadas (claude -p, SDK).
    4. Tareas programadas de Windows, arranque automático, hooks/settings (usuario, proyectos, plugins),
       variables ANTHROPIC_*, y n8n local (API o base de datos SQLite) con workflows que usen Claude.

  Uso (PowerShell normal, no hace falta admin):
    powershell -ExecutionPolicy Bypass -File .\diagnostico-cupo-claude.ps1
    powershell -ExecutionPolicy Bypass -File .\diagnostico-cupo-claude.ps1 -Since '2026-11-08 18:00'

  Genera un informe en el Escritorio: diagnostico_cupo_claude.txt (sin claves: se enmascaran).
#>
param(
  [datetime]$Since = '2026-11-08 18:00',
  [string]$OutFile = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'diagnostico_cupo_claude.txt')
)
$ErrorActionPreference = 'SilentlyContinue'
$sinceUtc = $Since.ToUniversalTime()
$out = New-Object System.Collections.Generic.List[string]
function W([string]$s = '') { $out.Add($s); Write-Host $s }
function H([string]$s) { W ''; W ('=' * 90); W $s; W ('=' * 90) }
function T($obj) { if ($obj) { ($obj | Format-Table -AutoSize -Wrap | Out-String -Width 260).TrimEnd() -split "`r?`n" | ForEach-Object { W $_ } } else { W '  (nada)' } }
function Mask([string]$s) { if (-not $s) { return '' }; $s = $s -replace 'sk-ant-[A-Za-z0-9_\-]+', 'sk-ant-***'; $s -replace '(?i)(api[_-]?key|token|secret|password)(["'':= ]+)[^"''\s,}]+', '$1$2***' }
function Cut([string]$s, [int]$n) { if (-not $s) { return '' }; $s = $s -replace '\s+', ' '; if ($s.Length -gt $n) { $s.Substring(0, $n) + '…' } else { $s } }
function K([double]$n) { if ($n -ge 1e6) { '{0:N1}M' -f ($n / 1e6) } elseif ($n -ge 1e3) { '{0:N0}k' -f ($n / 1e3) } else { '{0:N0}' -f $n } }

W "Diagnóstico de cupo Claude — $(Get-Date -Format 'yyyy-MM-dd HH:mm')  (desde $($Since.ToString('yyyy-MM-dd HH:mm')) hora local)"
W "Equipo: $env:COMPUTERNAME"

# ───────────────────────────── 1. PROCESOS ─────────────────────────────
H '1. PROCESOS (claude / node / n8n / python / codex)'
$pat = '(?i)claude|node|n8n|python|codex|npx|bun|deno|uvx'
$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match $pat -or $_.CommandLine -match '(?i)claude|n8n|anthropic|codex' }
$cores = [Environment]::ProcessorCount
$t0 = @{}; foreach ($p in $procs) { $g = Get-Process -Id $p.ProcessId; if ($g) { $t0[$p.ProcessId] = $g.TotalProcessorTime.TotalSeconds } }
Start-Sleep -Seconds 3
$rows = foreach ($p in $procs) {
  $g = Get-Process -Id $p.ProcessId
  if (-not $g) { continue }
  $cpuNow = $g.TotalProcessorTime.TotalSeconds
  $pct = if ($t0.ContainsKey($p.ProcessId)) { [math]::Round(($cpuNow - $t0[$p.ProcessId]) / 3 / $cores * 100, 1) } else { 0 }
  [pscustomobject]@{
    PID = $p.ProcessId; PPID = $p.ParentProcessId; Nombre = $p.Name
    Inicio = if ($p.CreationDate) { $p.CreationDate.ToString('dd/MM HH:mm') } else { '' }
    'CPU_s' = [math]::Round($cpuNow, 0); 'CPU%' = $pct
    'RAM_MB' = [math]::Round($p.WorkingSetSize / 1MB, 0)
    Comando = Cut (Mask $p.CommandLine) 150
  }
}
T ($rows | Sort-Object Inicio)
W ''
W "Nº de procesos claude: $(@($rows | Where-Object { $_.Nombre -match '(?i)claude' -or $_.Comando -match '(?i)claude' }).Count)   (varias 'claude.exe' con PPID distinto = varias sesiones/agentes vivos)"

H '1b. VARIABLES DE ENTORNO RELEVANTES (solo si existen, valor oculto)'
foreach ($v in 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_OAUTH_TOKEN', 'ANTHROPIC_BASE_URL', 'ANTHROPIC_MODEL', 'CLAUDE_CODE_USE_BEDROCK', 'N8N_API_KEY') {
  foreach ($scope in 'Process', 'User', 'Machine') {
    $val = [Environment]::GetEnvironmentVariable($v, $scope)
    if ($val) { W ("  {0,-26} definida en {1}" -f $v, $scope) }
  }
}
W '  (ANTHROPIC_API_KEY hace que Claude Code facture por API, NO por el cupo Max. Un CLAUDE_CODE_OAUTH_TOKEN en scripts = automatismos usando tu cupo Max.)'

# ───────────────────────────── 2. LOGS .jsonl ─────────────────────────────
H "2. LOGS DE CLAUDE (.jsonl modificados desde $($Since.ToString('dd/MM HH:mm')))"
$projRoot = Join-Path $env:USERPROFILE '.claude\projects'
$roots = @($projRoot, (Join-Path $env:APPDATA 'Claude'), (Join-Path $env:LOCALAPPDATA 'Claude'), (Join-Path $env:LOCALAPPDATA 'AnthropicClaude'))
$files = foreach ($r in $roots) { if (Test-Path $r) { Get-ChildItem $r -Recurse -Filter *.jsonl -File -Force | Where-Object { $_.LastWriteTime -ge $Since } } }
$files = @($files | Sort-Object FullName -Unique)
W "Archivos: $($files.Count)  ($([math]::Round(($files | Measure-Object Length -Sum).Sum / 1MB, 1)) MB)"

$SESS = @{}        # sesión -> datos
$MSG = @{}      # message.id -> uso máximo (Claude Code escribe varias líneas por mensaje)
$TASKS = @{}    # tool_use id -> sesión
$tsRe = [regex]'"timestamp":"([^"]+)"'
$i = 0
foreach ($f in $files) {
  $i++; Write-Progress -Activity 'Leyendo .jsonl' -Status $f.Name -PercentComplete ($i * 100 / [math]::Max(1, $files.Count))
  $isSub = $f.FullName -match '\\subagents\\'
  $sidFile = if ($isSub) { Split-Path (Split-Path $f.DirectoryName -Parent) -Leaf } else { $f.BaseName }
  if ($f.FullName.StartsWith($projRoot, [StringComparison]::OrdinalIgnoreCase)) { $proj = $f.FullName.Substring($projRoot.Length + 1).Split('\')[0] }
  else { $proj = 'DESKTOP:' + (Split-Path $f.DirectoryName -Leaf) }
  try { $fs = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite'); $sr = New-Object IO.StreamReader($fs, [Text.Encoding]::UTF8) } catch { continue }
  while ($null -ne ($line = $sr.ReadLine())) {
    if ($line.Length -lt 30) { continue }
    $mm = $tsRe.Matches($line); if ($mm.Count -eq 0) { continue }
    try { $ts = [datetime]::Parse($mm[$mm.Count - 1].Groups[1].Value, $null, [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime() } catch { continue }
    if ($ts -lt $sinceUtc) { continue }
    $sid = $sidFile
    if (-not $isSub) { $ms = [regex]::Match($line, '"sessionId":"([^"]+)"'); if ($ms.Success) { $sid = $ms.Groups[1].Value } }
    if (-not $SESS.ContainsKey($sid)) {
      $SESS[$sid] = @{ Sid = $sid; Proyecto = $proj; Cwd = ''; Ini = $ts; Fin = $ts; Modelos = @{}; Prompts = 0; Llamadas = 0
        In = 0.0; Out = 0.0; CR = 0.0; CC = 0.0; Tasks = 0; SubFiles = @{}; Entry = ''; Primer = ''; Compact = 0; Sidechain = 0 }
    }
    $s = $SESS[$sid]
    if ($ts -lt $s.Ini) { $s.Ini = $ts }; if ($ts -gt $s.Fin) { $s.Fin = $ts }
    if ($isSub) { $s.SubFiles[$f.Name] = 1 }
    if (-not $s.Cwd) { $mc = [regex]::Match($line, '"cwd":"((?:[^"\\]|\\.)*)"'); if ($mc.Success) { $s.Cwd = $mc.Groups[1].Value -replace '\\\\', '\' } }
    if (-not $s.Entry) { $me = [regex]::Match($line, '"entrypoint":"([^"]+)"'); if ($me.Success) { $s.Entry = $me.Groups[1].Value } }
    if ($line.Contains('"isCompactSummary":true')) { $s.Compact++ }
    if ($line.Contains('"type":"assistant"')) {
      try { $o = $line | ConvertFrom-Json } catch { continue }
      $m = $o.message; if (-not $m -or $m.model -eq '<synthetic>') { continue }
      $id = if ($m.id) { $m.id } else { $o.uuid }
      $u = $m.usage
      if (-not $MSG.ContainsKey($id)) { $MSG[$id] = @{ Sid = $sid; Ts = $ts; Model = $m.model; In = 0.0; Out = 0.0; CR = 0.0; CC = 0.0 } }
      $r = $MSG[$id]
      if ($u) {
        $r.In = [math]::Max($r.In, [double]$u.input_tokens); $r.Out = [math]::Max($r.Out, [double]$u.output_tokens)
        $r.CR = [math]::Max($r.CR, [double]$u.cache_read_input_tokens); $r.CC = [math]::Max($r.CC, [double]$u.cache_creation_input_tokens)
      }
      foreach ($c in @($m.content)) { if ($c.type -eq 'tool_use' -and ($c.name -eq 'Task' -or $c.name -eq 'Agent')) { $TASKS[$c.id] = $sid } }
    }
    elseif ($line.Contains('"type":"user"') -and -not $line.Contains('"tool_result"') -and -not $line.Contains('"isMeta":true')) {
      if ($isSub) { $s.Sidechain++ } else {
        $s.Prompts++
        if (-not $s.Primer) { $mp = [regex]::Match($line, '"content":"((?:[^"\\]|\\.){0,200})'); if (-not $mp.Success) { $mp = [regex]::Match($line, '"text":"((?:[^"\\]|\\.){0,200})') }; if ($mp.Success) { $s.Primer = Cut ($mp.Groups[1].Value -replace '\\n', ' ') 70 } }
      }
    }
  }
  $sr.Close(); $fs.Close()
}
Write-Progress -Activity 'Leyendo .jsonl' -Completed

# peso ≈ coste relativo (input 1, cache_write 1.25, cache_read 0.1, output 5)
function Peso($r) { $r.In + 1.25 * $r.CC + 0.1 * $r.CR + 5 * $r.Out }
$bins = @{}  # bin de 5 min (local) -> @{peso; porSesion}
foreach ($r in $MSG.Values) {
  $s = $SESS[$r.Sid]; $s.Llamadas++; $s.In += $r.In; $s.Out += $r.Out; $s.CR += $r.CR; $s.CC += $r.CC; $s.Modelos[$r.Model] = 1
  $loc = $r.Ts.ToLocalTime(); $b = $loc.Date.AddMinutes([math]::Floor(($loc.Hour * 60 + $loc.Minute) / 5) * 5)
  if (-not $bins.ContainsKey($b)) { $bins[$b] = @{ P = 0.0; N = 0; Ses = @{} } }
  $p = Peso $r; $bins[$b].P += $p; $bins[$b].N++; $bins[$b].Ses[$r.Sid] = [double]$bins[$b].Ses[$r.Sid] + $p
}
foreach ($t in $TASKS.Values) { if ($SESS.ContainsKey($t)) { $SESS[$t].Tasks++ } }

$ses = foreach ($s in $SESS.Values) {
  $dur = ($s.Fin - $s.Ini).TotalMinutes
  [pscustomobject]@{
    Sesion = $s.Sid.Substring(0, [math]::Min(8, $s.Sid.Length)); SidFull = $s.Sid
    Proyecto = Cut ($(if ($s.Cwd) { $s.Cwd } else { $s.Proyecto })) 45
    Inicio = $s.Ini.ToLocalTime().ToString('dd/MM HH:mm'); Fin = $s.Fin.ToLocalTime().ToString('dd/MM HH:mm'); Min = [math]::Round($dur, 0)
    Modelo = ($s.Modelos.Keys -join ',') -replace 'claude-', ''
    Prompts = $s.Prompts; Llamadas = $s.Llamadas
    Input = K $s.In; Output = K $s.Out; CacheRead = K $s.CR; CacheCreate = K $s.CC
    TotalTok = $s.In + $s.Out + $s.CR + $s.CC; Peso = [math]::Round($s.In + 1.25 * $s.CC + 0.1 * $s.CR + 5 * $s.Out, 0)
    Tasks = $s.Tasks; Subagentes = $s.SubFiles.Count; Compact = $s.Compact; Entry = $s.Entry; PrimerPrompt = $s.Primer
    _ini = $s.Ini; _cwd = $s.Cwd
  }
}
$ses = @($ses | Sort-Object Peso -Descending)
$tot = ($ses | Measure-Object Peso -Sum).Sum
W "Sesiones con actividad: $($ses.Count)   Llamadas API: $($MSG.Count)   Task/Agent lanzados: $($TASKS.Count)"
W ''
W 'TODAS LAS SESIONES (ordenadas por peso; peso ≈ input + 1,25·cache_create + 0,1·cache_read + 5·output):'
T ($ses | Select-Object Sesion, Proyecto, Inicio, Fin, Min, Modelo, Prompts, Llamadas, Input, Output, CacheRead, CacheCreate, Tasks, Subagentes, Entry)

# ───────────────────────────── 3. TOP 5, HORAS, VENTANAS, ALERTAS ─────────────────────────────
H '3. TOP 5 SESIONES POR CONSUMO'
$rank = 0
T ($ses | Select-Object -First 5 | ForEach-Object { $rank++; [pscustomobject]@{ '#' = $rank; Sesion = $_.SidFull; Proyecto = $_.Proyecto; Inicio = $_.Inicio; Fin = $_.Fin; Modelo = $_.Modelo; TotalTok = K $_.TotalTok; '%Peso' = if ($tot) { [math]::Round($_.Peso * 100 / $tot, 1) } else { 0 }; Tasks = $_.Tasks; PrimerPrompt = $_.PrimerPrompt } })

W ''; W 'CONSUMO POR HORA (local):'
$hours = $bins.GetEnumerator() | Group-Object { $_.Key.ToString('dd/MM HH:00') } | ForEach-Object {
  $p = ($_.Group | ForEach-Object { $_.Value.P } | Measure-Object -Sum).Sum
  $n = ($_.Group | ForEach-Object { $_.Value.N } | Measure-Object -Sum).Sum
  $agg = @{}; foreach ($g in $_.Group) { foreach ($k in $g.Value.Ses.Keys) { $agg[$k] = [double]$agg[$k] + $g.Value.Ses[$k] } }
  $top = $agg.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 1
  [pscustomobject]@{ Hora = $_.Name; Llamadas = $n; Peso = K $p; Barra = ('#' * [math]::Min(60, [math]::Ceiling($p / [math]::Max(1, $tot) * 200))); SesionTop = "$($(Cut $top.Key 9)) ($([math]::Round($top.Value*100/[math]::Max(1,$p),0))%) $(Cut $SESS[$top.Key].Cwd 30)" }
}
T ($hours | Sort-Object Hora)

W ''; W 'LAS 2 VENTANAS DE 60 MIN CON MÁS CONSUMO (deberían coincidir con los 2 cortes de cupo):'
$keys = @($bins.Keys | Sort-Object)
$cands = foreach ($k in $keys) { $e = $k.AddMinutes(60); $sum = 0.0; foreach ($k2 in $keys) { if ($k2 -ge $k -and $k2 -lt $e) { $sum += $bins[$k2].P } }; [pscustomobject]@{ Ini = $k; P = $sum } }
$win = @(); foreach ($c in ($cands | Sort-Object P -Descending)) { if ($win.Count -ge 2) { break }; if (-not ($win | Where-Object { [math]::Abs(($_.Ini - $c.Ini).TotalMinutes) -lt 60 })) { $win += $c } }
$winSes = @{}
foreach ($w in $win) {
  $agg = @{}; foreach ($k2 in $keys) { if ($k2 -ge $w.Ini -and $k2 -lt $w.Ini.AddMinutes(60)) { foreach ($sk in $bins[$k2].Ses.Keys) { $agg[$sk] = [double]$agg[$sk] + $bins[$k2].Ses[$sk] } } }
  W ("  Ventana {0:dd/MM HH:mm}–{1:HH:mm}  peso {2}  ({3}% del total del periodo)" -f $w.Ini, $w.Ini.AddMinutes(60), (K $w.P), [math]::Round($w.P * 100 / [math]::Max(1, $tot), 0))
  foreach ($e in ($agg.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 4)) {
    $pc = [math]::Round($e.Value * 100 / [math]::Max(1, $w.P), 0); if ($pc -ge 20) { $winSes[$e.Key] = [int]$winSes[$e.Key] + 1 }
    W ("      {0}%  sesión {1}  {2}  [{3}]" -f $pc, $e.Key, (Cut $SESS[$e.Key].Cwd 40), $SESS[$e.Key].Primer)
  }
}

W ''; W 'ALERTAS:'
$alert = 0
foreach ($k in $winSes.Keys) { if ($winSes[$k] -ge 2) { $alert++; W "  [!] Sesión $k aporta ≥20% en LAS DOS ventanas pico → principal sospechosa." } }
foreach ($g in ($ses | Where-Object { $_.PrimerPrompt } | Group-Object { "$($_._cwd)|$($_.PrimerPrompt)" } | Where-Object { $_.Count -ge 3 })) {
  $alert++; $x = $g.Group | Sort-Object _ini
  W "  [!] SE RELANZA SOLA: $($g.Count) sesiones con el mismo primer prompt en $(Cut $x[0]._cwd 40): '$($x[0].PrimerPrompt)'  ($($x[0].Inicio) … $($x[-1].Inicio))"
}
foreach ($x in $ses) {
  $why = @()
  if ($x.Entry -and $x.Entry -notmatch '^(cli|claude-vscode|claude-desktop)$') { $why += "entrypoint=$($x.Entry) (claude -p / SDK = automatizado)" }
  if ($x.Prompts -le 2 -and $x.Llamadas -ge 80) { $why += "$($x.Llamadas) llamadas con solo $($x.Prompts) prompt(s) humanos (agente autónomo)" }
  if ($x.Min -gt 0 -and $x.Llamadas / [math]::Max(1, $x.Min / 60) -ge 150 -and $x.Llamadas -ge 100) { $why += "ritmo $([math]::Round($x.Llamadas / ($x.Min/60),0)) llamadas/h" }
  if ($x.Tasks -ge 10) { $why += "$($x.Tasks) Task/Agent lanzados" }
  if ($x.Compact -ge 3) { $why += "$($x.Compact) compactaciones (contexto lleno repetidamente)" }
  if ($why) { $alert++; W "  [!] $($x.SidFull) ($(Cut $x.Proyecto 35), $($x.Inicio)): $($why -join '; ')" }
}
if ($alert -eq 0) { W '  Ninguna alerta automática. Mira el TOP 5 y la tabla por horas.' }

# ───────────────────────────── 4. AUTOMATISMOS ─────────────────────────────
H '4a. TAREAS PROGRAMADAS DE WINDOWS que lanzan claude/node/n8n/python/codex'
$st = foreach ($t in Get-ScheduledTask) {
  foreach ($a in $t.Actions) {
    $cmd = "$($a.Execute) $($a.Arguments)"
    if ($cmd -match '(?i)claude|node|n8n|npx|python|pythonw|codex|anthropic|\.ps1|\.bat|\.cmd') {
      if ($cmd -match '(?i)\\Microsoft\\|OneDrive|Edge|Google\\Update' -and $cmd -notmatch '(?i)claude|n8n|node|codex') { continue }
      $inf = Get-ScheduledTaskInfo -TaskName $t.TaskName -TaskPath $t.TaskPath
      [pscustomobject]@{ Tarea = "$($t.TaskPath)$($t.TaskName)"; Estado = $t.State; Ultima = $inf.LastRunTime; Proxima = $inf.NextRunTime; Resultado = $inf.LastTaskResult
        Disparador = (($t.Triggers | ForEach-Object { ($_.CimClass.CimClassName -replace 'MSFT_Task|Trigger', '') + $(if ($_.Repetition.Interval) { " cada $($_.Repetition.Interval)" }) }) -join ', '); Accion = Cut (Mask $cmd) 110 }
    }
  }
}
T ($st | Sort-Object Ultima -Descending)

H '4b. ARRANQUE AUTOMÁTICO (Run / Startup) con claude/node/n8n/python'
$run = @(foreach ($k in 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run', 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run') {
  $p = Get-ItemProperty $k; if ($p) { $p.PSObject.Properties | Where-Object { $_.Name -notmatch '^PS' -and "$($_.Value)" -match '(?i)claude|node|n8n|python|codex|pm2' } | ForEach-Object { [pscustomobject]@{ Origen = $k; Nombre = $_.Name; Valor = Cut (Mask $_.Value) 120 } } }
})
$run += foreach ($d in [Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('CommonStartup')) { Get-ChildItem $d -File | Where-Object { $_.Name -match '(?i)claude|node|n8n|python|codex|pm2' } | ForEach-Object { [pscustomobject]@{ Origen = $d; Nombre = $_.Name; Valor = '' } } }
if (Get-Command pm2 -ErrorAction SilentlyContinue) { W '  pm2 instalado → procesos gestionados:'; (pm2 jlist 2>$null | ConvertFrom-Json) | ForEach-Object { $run += [pscustomobject]@{ Origen = 'pm2'; Nombre = $_.name; Valor = "$($_.pm2_env.status) restarts=$($_.pm2_env.restart_time) $($_.pm2_env.pm_exec_path)" } } }
T $run

H '4c. SETTINGS / HOOKS DE CLAUDE CODE'
$cfg = @((Join-Path $env:USERPROFILE '.claude\settings.json'), (Join-Path $env:USERPROFILE '.claude\settings.local.json'), 'C:\ProgramData\ClaudeCode\managed-settings.json')
$cwds = @($SESS.Values | ForEach-Object { $_.Cwd } | Where-Object { $_ } | Sort-Object -Unique)
foreach ($c in $cwds) { $cfg += (Join-Path $c '.claude\settings.json'); $cfg += (Join-Path $c '.claude\settings.local.json') }
foreach ($f in ($cfg | Sort-Object -Unique)) {
  if (-not (Test-Path $f)) { continue }
  W ''; W "  >> $f  (modificado $((Get-Item $f).LastWriteTime.ToString('dd/MM HH:mm')))"
  try { $j = Get-Content $f -Raw | ConvertFrom-Json } catch { W '     (JSON no válido)'; continue }
  foreach ($p in 'model', 'apiKeyHelper', 'cleanupPeriodDays') { if ($j.$p) { W "     $p = $(Mask $j.$p)" } }
  if ($j.permissions.defaultMode) { W "     permissions.defaultMode = $($j.permissions.defaultMode)" }
  if ($j.env) { W "     env: $(($j.env.PSObject.Properties.Name) -join ', ')" }
  if ($j.statusLine) { W "     statusLine: $(Cut (Mask ($j.statusLine | ConvertTo-Json -Compress -Depth 5)) 160)"; if ("$($j.statusLine.command)" -match '(?i)claude\s+(-p|--print)') { W '     [!] El statusLine llama a claude -p → gasta cupo en CADA refresco' } }
  if ($j.hooks) {
    foreach ($ev in $j.hooks.PSObject.Properties) {
      foreach ($grp in @($ev.Value)) { foreach ($h in @($grp.hooks)) {
        $txt = "$($h.type): $(if ($h.command) { $h.command } else { $h.prompt })"
        $flag = if ($h.type -in 'prompt', 'agent') { '  [!] hook de tipo prompt/agent = llama al modelo en cada evento' } elseif ($txt -match '(?i)claude\s+(-p|--print)|claude\.exe|anthropic') { '  [!] el hook lanza claude → posible bucle/recursión' } else { '' }
        W "     hook $($ev.Name) [$($grp.matcher)] $(Cut (Mask $txt) 140)$flag"
      } }
    }
  }
}
W ''; W '  Plugins con hooks (~\.claude\plugins):'
$ph = Get-ChildItem (Join-Path $env:USERPROFILE '.claude\plugins') -Recurse -Filter hooks.json -File
foreach ($f in $ph) { $raw = Get-Content $f.FullName -Raw; $fl = @(); if ($raw -match '"type"\s*:\s*"(prompt|agent)"') { $fl += 'hook prompt/agent' }; if ($raw -match '(?i)claude\s+(-p|--print)') { $fl += 'llama a claude -p' }
  W ("     {0}  {1}" -f ($f.FullName.Replace($env:USERPROFILE, '~')), $(if ($fl) { '[!] ' + ($fl -join ', ') } else { '' })) }
if (-not $ph) { W '     (ninguno)' }
$sched = Get-ChildItem (Join-Path $env:USERPROFILE '.claude') -Recurse -File -Include *.json -Force | Where-Object { $_.FullName -match '(?i)schedul|cron|loop' -and $_.FullName -notmatch '\\projects\\' }
if ($sched) { W ''; W '  Archivos de tareas/cron/loop de Claude:'; $sched | ForEach-Object { W "     $($_.FullName.Replace($env:USERPROFILE,'~'))  ($($_.LastWriteTime.ToString('dd/MM HH:mm')))" } }

H '4d. n8n LOCAL'
$n8nProc = $rows | Where-Object { $_.Comando -match '(?i)n8n' -or $_.Nombre -match '(?i)n8n' }
W "  Proceso n8n: $(if ($n8nProc) { 'SÍ (PID ' + (($n8nProc.PID) -join ',') + ')' } else { 'no detectado' })"
if (Get-Command docker -ErrorAction SilentlyContinue) { $dk = docker ps --format '{{.Names}} {{.Image}} {{.Status}}' 2>$null | Select-String -Pattern 'n8n'; if ($dk) { W "  Docker: $dk" } }
$up = $false; try { $null = Invoke-WebRequest 'http://localhost:5678/healthz' -UseBasicParsing -TimeoutSec 3; $up = $true } catch {}
W "  http://localhost:5678 responde: $up"
$key = if ($env:N8N_API_KEY) { $env:N8N_API_KEY } else { [Environment]::GetEnvironmentVariable('N8N_API_KEY', 'User') }
$found = $false
if ($up -and $key) {
  try {
    $wf = (Invoke-RestMethod 'http://localhost:5678/api/v1/workflows?active=true&limit=250' -Headers @{ 'X-N8N-API-KEY' = $key }).data
    foreach ($w in $wf) { $hit = $w.nodes | Where-Object { $_.type -match '(?i)anthropic|claude' -or (($_.parameters | ConvertTo-Json -Depth 8 -Compress) -match '(?i)claude|anthropic') }
      if ($hit) { $found = $true; W "  [!] Workflow ACTIVO '$($w.name)' (id $($w.id)) nodos: $(($hit | ForEach-Object { "$($_.name) [$($_.type)]" }) -join '; ')" } }
  } catch { W "  API n8n: error $($_.Exception.Message)" }
}
$db = Join-Path $env:USERPROFILE '.n8n\database.sqlite'
$py = (Get-Command python -ErrorAction SilentlyContinue).Source; if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $found -and (Test-Path $db) -and $py) {
  $tmp = Join-Path $env:TEMP 'n8n_diag_readonly.py'
  @'
import sqlite3, sys
con = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True)
q = "select id,name,active,updatedAt from workflow_entity where active=1 and (lower(nodes) like '%anthropic%' or lower(nodes) like '%claude%')"
for r in con.execute(q): print('  [!] Workflow ACTIVO con Claude/Anthropic:', r)
try:
    q2 = "select w.name, count(*), min(e.startedAt), max(e.startedAt) from execution_entity e join workflow_entity w on w.id=e.workflowId where e.startedAt >= ? group by w.name order by 2 desc limit 10"
    rows = list(con.execute(q2, (sys.argv[2],)))
    print('  Ejecuciones desde', sys.argv[2], ':')
    for r in rows: print('     ', r)
except Exception as ex: print('  (sin tabla de ejecuciones:', ex, ')')
'@ | Set-Content $tmp -Encoding UTF8
  & $py -I $tmp $db $sinceUtc.ToString('yyyy-MM-dd HH:mm:ss') | ForEach-Object { W $_ }
  Remove-Item $tmp
} elseif (-not $found -and (Test-Path $db)) {
  $hits = (Select-String -Path $db -Pattern 'lmChatAnthropic|anthropicApi|claude -p' -AllMatches).Count
  W "  database.sqlite existe; coincidencias 'anthropic/claude -p' (líneas, búsqueda bruta): $hits  (instala python para detalle)"
} elseif (-not $found) { W '  No hay n8n local accesible (ni API con N8N_API_KEY ni ~\.n8n\database.sqlite).' }
W '  Nota: un nodo Anthropic de n8n con API key factura en console.anthropic.com, NO gasta cupo Max. Solo gasta cupo Max si n8n ejecuta el CLI `claude` (nodo Execute Command) o usa un token OAuth de tu suscripción.'

$out | Set-Content -Path $OutFile -Encoding UTF8
Write-Host ''; Write-Host "Informe guardado en: $OutFile" -ForegroundColor Green
