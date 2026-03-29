# Solar Site Health & Safety App (Simple Mobile Web App)

A lightweight, phone-friendly app for small electrical teams doing solar installations.

## What it does

- Captures business/job/site details
- Includes Solar Electrix logo in app and generated PDF
- Provides a practical risk checklist aligned to common AS/NZS + WorkSafe style controls
- Lets you take or attach site photos
- Adds photo captions
- Exports a final PDF report with checklist outcomes, notes, sign-off, and photos
- Pre-fills Health & Safety contact details for Hein Pheiffer (0273288180)
- Saves drafts locally on the device/browser

## Run it

No build step required.

1. Open `app/index.html` in a browser, or
2. Serve the folder with any static server (recommended for mobile sharing), for example:

```bash
python3 -m http.server 8080
```

Then open `http://<your-ip>:8080/app/` on your phone (same network).

## Permanent web link (GitHub Pages)

This repository includes a GitHub Actions workflow to publish the app from `app/` to GitHub Pages.

1. In GitHub, open **Settings -> Pages** (one-time)
2. Under **Build and deployment**, set **Source** to **GitHub Actions** (if not already set)
3. Push to `master` (or this feature branch) and wait for the **Deploy Solar Safety App to Pages** workflow
4. Your app will be available at:
   - `https://heinpheiifer.github.io/driver-realtek-/`
   - (root redirects to `/app/`)

Note: custom-domain config has been removed for now so the GitHub URL is the primary access method.

## Compliance note

This app is a practical field form and **not legal advice**. You should review your process against the relevant standards and guidance for your jurisdiction, including (where applicable):

- AS/NZS 3000
- AS/NZS 5033
- State/Territory WorkSafe requirements

## Data storage

- Drafts are stored in browser local storage on the device.
- No backend or cloud storage is included in this version.
