# The Development League website

Next.js (App Router) + Tailwind, dark theme, mobile first. Maps are drawn with Konva.

```bash
npm install
API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
npm test          # plain unit tests (node --test)
npm run lint
npm run typecheck
```

The site proxies `/api/*` and `/media/*` to the Django API (`API_URL`, read when the
site is built or started), so the browser only talks to one origin and the sign-in
cookies stay first-party. Django needs `DJANGO_CSRF_TRUSTED_ORIGINS` to include the
site's origin (e.g. `http://localhost:3000`).

Staff screens:

- `/staff/matches`: published matches and how many team rotations are confirmed.
- `/staff/matches/{id}/plot`: the plotting tool. The auto draft is shown dashed; fix it,
  then confirm. Keys: `1-9`/`Tab` team, `Q` drop, `W E R T U I` zones 1-6, `Y` final,
  `X` eliminated, `A` extra, `C` copy the previous position, `Ctrl+Z` undo, `S` save,
  `Enter` confirm and next team.
- `/staff/maps/{slug}/calibrate` (Super Admin): upload a map image and drag the fight
  dots onto it, or add known points for a precise fit.

World coordinates are stored everywhere; `lib/coordinates.ts` converts to pixels with the
same maths as `backend/apps/maps/calibration.py`.
