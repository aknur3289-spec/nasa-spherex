# Planet X × SPHEREx

A static observation viewer for comparing SPHEREx cutouts. Choose two epochs on the timeline and compare them side by side or with automatic Blink. The bundled observations are synthetic demo data.

```text
NASA IRSA FITS → offline Python pipeline → field.json + PNGs → React viewer
```

With Node.js 22.12 or later, run from the repository root:

```sh
npm --prefix web ci
npm --prefix web run dev
npm --prefix web test
npm --prefix web run build
npm --prefix web run preview
```

Dev3 owns the static client, data loader, contract and deployment. Dev4 owns the specialized viewer and dial integration. Dev5 owns pipeline outputs and real observations. To add a field, place its JSON and cutouts under `web/public/data/<field_id>/` and add its summary to `index.json`. See the [data contract](docs/CONTRACT.md) and [decisions](docs/DECISIONS.md).

Import this repository in Vercel, using its root directory and the checked-in configuration. Vercel builds `web/` and publishes `web/dist/`. The GitHub Actions workflow also supports production deployments when repository secret `VERCEL_TOKEN` and variables `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` are configured. Use one deployment trigger to avoid duplicate builds.
