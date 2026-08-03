$env:OLLAMA_MODELS = "D:\OllamaModels"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "C:\Users\李炳树\AppData\Local\Programs\Ollama\ollama.exe"
$psi.Arguments = "serve"
$psi.UseShellExecute = $true
$psi.CreateNoWindow = $true
[System.Diagnostics.Process]::Start($psi)
