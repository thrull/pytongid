# pytongid

Lightweight PDF token and dictionary-tag scanner that works on raw bytes. Identify PDF tokens and dictionary occurences for PDF document file analysis (like pdfid but better)


It reports:
- Structural tokens: `obj`, `endobj`, `stream`, `endstream`, `xref`, `trailer`, `startxref`, `%%EOF`
- Dictionary name tags found inside `<< ... >>` (for example `/Page`, `/JS`, `/JavaScript`)
- Optional PDFiD-like XML output

## Requirements

- Python 3.9+ (tested with Python 3)

## Usage

Run from the project directory:

```bash
python pytongid.py <path-to-pdf>
```

### Text report (default)

```bash
python pytongid.py sample.pdf
```

### JSON output

```bash
python pytongid.py sample.pdf --json
```

JSON includes:
- `tokens`
- `dictionary_tags`
- `dictionary_tag_hexcodes`
- `dates`

### PDFiD-like XML output

```bash
python pytongid.py sample.pdf --pdfid
```

Example root element:

```xml
<PDFiD ErrorOccured="False" ErrorMessage="" Filename="sample.pdf" Header="%PDF-1.7" IsPDF="True" Version="0.0.4" Entropy="4.28">
```

## Notes

- Stream contents are skipped to reduce false positives from binary stream data.
- Dictionary tags are counted only while inside dictionary blocks (`<< ... >>`).
- Date values (for example `/ModDate (...)`) are extracted for the `<Dates>` section in PDFiD output.

