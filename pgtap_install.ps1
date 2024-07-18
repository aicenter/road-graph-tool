[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateScript({ Test-Path $_ }, ErrorMessage="The path does not exist: {0}")]
    [string]
    $pgtapPath
)

function elevate {
    $myWindowsID=[Security.Principal.WindowsIdentity]::GetCurrent()
    $myWindowsPrincipal=new-object Security.Principal.WindowsPrincipal($myWindowsID)
    if (!$myWindowsPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        # $newProcess = new-object System.Diagnostics.ProcessStartInfo "PowerShell";
        # $newProcess.Arguments = $myInvocation.MyCommand.Definition;
        # $newProcess.Verb = "runas";
        # [System.Diagnostics.Process]::Start($newProcess);
        # $argString = @() | ForEach-Object { "`"$_`"" } -join ' '
        # Start-Process pwsh -Verb RunAs -ArgumentList "-noexit -File `"$PSCommandPath`" `"$($MyInvocation.MyCommand.UnboundArguments)`""
        Write-Host "This script requires elevated privileges. Please run it as an administrator."
        exit
    }
}

elevate

Write-Debug "Searching for Postgres directory..."

foreach($record in Get-ChildItem HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall) {
    try {
        $item = Get-ItemProperty $record.PSPath
        if($item.DisplayName -like "PostgreSQL*") {
            $PostgreSQLDir = $item.InstallLocation
            break
        }
    } catch {
        # silence known casting error
        if ($_.Exception -match "Unable to cast object of type 'System.Int64' to type 'System.Int32'") {
            Write-Verbose "Encountered a casting error. Handling gracefully."
            continue
        # Rethrow other exceptions
        } else {
            throw
        }
    }
}

if (-not $PostgreSQLDir) {
    Write-Error "PostgreSQL directory not found. Please install PostgreSQL first."
    exit
}


Write-Debug "Postgres directory found: $PostgreSQLDir"

cd $pgtapPath



# get the version from the version parameter in the META.json file
$PgTapVersion = (Get-Content META.json | ConvertFrom-Json).version
Write-Host "PgTap version: $PgTapVersion"


Write-Debug "Preparing pgtap.sql"

$sqlFilePath = "sql/pgtap--$PgTapVersion.sql"

# Copy pgtap.sql
Copy-Item "sql\pgtap.sql.in" $sqlFilePath

# Replace placeholders in pgtap.sql
(Get-Content $sqlFilePath) | 
   ForEach-Object {$_ -replace "TAPSCHEMA", "tap"} |
   ForEach-Object {$_ -replace "__OS__", "win64"} |
   ForEach-Object {$_ -replace "__VERSION__", "0.24"} |
   ForEach-Object {$_ -replace "^-- ## ", ""} |
   Set-Content $sqlFilePath

Write-Host "Installing pgtap into $PostgreSQLDir" 

# Copy files to PostgreSQL directories
Copy-Item $sqlFilePath "$PostgreSQLDir\share\extension"
Copy-Item "contrib\pgtap.spec" "$PostgreSQLDir\contrib"
Copy-Item "pgtap.control" "$PostgreSQLDir\share\extension"