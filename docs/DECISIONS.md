# Decisions

- Vercel serves the static Vite build. The offline Python pipeline owns science products and never runs inside the web app.
- Contract 1.0 uses a field index plus one self-contained directory per field. Band and FITS are optional for compatibility with early pipeline outputs.
- The Dev3 viewer compares two selected frames. Dial metadata is validated for integration.
- The bundled star fields, metadata, and motion marker are synthetic and are labeled DEMO DATA.
