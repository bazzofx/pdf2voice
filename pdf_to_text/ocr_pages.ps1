param(
    [string]$PagesDir = "C:\_deepSeekApps\pdf2text\temp_pages",
    [string]$OutFile  = "C:\_deepSeekApps\pdf2text\output\raw_ocr.txt",
    [int]$Count       = 0
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataWriter, Windows.Storage.Streams, ContentType = WindowsRuntime]

# Helper: synchronously await a WinRT IAsyncOperation<T> from PowerShell.
$getAwaiter = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'GetAwaiter' -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } |
    Select-Object -First 1

function Await($AsyncTask, $ResultType) {
    $Awaiter = $getAwaiter.MakeGenericMethod($ResultType).Invoke($null, @($AsyncTask))
    while (-not $Awaiter.IsCompleted) { Start-Sleep -Milliseconds 20 }
    $Awaiter.GetResult()
}

function OcrFile($path, $engine) {
    # Read the PNG bytes with plain .NET (WinRT StorageFile is sandboxed and
    # fails with "Access is denied" on arbitrary paths), then decode the
    # bitmap from an in-memory stream.
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $ms = [Windows.Storage.Streams.InMemoryRandomAccessStream]::new()
    $dw = [Windows.Storage.Streams.DataWriter]::new($ms)
    $dw.WriteBytes($bytes)
    $null = Await ($dw.StoreAsync()) ([uint32])
    $null = $dw.DetachStream()   # returns IOutputStream -- must be swallowed
    $null = $ms.Seek(0)

    try {
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ms)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $sb = New-Object System.Text.StringBuilder
        foreach ($line in $result.Lines) {
            $wordTexts = foreach ($w in $line.Words) { $w.Text }
            [void]$sb.AppendLine(($wordTexts -join ' '))
        }
        return $sb.ToString()
    } finally {
        $ms.Dispose()
    }
}

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { throw 'No OCR engine available for user profile languages.' }
Write-Host "OCR engine language: $($engine.RecognizerLanguage.LanguageTag)"

if ($Count -le 0) {
    $pngs = Get-ChildItem -Path $PagesDir -Filter 'page_*.png' -ErrorAction SilentlyContinue
    $Count = $pngs.Count
    if ($Count -le 0) { throw "No page_*.png files found in $PagesDir" }
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$writer = New-Object System.IO.StreamWriter($OutFile, $false, [System.Text.UTF8Encoding]::new($false))
try {
    for ($i = 0; $i -lt $Count; $i++) {
        $png = Join-Path $PagesDir ("page_{0:D3}.png" -f $i)
        if (-not (Test-Path $png)) {
            Write-Host "MISSING $png"
            [void]$writer.WriteLine("----- Page $($i+1) -----")
            [void]$writer.WriteLine("[missing image]")
            continue
        }
        $txt = OcrFile $png $engine
        $chars = $txt.Length
        [void]$writer.WriteLine("----- Page $($i+1) -----")
        [void]$writer.Write($txt)
        if ($chars -lt 80) { Write-Host "page $($i+1): LOW TEXT ($chars chars)" }
        if (($i + 1) % 20 -eq 0) {
            Write-Host ("{0}/{1} pages, {2:N1}s elapsed" -f ($i+1), $Count, $sw.Elapsed.TotalSeconds)
        }
    }
} finally {
    $writer.Close()
}
Write-Host ("DONE in {0:N1}s" -f $sw.Elapsed.TotalSeconds)
