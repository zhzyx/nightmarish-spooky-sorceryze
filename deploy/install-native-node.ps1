#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$Config
)
$ErrorActionPreference = 'Stop'
$pythonPath = (Get-Item -LiteralPath $Python).FullName
$configPath = (Get-Item -LiteralPath $Config).FullName
$entryPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../customizations/components/tianxuan/sinan-workorders/native_node.py')).Path
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$taskName = 'TianxuanNativeNode-' + $identity.User.Value
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument ('"{0}" --config "{1}"' -f $entryPath, $configPath) -WorkingDirectory (Split-Path $entryPath)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
if ($PSCmdlet.ShouldProcess($taskName, 'Register current-user native node and start it')) {
    $existing = Get-ScheduledTask -TaskPath '\' -ErrorAction Stop | Where-Object TaskName -eq $taskName
    if ($existing) {
        $matchesIdentity = $existing.Principal.UserId -in @($identity.Name, $identity.User.Value)
        $matchesAction = $existing.Actions.Count -eq 1 -and
            $existing.Actions[0].Execute -eq $action.Execute -and
            $existing.Actions[0].Arguments -ceq $action.Arguments -and
            $existing.Actions[0].WorkingDirectory -eq $action.WorkingDirectory
        $matchesSettings = $existing.Settings.Enabled -and $existing.Triggers[0].Enabled
        foreach ($field in @('MultipleInstances', 'ExecutionTimeLimit', 'RestartCount', 'RestartInterval',
                             'DisallowStartIfOnBatteries', 'StopIfGoingOnBatteries')) {
            if ($existing.Settings.$field -ne $settings.$field) { $matchesSettings = $false }
        }
        if (-not ($matchesSettings -and $matchesIdentity -and $matchesAction -and $existing.Principal.RunLevel -eq 'Limited' -and
                  $existing.Principal.LogonType -eq 'Interactive' -and $existing.Triggers.Count -eq 1 -and
                  $existing.Triggers[0].CimClass.CimClassName -eq 'MSFT_TaskLogonTrigger' -and
                  $existing.Triggers[0].UserId -in @($identity.Name, $identity.User.Value))) {
            throw "A different scheduled task already owns $taskName"
        }
    } else {
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -ErrorAction Stop | Out-Null
    }
    if (-not $existing -or $existing.State -notin @('Running', 'Queued')) {
        Start-ScheduledTask -TaskName $taskName
    }
    Get-ScheduledTaskInfo -TaskName $taskName
}
