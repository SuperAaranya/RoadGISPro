param(
  [string]$Languages = "rust_router,js_metrics,go_metrics,csharp_metrics,rust_validator,go_validator,plugins"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $scriptDir "setup_languages.py"
$cfg = Join-Path (Split-Path -Parent $scriptDir) "runtime_config.json"

python $py --languages $Languages --write-config $cfg
