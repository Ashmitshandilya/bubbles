$process = Get-Process -Id 6356 -ErrorAction SilentlyContinue
if ($process) {
    Write-Output "Process Name: $($process.ProcessName)"
    Write-Output "Process Path: $($process.Path)"
    Write-Output ""
    # Get environment variables for this process via WMI
    $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId=6356").CommandLine
    Write-Output "Command Line: $cmdLine"
} else {
    Write-Output "Process 6356 not found"
}
