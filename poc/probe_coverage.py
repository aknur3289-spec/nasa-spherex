#!/usr/bin/env python
"""Read-only IRSA SIA2 collection discovery and SPHEREx coverage probe."""
import csv
from pathlib import Path
from urllib.request import urlopen
import xml.etree.ElementTree as ET

import pyvo
from astropy.coordinates import SkyCoord
import astropy.units as u

from find_windows import OUT

# IRSA documents this generic SIA2 endpoint. Collection names are discovered
# from its queryable metadata at runtime; none are assumed here.
SIA_URL = "https://irsa.ipac.caltech.edu/SIA?"


def main():
    service = pyvo.dal.SIA2Service(SIA_URL)
    print(f"IRSA SIA2 service: {SIA_URL}")
    # IRSA publishes the supported parameter values in SIA2's self-description.
    # MAXREC=0 requests metadata only; this does not fetch image data.
    metadata_url = service.query_ep.rstrip("?") + "/queryables?MAXREC=0"
    with urlopen(metadata_url) as response:
        metadata = ET.fromstring(response.read())
    collection_params = [elem for elem in metadata.iter()
                         if elem.tag.endswith("PARAM") and elem.attrib.get("name", "").upper() == "COLLECTION"]
    options = [option.attrib["value"] for param in collection_params for child in param
               if child.tag.endswith("VALUES") for option in child
               if option.tag.endswith("OPTION") and "value" in option.attrib]
    collections = sorted({value for value in options if value.lower().startswith("spherex")})
    print("Available SIA2 queryable parameters and values retrieved from:", metadata_url)
    if not collections:
        raise RuntimeError("IRSA SIA2 metadata returned no collection values beginning with 'spherex'")
    print("Available SPHEREx collections:")
    for collection in collections:
        print(f"  {collection}")

    for body in ("neptune", "uranus"):
        src = OUT / f"windows_{body}.csv"
        with src.open(newline="") as f:
            windows = list(csv.DictReader(f))
        output = []
        for w in windows:
            coord = SkyCoord(float(w["ra_deg"])*u.deg, float(w["dec_deg"])*u.deg)
            found = []
            for collection in collections:
                result = service.search(pos=(coord, 0.05*u.deg),
                                        time=(w["start_utc"], w["end_utc"]),
                                        collection=collection)
                found.extend(result.to_table().to_pandas().to_dict("records"))
            # Collections can overlap in the archive; count each distinct image
            # URL once and preserve the service's returned row values.
            unique = {}
            for row in found:
                unique.setdefault(row.get("access_url", repr(row)), row)
            found = list(unique.values())
            print(f"{body} window {w['window_id']}: {len(found)} matching images")
            for row in found[:3]:
                print("  example:", {k: row.get(k) for k in row if k.lower() in {
                    "obs_id", "obsid", "t_min", "t_max", "access_url", "em_min", "em_max",
                    "band", "collection"}})
            for row in found:
                output.append({"window_id": w["window_id"], **row})
        path = OUT / f"coverage_{body}.csv"
        fields = sorted({key for row in output for key in row}) if output else ["window_id"]
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(output)
        print(f"{body}: wrote {len(output)} rows to {path}")


if __name__ == "__main__":
    main()
