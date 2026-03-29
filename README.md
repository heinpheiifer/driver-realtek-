# Solar Site Health & Safety App (Simple Mobile Web App)

A lightweight, phone-friendly app for small electrical teams doing solar installations.

## What it does

- Captures business/job/site details
- Provides a practical risk checklist aligned to common AS/NZS + WorkSafe style controls
- Lets you take or attach site photos
- Adds photo captions
- Exports a final PDF report with checklist outcomes, notes, sign-off, and photos
- Saves drafts locally on the device/browser

## Run it

No build step required.

1. Open `app/index.html` in a browser, or
2. Serve the folder with any static server (recommended for mobile sharing), for example:

```bash
python3 -m http.server 8080
```

Then open `http://<your-ip>:8080/app/` on your phone (same network).

## Compliance note

This app is a practical field form and **not legal advice**. You should review your process against the relevant standards and guidance for your jurisdiction, including (where applicable):

- AS/NZS 3000
- AS/NZS 5033
- State/Territory WorkSafe requirements

## Data storage

- Drafts are stored in browser local storage on the device.
- No backend or cloud storage is included in this version.
