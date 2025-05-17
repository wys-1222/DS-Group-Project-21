import json
import geopandas as gpd
from shapely.geometry import shape
import shapely.ops
import os
import pandas as pd
import numpy as np

# Load the subset data
subset_file = 'subset_for_ai.json'
with open(subset_file, 'r') as f:
    geospatial_data = json.load(f)

print(f"Analyzing {len(geospatial_data['features'])} features from the dataset...")
print("=" * 50)

# Convert to GeoDataFrame for analysis
gdf = gpd.GeoDataFrame.from_features(geospatial_data['features'])
print(f"Dataset contains {len(gdf)} features")
print(f"CRS: {gdf.crs}")
print(f"Geometry types: {gdf.geometry.type.value_counts()}")

# Check for basic validity
valid_geoms = gdf.is_valid
print(f"\n1. VALIDITY CHECK:")
print(f"   - Valid geometries: {valid_geoms.sum()} out of {len(gdf)}")
print(f"   - Invalid geometries: {(~valid_geoms).sum()} out of {len(gdf)}")

# If any invalid geometries, analyze them in more detail
if (~valid_geoms).any():
    invalid_indices = gdf[~valid_geoms].index.tolist()
    print("   - Invalid geometries at indices:", invalid_indices)
    for idx in invalid_indices:
        geom = gdf.loc[idx, 'geometry']
        try:
            reason = shapely.validation.explain_validity(geom)
            print(f"   - Issue at index {idx}: {reason}")
        except:
            print(f"   - Issue at index {idx}: (Could not determine specific reason)")

# Check for self-intersections in all geometries
print("\n2. SELF-INTERSECTION CHECK:")
self_intersections = 0
for idx, geom in enumerate(gdf.geometry):
    try:
        # Check if the geometry is simple (no self-intersections)
        if not geom.is_simple:
            self_intersections += 1
            print(f"   - Self-intersection found at index {idx}")
    except Exception as e:
        print(f"   - Could not check self-intersection at index {idx}: {e}")

print(f"   - Self-intersections found: {self_intersections} out of {len(gdf)}")

# Check for ring orientation (exterior should be clockwise, holes counter-clockwise)
print("\n3. RING ORIENTATION CHECK:")
orientation_issues = 0
for idx, geom in enumerate(gdf.geometry):
    try:
        # Multi-part geometries need to be checked part by part
        if geom.geom_type == 'MultiPolygon':
            for i, part in enumerate(geom.geoms):
                # Check exterior ring
                if part.exterior.is_ccw:  # Counter-clockwise exterior (should be clockwise)
                    orientation_issues += 1
                    print(f"   - Incorrect orientation at index {idx} (part {i}): exterior ring is counter-clockwise")
                # Check any interior rings (holes)
                for j, interior in enumerate(part.interiors):
                    if not interior.is_ccw:  # Clockwise interior (should be counter-clockwise)
                        orientation_issues += 1
                        print(f"   - Incorrect orientation at index {idx} (part {i}, hole {j}): interior ring is clockwise")
        elif geom.geom_type == 'Polygon':
            # Check exterior ring
            if geom.exterior.is_ccw:  # Counter-clockwise exterior (should be clockwise)
                orientation_issues += 1
                print(f"   - Incorrect orientation at index {idx}: exterior ring is counter-clockwise")
            # Check any interior rings (holes)
            for j, interior in enumerate(geom.interiors):
                if not interior.is_ccw:  # Clockwise interior (should be counter-clockwise)
                    orientation_issues += 1
                    print(f"   - Incorrect orientation at index {idx} (hole {j}): interior ring is clockwise")
    except Exception as e:
        print(f"   - Could not check ring orientation at index {idx}: {e}")

print(f"   - Orientation issues found: {orientation_issues}")

# Check for precision issues
print("\n4. PRECISION ISSUES CHECK:")
# Count very close vertices (potential precision issues)
close_vertices_threshold = 1e-8  # Threshold for "too close" vertices
close_vertices_count = 0
duplicate_vertices = 0

