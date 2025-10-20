# modified_global.ini in eine Hashtable laden (Key -> neuer Wert)
$replacements = @{}
Get-Content .\modified_global.ini | ForEach-Object {
    if ($_ -match '^(.*?)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2]
        $replacements[$key] = $value
    }
}

# global.ini Zeile für Zeile verarbeiten und nur Werte ersetzen
Get-Content .\global.ini | ForEach-Object {
    if ($_ -match '^(.*?)(=)(.*)$') {
        $key = $matches[1].Trim()
        $prefix = $_.Substring(0, $_.IndexOf('=') + 1)  # Alles bis inkl. '=' beibehalten (inkl. Leerzeichen!)
        if ($replacements.ContainsKey($key)) {
            $prefix + $replacements[$key]
        } else {
            $_
        }
    } else {
        $_  # Leerzeilen / Kommentare usw. bleiben unangetastet
    }
} | Set-Content .\merged.ini -Encoding UTF8
