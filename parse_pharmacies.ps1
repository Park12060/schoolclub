# PowerShell script to parse pharmacy CSVs and generate JSON
$base = "c:\Users\parkj\IdeaProjects\schoolclub1"
$results = [System.Collections.Generic.List[hashtable]]::new()

function CleanField($s) {
    return $s.Trim().Trim('"').Trim("'").Trim()
}

# Parse CSV with proper handling of quoted fields
function ParseCSVLine($line) {
    $fields = @()
    $current = ""
    $inQuote = $false
    foreach ($ch in $line.ToCharArray()) {
        if ($ch -eq '"') {
            $inQuote = !$inQuote
        } elseif ($ch -eq ',' -and !$inQuote) {
            $fields += $current
            $current = ""
        } else {
            $current += $ch
        }
    }
    $fields += $current
    return $fields
}

# ===== 서구: 번호, 약국명칭, 약국주소(도로명), 약국전화번호 =====
$lines = [System.IO.File]::ReadAllLines("$base\대전광역시 서구_약국현황_20250820.csv", [System.Text.Encoding]::GetEncoding("euc-kr"))
Write-Host "서구 header: $($lines[0])"
for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "") { continue }
    $row = ParseCSVLine $lines[$i]
    if ($row.Count -ge 3) {
        $results.Add(@{
            district = "서구"
            name = CleanField $row[1]
            address = CleanField $row[2]
            phone = if ($row.Count -gt 3) { CleanField $row[3] } else { "" }
        })
    }
}
Write-Host "서구: $(($results | Where-Object { $_['district'] -eq '서구' }).Count)"

# ===== 동구: 번호, 약국명칭, 약국전화번호, 약국주소(도로명) =====
$lines = [System.IO.File]::ReadAllLines("$base\대전광역시 동구 약국 현황_20250701.csv", [System.Text.Encoding]::GetEncoding("euc-kr"))
Write-Host "동구 header: $($lines[0])"
for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "") { continue }
    $row = ParseCSVLine $lines[$i]
    if ($row.Count -ge 4) {
        $results.Add(@{
            district = "동구"
            name = CleanField $row[1]
            address = CleanField $row[3]
            phone = CleanField $row[2]
        })
    }
}
Write-Host "동구: $(($results | Where-Object { $_['district'] -eq '동구' }).Count)"

# ===== 대덕구: 약국명칭, 약국주소(도로명), 전화번호, 기준일 =====
$lines = [System.IO.File]::ReadAllLines("$base\대전광역시 대덕구_약국정보_20250101.csv", [System.Text.Encoding]::GetEncoding("euc-kr"))
Write-Host "대덕구 header: $($lines[0])"
for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "") { continue }
    $row = ParseCSVLine $lines[$i]
    if ($row.Count -ge 2) {
        $results.Add(@{
            district = "대덕구"
            name = CleanField $row[0]
            address = CleanField $row[1]
            phone = if ($row.Count -gt 2) { CleanField $row[2] } else { "" }
        })
    }
}
Write-Host "대덕구: $(($results | Where-Object { $_['district'] -eq '대덕구' }).Count)"

# ===== 유성구: 구분코드, 구분기준, 약국명, 도로명주소, 전화번호 =====
$lines = [System.IO.File]::ReadAllLines("$base\대전광역시 유성구_약국현황_20250731.csv", [System.Text.Encoding]::GetEncoding("euc-kr"))
Write-Host "유성구 header: $($lines[0])"
for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "") { continue }
    $row = ParseCSVLine $lines[$i]
    if ($row.Count -ge 5) {
        $results.Add(@{
            district = "유성구"
            name = CleanField $row[2]
            address = CleanField $row[3]
            phone = CleanField $row[4]
        })
    }
}
Write-Host "유성구: $(($results | Where-Object { $_['district'] -eq '유성구' }).Count)"

# ===== 중구: 번호, 약국명칭, 약국전화번호, 약국번호(도로명), 약국주소(도로명), 한줄번호 =====
$lines = [System.IO.File]::ReadAllLines("$base\대전광역시 중구 약국 정보_20250905.csv", [System.Text.Encoding]::GetEncoding("euc-kr"))
Write-Host "중구 header: $($lines[0])"
for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -eq "") { continue }
    $row = ParseCSVLine $lines[$i]
    if ($row.Count -ge 5) {
        $results.Add(@{
            district = "중구"
            name = CleanField $row[1]
            address = CleanField $row[4]
            phone = CleanField $row[2]
        })
    }
}
Write-Host "중구: $(($results | Where-Object { $_['district'] -eq '중구' }).Count)"

Write-Host "`n전체: $($results.Count)"

# Filter empty addresses
$filtered = $results | Where-Object { $_['address'] -and $_['address'].Length -gt 5 }
Write-Host "주소 있는 약국: $($filtered.Count)"

# Preview first 3
$filtered | Select-Object -First 3 | ForEach-Object { Write-Host ($_ | ConvertTo-Json -Compress) }

# Build JSON
$jsonArr = $filtered | ForEach-Object {
    $name = $_.name -replace '\\', '\\\\' -replace '"', '\"'
    $addr = $_.address -replace '\\', '\\\\' -replace '"', '\"'
    $phone = $_.phone -replace '\\', '\\\\' -replace '"', '\"'
    $dist = $_.district -replace '\\', '\\\\' -replace '"', '\"'
    "  {`"district`":`"$dist`",`"name`":`"$name`",`"address`":`"$addr`",`"phone`":`"$phone`"}"
}

$json = "[$([Environment]::NewLine)$($jsonArr -join ",`n")$([Environment]::NewLine)]"
[System.IO.File]::WriteAllText("$base\pharmacies.json", $json, [System.Text.Encoding]::UTF8)
Write-Host "저장 완료: $base\pharmacies.json"
