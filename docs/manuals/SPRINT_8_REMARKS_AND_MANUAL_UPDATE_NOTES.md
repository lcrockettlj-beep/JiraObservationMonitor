# Sprint 8 Remarks and Manual Update Notes

## Purpose
This note captures what should be documented after Sprint 8 frontend alignment stabilises.

## Files that should receive remarks/comments later
- `templates/_nav.html`  
  Add a short comment that this is the shared navigation component and should remain the single source of nav structure.

- `static/css/app.css`  
  Add a short comment above the GLI logo and dark-mode readability sections explaining that they were introduced during Sprint 8 branding alignment.

- `static/css/home.css`  
  Add a short comment above the glow hierarchy sections explaining the warning/critical visual rules.

- `templates/home.html`  
  Add a brief comment above the homepage status strip explaining that operator-friendly indicators replaced internal source filenames.

## Manuals likely to update after Sprint 8
- `docs/manuals/html_project_manual.txt`
- `docs/manuals/css_project_manual.txt`
- `docs/manuals/manuals_index.txt`

## Documentation themes to add
1. Shared navigation system
2. GLI branding integration (logo + font)
3. Dark/light mode contrast strategy
4. Homepage operator-language refactor
5. CSS glow hierarchy rules for warning/critical cards
6. Inline style extraction approach for page-specific CSS

## Important note
Do not update the manuals mid-refactor.  
Document only once the current frontend state is stable and confirmed working.
