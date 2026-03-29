# Solar COC & Commissioning App

A lightweight browser-based app to capture solar installation compliance and commissioning records, including:

- Electrical Certificate of Compliance (COC) fields
- Commissioning checklist
- PV string test measurements
- Inverter/AC test values
- Installation and electrical test photos with captions
- Local autosave, JSON export/import, and printable report output

## Run

No build step required.

1. Open `index.html` in any modern browser.
2. Fill out the sections.
3. Add installation and electrical test photos.
4. Use:
   - **Save Draft** (local browser storage)
   - **Export JSON / Import JSON** for backup/share
   - **Print Report** to generate a report-style document.

## Notes

- Data is saved in your browser under local storage key `solar-coc-commissioning-data-v1`.
- Photos are stored as base64 data in browser storage and JSON exports. Large photo sets can produce large files.
- This is a static app and does not send data to any server.
