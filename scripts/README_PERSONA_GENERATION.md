# Persona Deep Dive Generation

This folder contains a repeatable generator that refreshes the persona text file from the spreadsheet CSV.

## Source of truth

- Edit in Excel: `PERSONA_DEEP_DIVE_FIRST5_FORUM_GROUNDED.xlsx`
- Export/save as CSV: `PERSONA_DEEP_DIVE_FIRST5_FORUM_GROUNDED.csv`

## Generate TXT

From repo root (`/home/mylappy/myspace/info`):

```bash
python3 scripts/generate_persona_txt.py
```

This rewrites:

- `PERSONA_DEEP_DIVE_01_05.txt`

## Check mode (CI-friendly)

```bash
python3 scripts/generate_persona_txt.py --check
```

- Returns exit code `0` if TXT matches CSV.
- Returns exit code `1` if TXT is out of date.

## Notes

- The script keeps the same layered structure (Layer 1/2/3) and section numbering.
- It preserves existing `Basic snapshot` bullets for each persona when they already exist in the output file.
- If a snapshot is missing, it uses a small fallback snapshot.
- Source links are rendered under `SOURCE EVIDENCE (USED)`.

## Expected CSV columns

The script validates required columns:

- `Persona_ID`
- `Persona_Name`
- `Layer1_Raw_Pain_Forum_Verbatim`
- `Layer1_Trigger_Scenarios_Forum`
- `Layer1_Objections_Forum`
- `Layer2_Core_Message`
- `Layer2_Grounded_Mechanism_Map`
- `Layer2_How_Kit_Solves`
- `Layer2_Trust_Anchors`
- `Layer3_English_Ready_Phrasing`
- `Layer3_Hindi_Ready_Phrasing`
- `Layer3_Hinglish_Ready_Phrasing`
- `Primary_Sources`
