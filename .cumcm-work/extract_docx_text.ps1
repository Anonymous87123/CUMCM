param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

Add-Type -AssemblyName System.IO.Compression.FileSystem

$resolvedInput = (Resolve-Path -LiteralPath $InputPath).Path
$zip = [System.IO.Compression.ZipFile]::OpenRead($resolvedInput)
try {
    $entry = $zip.GetEntry('word/document.xml')
    if ($null -eq $entry) {
        throw "word/document.xml not found in $resolvedInput"
    }

    $stream = $entry.Open()
    $reader = [System.IO.StreamReader]::new($stream, [Text.UTF8Encoding]::new($false))
    try {
        [xml]$documentXml = $reader.ReadToEnd()
    }
    finally {
        $reader.Dispose()
        $stream.Dispose()
    }

    $namespace = [System.Xml.XmlNamespaceManager]::new($documentXml.NameTable)
    $namespace.AddNamespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')

    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($node in $documentXml.SelectNodes('/w:document/w:body/*', $namespace)) {
        if ($node.LocalName -eq 'p') {
            $text = (($node.SelectNodes('.//w:t', $namespace) | ForEach-Object { $_.'#text' }) -join '')
            if (-not [string]::IsNullOrWhiteSpace($text)) {
                $lines.Add($text.Trim())
            }
            continue
        }

        if ($node.LocalName -eq 'tbl') {
            foreach ($row in $node.SelectNodes('./w:tr', $namespace)) {
                $cells = foreach ($cell in $row.SelectNodes('./w:tc', $namespace)) {
                    (($cell.SelectNodes('.//w:t', $namespace) | ForEach-Object { $_.'#text' }) -join '').Trim()
                }
                $lines.Add(($cells -join "`t"))
            }
        }
    }

    $outputDirectory = Split-Path -Parent $OutputPath
    if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
        [System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
    }
    [System.IO.File]::WriteAllLines($OutputPath, $lines, [Text.UTF8Encoding]::new($false))
}
finally {
    $zip.Dispose()
}
