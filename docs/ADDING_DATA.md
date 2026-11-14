# Adding data to Parallax Dial

1. Choose a unique field ID and create its directory in web/public/data.
2. Write field.json against the frozen contract. Include provenance, dates, wavelength, detector and valid pair references. For v1.1 include pixel dimensions.
3. Put the PNGs in that directory. Include optional timeline.json and per-pair difference PNGs when available.
4. Add an index.json entry with the matching ID, kind, title and thumbnail. Optional date range and frame count appear in the picker. Use pending for unreleased fields.
5. From web run npm test, npm run build and npm run dev. Open the new field and verify the timeline, metadata, source links and any Distance mode.
