<#
.SYNOPSIS
    Remove running heads (repeated book-title / section-title + page-number
    lines) from a paged text document produced from a scanned book.

.DESCRIPTION
    After every "----- Page N -----" marker, this script removes up to
    MaxHeaderLines (default 2) short lines that are page-header noise:
      * a page number (digits or Roman numerals), and/or
      * a line containing one of the -Keywords (e.g. "HISTORY OF MAGIC",
        "PREFACE"), i.e. the book/section title repeated at the top of
        every page.
    Header lines are only removed when they are SHORT (<= MaxLineLen, default
    25 chars) -- a longer line is treated as real page content and kept.
    Lines starting with "CHAPTER" are always kept (chapter headings are
    content, not running heads).
    Blank lines directly after the marker are dropped; the content that
    follows the header is preserved.

    Example (before):
        ----- Page 10 -----
        AN HISTORY OF MAGIC,
        23
        IT was a principal object ...
    Example (after):
        ----- Page 10 -----
        IT was a principal object ...

.PARAMETER Path
    Input text file (the paged document).

.PARAMETER OutPath
    Output file. Defaults to "<Path without extension>_clean.txt".
    Use -OutPath $Path to overwrite in place.

.PARAMETER MaxHeaderLines
    Maximum number of header lines to remove per page (default 2).

.PARAMETER MaxLineLen
    A line longer than this is considered real content and never removed
    (default 25).

.PARAMETER Keywords
    Substrings that mark a line as a repeated book/section title. Defaults
    cover the running heads of the Colquhoun book; pass your own list for
    other books.

.EXAMPLE
    .\remove-running-heads.ps1 -Path .\output\book.txt -OutPath .\output\book_clean.txt
#>
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$OutPath = '',
    [int]$MaxHeaderLines = 2,
    [int]$MaxLineLen = 25,
    [string[]]$Keywords = @('HISTORY OF MAGIC', 'PREFACE', 'INTRODUCTION',
                            'CONTENTS', 'INDEX', 'APPENDIX', 'SUPPLEMENT', 'NOTES')
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Path)) { throw "Input file not found: $Path" }
if (-not $OutPath) {
    $dir  = Split-Path -Parent (Resolve-Path -LiteralPath $Path).Path
    $base = [System.IO.Path]::GetFileNameWithoutExtension((Resolve-Path -LiteralPath $Path).Path)
    $OutPath = Join-Path $dir ($base + '_clean.txt')
}

$text = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path).Path)
$lines = $text -split "`n"
for ($k = 0; $k -lt $lines.Count; $k++) { $lines[$k] = $lines[$k].TrimEnd("`r") }

$romanRe  = '^(?:[ivxlcdmIVXLCDM]+)$'
$markerRe = '^----- Page \d+ -----$'

$out    = [System.Collections.Generic.List[string]]::new()
$removedCount = 0
$pagesProcessed = 0
$scan = $false          # currently scanning the header zone of a page
$removedThisPage = 0
$removedSamples = [System.Collections.Generic.List[string]]::new()

foreach ($line in $lines) {
    # --- normalize a marker glued to page content onto its own line ---
    $m = [regex]::Match($line, '----- Page \d+ -----')
    if ($m.Success -and $line.Trim() -ne $m.Value) {
        $before = $line.Substring(0, $m.Index).TrimEnd()
        $after  = $line.Substring($m.Index + $m.Length)
        if ($before) { $out.Add($before) }
        $out.Add($m.Value)
        if ($after)  { $out.Add($after) }
        $pagesProcessed++
        $scan = $true
        $removedThisPage = 0
        continue
    }

    if ($line -match $markerRe) {
        $out.Add($line)
        $pagesProcessed++
        $scan = $true
        $removedThisPage = 0
        continue
    }

    if ($scan) {
        $s = $line.Trim()
        if ($s -eq '') { continue }                # drop blank line(s) after the marker
        if ($s -eq '[blank page]') { $out.Add($line); $scan = $false; continue }
        if ($s.Length -gt $MaxLineLen) { $out.Add($line); $scan = $false; continue }   # real content

        $isChapter    = $s -match '^(?i)chapter\b'
        $isPageNumber = ($s -match '^\d+$') -or ($s -match $romanRe)
        $hasKeyword   = $false
        foreach ($k in $Keywords) {
            if ($s.IndexOf($k, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { $hasKeyword = $true; break }
        }

        if (-not $isChapter -and ($isPageNumber -or $hasKeyword) -and $removedThisPage -lt $MaxHeaderLines) {
            $removedThisPage++
            $removedCount++
            if ($removedSamples.Count -lt 8) { $removedSamples.Add($line.Trim()) }
            continue                             # header line removed
        }

        $out.Add($line)                          # short line that is content -> keep it
        if ($removedThisPage -eq 0) { $scan = $false }   # nothing removed yet -> headers are done
        continue
    }

    $out.Add($line)
}

$result = ($out -join "`n") + "`n"
[System.IO.File]::WriteAllText($OutPath, $result, [System.Text.UTF8Encoding]::new($false))

Write-Host "Pages processed : $pagesProcessed"
Write-Host "Header lines removed: $removedCount"
Write-Host "Output          : $OutPath"
if ($removedSamples.Count -gt 0) {
    Write-Host "Sample removed lines:"
    $removedSamples | ForEach-Object { Write-Host ("  - " + $_) }
}
