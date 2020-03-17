param($process_id)

$events = @();
$lognames = 'Microsoft-Windows-Powershell/Operational', 'Security', 'Windows PowerShell';
foreach ($logname in $lognames) {
    $events += $(Get-WinEvent -FilterHashTable @{LogName = $logname; Data = $process_id} -ErrorAction SilentlyContinue | Select-Object -Property RecordId, ProviderName, UserId);
}