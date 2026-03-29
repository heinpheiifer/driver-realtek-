# Solar COC & Commissioning App

A lightweight browser-based app to capture solar installation compliance and commissioning records, including:

- Electrical Certificate of Compliance (COC) fields
- Electrical worker + supervised worker detail capture
- Commissioning checklist
- PV string test measurements
- Inverter/AC test values
- Installation and electrical test photos with captions
- Local autosave, JSON export/import, and printable report output
- Multi-job dashboard (create/switch/duplicate/delete jobs)
- Drawn signature pad per job
- PDF export and email draft workflow
- Branded PDF header (company name + optional logo) with certificate-style declaration page

## Run

No build step required.

1. Open `index.html` in any modern browser.
2. Fill out the sections.
3. Add installation and electrical test photos.
4. Use:
   - **Save Draft** (local browser storage)
   - **Export JSON / Import JSON** for backup/share
   - **Print Report** to generate a report-style document
   - **Export PDF** to download a structured, branded certificate-style PDF
   - **Email Report** to open your email client with a prefilled draft summary (attach the exported PDF before sending)

5. (Optional) In **Jobs Dashboard** set:
   - **Company / Brand Name**
   - **Brand Logo** (image upload)
   These are applied to the PDF header and saved per job.

6. To test with sample data and output:
   - Import `examples/example-job-data.json` using **Import JSON**
   - Review `examples/example-generated-report.md` for a representative report structure/content

## Notes

- Data is saved in your browser under local storage key `solar-coc-commissioning-data-v1`.
- Photos are stored as base64 data in browser storage and JSON exports. Large photo sets can produce large files.
- This is a static app and does not send data to any server.
