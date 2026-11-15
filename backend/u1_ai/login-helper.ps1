param()
$ErrorActionPreference='Stop'
$base='__ORIGIN__'
$pair='__PAIR__'
function Send-U1($name,$body) {
 $r=Invoke-RestMethod -Method Post -Uri ($base+'/u1-ai/api/helper/'+$name) -ContentType 'application/json' -Body ($body|ConvertTo-Json -Compress) -TimeoutSec 90
 if (!$r.ok) { throw $r.error };return $r.value
}
$listener=New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback,0)
try {
 $listener.Start();$port=($listener.LocalEndpoint).Port
 $login=Send-U1 'start' @{pair=$pair;port=$port}
 Write-Host 'Sign in only on the OpenAI page. Keep this window open.'
 Start-Process $login.url
 $deadline=[DateTime]::UtcNow.AddMinutes(9)
 while ([DateTime]::UtcNow -lt $deadline) {
  if (!$listener.Pending()) { Start-Sleep -Milliseconds 200;continue }
  $client=$listener.AcceptTcpClient();$stream=$client.GetStream();$stream.ReadTimeout=5000
  try {
   $reader=New-Object System.IO.StreamReader($stream)
   $line=$reader.ReadLine();$bytes=0
   while ($header=$reader.ReadLine()) { $bytes+=$header.Length;if($bytes -gt 20000){throw 'Request too large'} }
   if ($line -notmatch '^GET (/auth/callback\?[^ ]{1,16000}) HTTP/1\.[01]$') { $client.Close();continue }
   $callback='http://127.0.0.1:'+ $port + $Matches[1]
   $done=Send-U1 'finish' @{pair=$pair;callback=$callback}
   $body=[Text.Encoding]::UTF8.GetBytes('<html><body><h2>U1 Companion connected</h2>Return to U1 Companion and select your model.</body></html>')
   $head=[Text.Encoding]::ASCII.GetBytes("HTTP/1.1 200 OK`r`nContent-Type: text/html; charset=utf-8`r`nCache-Control: no-store`r`nContent-Length: $($body.Length)`r`nConnection: close`r`n`r`n")
   $stream.Write($head,0,$head.Length);$stream.Write($body,0,$body.Length)
   Write-Host 'Connected. Return to U1 Companion settings.';break
  } finally {$client.Close()}
 }
} catch { Write-Host ('Connection not confirmed: '+$_.Exception.Message) -ForegroundColor Red }
finally { $listener.Stop();$pair='';Read-Host 'Press Enter to close' }
