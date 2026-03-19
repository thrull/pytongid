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
```bash
Structural tokens:
  obj: 78
  endobj: 78
  stream: 30
  endstream: 30
  xref: 1
  trailer: 1
  startxref: 1
  %%EOF: 0

Dictionary tags:
  /Type: 43
  /Filter: 30
  /FlateDecode: 30
  /Length: 30
  /Subtype: 30
  /Font: 24
  /BaseFont: 20
  /FontDescriptor: 16
  /URI: 14
  /Encoding: 12
  /GGGGGG+SegoeUI: 9
  /Ascent: 8
  /CIDFontType2: 8
  /CIDSet: 8
  /CIDSystemInfo: 8
  /CIDToGIDMap: 8
...
  /Pages: 2
  /Width: 2
  /Annots: 1
  /Author: 1
  /BBox: 1
  /CalRGB: 1
  /Catalog: 1
  /Count: 1
  /CreationDate: 1
  /DeviceGray: 1
  /Form: 1
  /Gamma: 1

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

```json
{
  "dates": [
    {
      "name": "/CreationDate",
      "value": "D:20251015025826+00'00'"
    },
    {
      "name": "/ModDate",
      "value": "D:20251015025826+00'00'"
    }
  ],
  "dictionary_tag_hexcodes": {},
  "dictionary_tags": {
    "/A": 7,
    "/Action": 7,
    "/Annots": 1,
    "/Ascent": 8,
    "/Author": 1,
    "/BBox": 1,
    "/Contents": 3,
    "/Count": 1,
    "/CreationDate": 1,
    "/DW": 8,
    "/DescendantFonts": 8,
    "/Descent": 8,
    "/DeviceGray": 1,
    "/Encoding": 12,
    "/Filter": 30,
    "/Flags": 8,
    "/FlateDecode": 30,
...
    "/Root": 1,
    "/S": 7,
    "/SMask": 1,
    "/Size": 1,
    "/StemV": 8,
    "/Style": 8,
    "/Subtype": 30,
    "/Supplement": 8,
    "/URI": 14,
    "/W": 8,
    "/WhitePoint": 1,
    "/Width": 2,
    "/WinAnsiEncoding": 4,
    "/XObject": 6
  },
  "tokens": {
    "endobj": 78,
    "endstream": 30,
    "obj": 78,
    "startxref": 1,
    "stream": 30,
    "trailer": 1,
    "xref": 1
  }
}
```

### PDFiD-like XML output

```bash
python pytongid.py sample.pdf --pdfid
```

Example root element:

```xml
<PDFiD ErrorOccured="False" ErrorMessage="" Filename="SOME_Invoice.pdf" Header="%PDF-1.7" IsPDF="True" Version="0.0.4" Entropy="7.98">
  <Keywords>
    <Keyword Count="78" HexcodeCount="0" Name="obj"/>
    <Keyword Count="78" HexcodeCount="0" Name="endobj"/>
    <Keyword Count="30" HexcodeCount="0" Name="stream"/>
    <Keyword Count="30" HexcodeCount="0" Name="endstream"/>
    <Keyword Count="1" HexcodeCount="0" Name="xref"/>
    <Keyword Count="1" HexcodeCount="0" Name="trailer"/>
    <Keyword Count="1" HexcodeCount="0" Name="startxref"/>
    <Keyword Count="3" HexcodeCount="0" Name="/Page"/>
    <Keyword Count="0" HexcodeCount="0" Name="/Encrypt"/>
    <Keyword Count="0" HexcodeCount="0" Name="/ObjStm"/>
    <Keyword Count="0" HexcodeCount="0" Name="/JS"/>
    <Keyword Count="0" HexcodeCount="0" Name="/JavaScript"/>
    <Keyword Count="0" HexcodeCount="0" Name="/AA"/>
    <Keyword Count="0" HexcodeCount="0" Name="/OpenAction"/>
    <Keyword Count="0" HexcodeCount="0" Name="/AcroForm"/>
    <Keyword Count="0" HexcodeCount="0" Name="/JBIG2Decode"/>
    <Keyword Count="0" HexcodeCount="0" Name="/RichMedia"/>
    <Keyword Count="0" HexcodeCount="0" Name="/Launch"/>
    <Keyword Count="0" HexcodeCount="0" Name="/EmbeddedFile"/>
    <Keyword Count="0" HexcodeCount="0" Name="/XFA"/>
  </Keywords>
  <Dates>
    <Date Value="D:20251015025826+00'00'" Name="/CreationDate"/>
    <Date Value="D:20251015025826+00'00'" Name="/ModDate"/>
  </Dates>
</PDFiD>
```

## Notes

- Stream contents are skipped to reduce false positives from binary stream data.
- Dictionary tags are counted only while inside dictionary blocks (`<< ... >>`).
- Date values (for example `/ModDate (...)`) are extracted for the `<Dates>` section in PDFiD output.

