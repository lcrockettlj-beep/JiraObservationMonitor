# Sprint 8 Progress Archive

**Checkpoint date:** 22 June 2026  
**Phase:** Sprint 8 — Frontend Alignment & Refresh  
**Status:** In progress

## What has been completed

### Pillar 1 — Foundation
- Shared navigation extracted into `templates/_nav.html`
- GLI logo integrated into shared nav
- Light/dark mode logo contrast issue corrected
- Shared nav applied across all main pages

### Pillar 2 — Homepage UX alignment
- Homepage source-strip changed from internal file references to operator-facing status indicators
- Engineer-oriented labels replaced with operator-friendly language on homepage
- Hero text and section descriptions rewritten for non-technical readability
- Homepage cards reduced in noise and signal hierarchy improved

### Pillar 3 — Visual branding and readability
- GLI font integrated
- Dark mode readability corrected
- Intelligence cards given glow hierarchy
- Site cards improved with warning/critical signal styling
- Light and dark mode both visually stable

## Assets already committed
- `static/img/gli.svg`
- `static/fonts/texgyreadventor-regular.woff`

## Current frontend direction
Sprint 8 is confirmed as an **alignment and refresh sprint**, not a rebuild.  
The current direction is:
- operator-friendly wording
- shared navigation and consistent branding
- dark operations-console aesthetic with GLI styling
- frontend remapped to current backend truth
- no React / Three.js / WebSocket rebuild in this sprint

## Current known next steps
1. Align `estate.html`, `reference.html`, and `detail_list.html` with homepage standards
2. Remove inline style debt into dedicated CSS files
3. Continue data-truth mapping between backend fields and frontend views
4. Update documentation only after the current frontend phase is stabilised

## Recommended next checkpoint
After replacement of the estate/reference/detail files and associated CSS, commit the following milestone:

```powershell
git add templates\estate.html templateseference.html templates\detail_list.html static\css\estate.css static\csseference.css
git commit -m "Sprint 8 Pillar 3C: Align estate, reference, and detail pages with shared branding and operator-facing UX"
git push
```
