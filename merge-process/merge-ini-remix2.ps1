$replacements = @{}
Get-Content .\modified_global_remix2.ini | ForEach-Object {
    if ($_ -match '^(.*?)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2]
        $replacements[$key] = $value
    }
}
Get-Content .\global.ini | ForEach-Object {
    if ($_ -match '^(.*?)(=)(.*)$') {
        $key = $matches[1].Trim()
        $prefix = $_.Substring(0, $_.IndexOf('=') + 1)
        if ($replacements.ContainsKey($key)) {
            $prefix + $replacements[$key]
        } else {
            $_
        }
    } else {
        $_
    }
} | Set-Content "B:\Games\StarCitizen\ScCompLangPack\ScCompLangPackRemix2\data\Localization\english\global_merged-remix2.ini" -Encoding UTF8