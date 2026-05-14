
$base = "c:\Users\parkj\IdeaProjects\schoolclub1"
$pharmacies = [System.Collections.Generic.List[object]]::new()

function Parse-CSVLine([string]$line) {
    $fields = [System.Collections.Generic.List[string]]::new()
    $current = [System.Text.StringBuilder]::new()
    $inQ = $false
    foreach ($ch in $line.ToCharArray()) {
        if ($ch -eq '"') { $inQ = !$inQ }
        elseif ($ch -eq ',' -and !$inQ) { $fields.Add($current.ToString().Trim()); [void]$current.Clear() }
        else { [void]$current.Append($ch) }
    }
    $fields.Add($current.ToString().Trim())
    return $fields.ToArray()
}

function EscapeJS([string]$s) {
    return $s -replace '\\','\\' -replace '"','\"' -replace "`r","" -replace "`n",""
}

# --- 서구: col[1]=name, col[2]=address, col[3]=phone ---
$lines = [System.IO.File]::ReadAllLines("$base\seoku.csv", [System.Text.Encoding]::UTF8)
for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "") { continue }
    $r = Parse-CSVLine $lines[$i]
    if ($r.Count -ge 3 -and $r[2].Length -gt 5) {
        $pharmacies.Add([PSCustomObject]@{ d="서구"; n=$r[1]; a=$r[2]; p=if($r.Count -gt 3){$r[3]}else{""} })
    }
}

# --- 동구: col[1]=name, col[3]=address, col[2]=phone ---
$lines = [System.IO.File]::ReadAllLines("$base\dongku.csv", [System.Text.Encoding]::UTF8)
for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "") { continue }
    $r = Parse-CSVLine $lines[$i]
    if ($r.Count -ge 4 -and $r[3].Length -gt 5) {
        $pharmacies.Add([PSCustomObject]@{ d="동구"; n=$r[1]; a=$r[3]; p=$r[2] })
    }
}

# --- 대덕구: col[0]=name, col[1]=address, col[2]=phone ---
$lines = [System.IO.File]::ReadAllLines("$base\daedukku.csv", [System.Text.Encoding]::UTF8)
for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "") { continue }
    $r = Parse-CSVLine $lines[$i]
    if ($r.Count -ge 2 -and $r[1].Length -gt 5) {
        $pharmacies.Add([PSCustomObject]@{ d="대덕구"; n=$r[0]; a=$r[1]; p=if($r.Count -gt 2){$r[2]}else{""} })
    }
}

# --- 유성구: col[2]=name, col[3]=address, col[4]=phone ---
$lines = [System.IO.File]::ReadAllLines("$base\yuseongku.csv", [System.Text.Encoding]::UTF8)
for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "") { continue }
    $r = Parse-CSVLine $lines[$i]
    if ($r.Count -ge 5 -and $r[3].Length -gt 5) {
        $pharmacies.Add([PSCustomObject]@{ d="유성구"; n=$r[2]; a=$r[3]; p=$r[4] })
    }
}

# --- 중구: col[1]=name, col[4]=address, col[2]=phone ---
$lines = [System.IO.File]::ReadAllLines("$base\jungku.csv", [System.Text.Encoding]::UTF8)
for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "") { continue }
    $r = Parse-CSVLine $lines[$i]
    if ($r.Count -ge 5 -and $r[4].Length -gt 5) {
        $pharmacies.Add([PSCustomObject]@{ d="중구"; n=$r[1]; a=$r[4]; p=$r[2] })
    }
}

Write-Host "Total: $($pharmacies.Count)"

$entries = $pharmacies | ForEach-Object {
    $d = EscapeJS $_.d; $n = EscapeJS $_.n; $a = EscapeJS $_.a; $p = EscapeJS $_.p
    "{d:`"$d`",n:`"$n`",a:`"$a`",p:`"$p`"}"
}

$js = "const PHARMACY_DATA = [" + ($entries -join ",") + "];"
[System.IO.File]::WriteAllText("$base\pharmacies_data.js", $js, [System.Text.Encoding]::UTF8)
Write-Host "Done: pharmacies_data.js ($($pharmacies.Count) entries)"
