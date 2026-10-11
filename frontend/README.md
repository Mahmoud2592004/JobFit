# Pathly (React + TypeScript)

Vite + React 18 + TypeScript port of the original `JobFit.html`. CSS is carried over unchanged (`src/styles.css`).

```bash
npm install
npm run dev      # local dev server
npm run build    # typecheck + production build
```

## Structure
- `src/styles.css` – original stylesheet, verbatim
- `src/types.ts`, `src/lib.ts` – types, sample jobs, matching / tailoring logic
- `src/store.tsx` – app state context, persisted to `localStorage` (`pathly` key)
- `src/App.tsx` – hash router (`#/login`, `#/dash`, `#/jobs`, `#/tailor/ID[/RID]`, ...); other hashes show the landing page
- `src/pages/Landing.tsx` + `src/components/ProcessShow.tsx` – marketing page and the scroll-driven three.js scene (three pinned to r128, as in the original)
- `src/pages/*` – workspace screens
