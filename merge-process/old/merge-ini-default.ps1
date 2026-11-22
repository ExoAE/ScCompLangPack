$replacements = @{}
Get-Content .\modified_global.ini | ForEach-Object {
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
} | Set-Content "B:\Games\StarCitizen\ScCompLangPack\ScCompLangPack\data\Localization\english\global_merged.ini" -Encoding UTF8