for idx, geom in enumerate(gdf.geometry):
    try:
        if geom.geom_type == 'MultiPolygon':
            for i, part in enumerate(geom.geoms):
                coords = list(part.exterior.coords)
                # Check for consecutive vertices that are very close
                for j in range(len(coords) - 1):
                    if j+1 < len(coords):
                        dist = np.sqrt((coords[j][0] - coords[j+1][0])**2 + (coords[j][1] - coords[j+1][1])**2)
                        if dist < close_vertices_threshold and dist > 0:
                            close_vertices_count += 1
                        if dist == 0:
                            duplicate_vertices += 1
        elif geom.geom_type == 'Polygon':
            coords = list(geom.exterior.coords)
            # Check for consecutive vertices that are very close
            for j in range(len(coords) - 1):
                if j+1 < len(coords):
                    dist = np.sqrt((coords[j][0] - coords[j+1][0])**2 + (coords[j][1] - coords[j+1][1])**2)
                    if dist < close_vertices_threshold and dist > 0:
                        close_vertices_count += 1
                    if dist == 0:
                        duplicate_vertices += 1
    except Exception as e:
        print(f"   - Could not check precision issues at index {idx}: {e}")

print(f"   - Very close vertices found: {close_vertices_count}")
print(f"   - Duplicate consecutive vertices found: {duplicate_vertices}")

# Check for very small geometries (potentially causing precision issues)
print("\n5. VERY SMALL GEOMETRIES CHECK:")
areas = gdf.geometry.area
small_area_threshold = 1e-10
small_areas = areas[areas < small_area_threshold]
print(f"   - Very small geometries (area < {small_area_threshold}): {len(small_areas)}")
if len(small_areas) > 0:
    for idx in small_areas.index:
        print(f"   - Small geometry at index {idx}, area: {areas[idx]}")

# Check for overlapping geometries (topology errors)
print("\n6. OVERLAPPING GEOMETRIES CHECK:")
overlaps = 0
# For efficiency, only check a subset of geometries for overlap
sample_size = min(20, len(gdf))
sample_indices = np.random.choice(gdf.index, sample_size, replace=False)
sample_gdf = gdf.loc[sample_indices]

for i in range(sample_size):
    for j in range(i+1, sample_size):
        idx1 = sample_indices[i]
        idx2 = sample_indices[j]
        geom1 = sample_gdf.iloc[i].geometry
        geom2 = sample_gdf.iloc[j].geometry
        try:
            if geom1.intersects(geom2) and not geom1.touches(geom2):
                # Check if the overlap is significant (not just a boundary touch)
                intersection = geom1.intersection(geom2)
                if intersection.area > 0:
                    overlaps += 1
                    print(f"   - Overlap between features at indices {idx1} and {idx2}")
                    print(f"     Intersection area: {intersection.area}")
        except Exception as e:
            print(f"   - Could not check overlap between indices {idx1} and {idx2}: {e}")

print(f"   - Overlapping geometries found in sample: {overlaps} out of {sample_size*(sample_size-1)//2} pairs checked")

# Check for coordinate precision issues
print("\n7. COORDINATE PRECISION CHECK:")
# Count the number of decimal places in coordinates
decimal_places = []
for idx, geom in enumerate(gdf.geometry.head(5)):  # Check first 5 geometries for efficiency
    if geom.geom_type == 'MultiPolygon':
        coords = list(geom.geoms[0].exterior.coords)
    elif geom.geom_type == 'Polygon':
        coords = list(geom.exterior.coords)
    else:
        continue
    
    # Check first few coordinates
    for i, coord in enumerate(coords[:5]):
        for val in coord:
            str_val = str(val)
            if '.' in str_val:
                decimal_count = len(str_val.split('.')[1])
                decimal_places.append(decimal_count)

if decimal_places:
    avg_decimals = sum(decimal_places) / len(decimal_places)
    print(f"   - Average decimal places in coordinates: {avg_decimals:.2f}")
    print(f"   - Maximum decimal places in coordinates: {max(decimal_places)}")
    if max(decimal_places) > 10:
        print("   - WARNING: High coordinate precision may cause computation issues")

print("\n" + "=" * 50)
print("SUMMARY OF TOPOLOGICAL ISSUES:")
print(f"1. Invalid geometries: {(~valid_geoms).sum()}")
print(f"2. Self-intersections: {self_intersections}")
print(f"3. Ring orientation issues: {orientation_issues}")
print(f"4. Very close vertices: {close_vertices_count}")
print(f"5. Duplicate vertices: {duplicate_vertices}")
print(f"6. Very small geometries: {len(small_areas)}")
print(f"7. Overlapping geometries in sample: {overlaps}")
print("=" * 50) 