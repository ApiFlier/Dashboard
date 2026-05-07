#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def validate():
    data_dir = Path(__file__).parent.parent / "app" / "data"
    airports_file = data_dir / "airports_seed.json"
    runways_file = data_dir / "runways_seed.json"
    frequencies_file = data_dir / "frequencies_seed.json"

    errors = []
    warnings = []

    # Load data
    try:
        with open(airports_file) as f:
            airports = json.load(f)
        with open(runways_file) as f:
            runways = json.load(f)
        with open(frequencies_file) as f:
            frequencies = json.load(f)
    except Exception as e:
        print(f"Error loading files: {e}")
        sys.exit(1)

    airport_idents = {a.get("icao") for a in airports if a.get("icao")}
    
    print(f"--- Reference Data Validation ---")
    print(f"Airports: {len(airports)}")
    print(f"Runway entries: {len(runways)}")
    print(f"Frequency entries: {len(frequencies)}")

    # 1. Validate Airports
    seen_idents = set()
    for a in airports:
        ident = a.get("icao")
        if not ident:
            errors.append("Airport missing icao ident")
            continue
        
        if ident in seen_idents:
            errors.append(f"Duplicate airport ident: {ident}")
        seen_idents.add(ident)

        if not a.get("name"):
            warnings.append(f"Airport {ident} missing name")
        
        lat = a.get("lat")
        lon = a.get("lon")
        if lat is None or lon is None:
            errors.append(f"Airport {ident} missing lat/lon")
        else:
            if not (-90 <= lat <= 90):
                errors.append(f"Airport {ident} invalid lat: {lat}")
            if not (-180 <= lon <= 180):
                errors.append(f"Airport {ident} invalid lon: {lon}")
        
        if a.get("elevation_ft") is None:
            warnings.append(f"Airport {ident} missing elevation")

    # 2. Validate Runways
    for ident, rwys in runways.items():
        if ident not in airport_idents:
            errors.append(f"Runways found for unknown airport: {ident}")
        
        for r in rwys:
            rid = r.get("id")
            if not rid:
                errors.append(f"Runway in {ident} missing id")
            
            heading = r.get("heading")
            if heading is not None:
                if not (0 <= heading <= 360):
                    errors.append(f"Runway {rid} in {ident} invalid heading: {heading}")
            
            length = r.get("length_ft")
            if length is not None and length <= 0:
                warnings.append(f"Runway {rid} in {ident} non-positive length: {length}")

    # 3. Validate Frequencies
    for ident, freqs in frequencies.items():
        if ident not in airport_idents:
            errors.append(f"Frequencies found for unknown airport: {ident}")
        
        for f in freqs:
            ftype = f.get("type")
            if not ftype:
                errors.append(f"Frequency in {ident} missing type")
            
            freq = f.get("frequency")
            if freq:
                try:
                    float(freq)
                except ValueError:
                    errors.append(f"Frequency '{freq}' in {ident} is not numeric")

    # Output results
    print(f"\nWarnings: {len(warnings)}")
    for w in warnings[:10]:
        print(f"  [W] {w}")
    if len(warnings) > 10:
        print(f"  ... and {len(warnings) - 10} more")

    print(f"Errors: {len(errors)}")
    for e in errors[:10]:
        print(f"  [E] {e}")
    if len(errors) > 10:
        print(f"  ... and {len(errors) - 10} more")

    if errors:
        print("\nValidation FAILED.")
        sys.exit(1)
    else:
        print("\nValidation PASSED.")

if __name__ == "__main__":
    validate()
