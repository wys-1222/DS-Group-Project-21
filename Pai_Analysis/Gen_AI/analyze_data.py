import json
import os
import pandas as pd
import geopandas as gpd
from shapely.validation import explain_validity
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Path to the dataset
data_path = '/Users/pranavpai/Code/Data Sci Project/DS-Group-Project-21/Pai_Analysis/Pai_EDA_Area/data_unzipped/areas/osm-osm-traffic-a-2021-na/osm-osm-traffic-a-2021-na.json'

# Check if file exists
if not os.path.exists(data_path):
    print(f"File not found: {data_path}")
    exit(1)

# Load the data
print(f"Loading data from {data_path}")
try:
    with open(data_path, 'r') as f:
        data = json.load(f)
    
    print("\nData type:", type(data))
    print("Keys in the dictionary:", data.keys())
    print(f"Number of features: {len(data['features'])}")
    
    # Create a GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    print("\nGeoDataFrame created successfully")
    print(f"CRS: {gdf.crs}")
    print(f"Shape: {gdf.shape}")
    print(f"Columns: {gdf.columns.tolist()}")
    print(f"Geometry types: {gdf.geometry.type.value_counts()}")
    
    # Print property columns statistics
    print("\nProperty statistics:")
    for col in gdf.columns:
        if col != 'geometry':
            print(f"{col}: {gdf[col].nunique()} unique values")
    
    # Check for basic topology issues
    print("\nChecking for basic topology issues...")
    invalid_geoms = ~gdf.is_valid
    if invalid_geoms.any():
        print(f"Found {invalid_geoms.sum()} invalid geometries")
        
        # Sample a few invalid geometries to understand the issues
        invalid_sample = gdf[invalid_geoms].head(5)
        for idx, row in invalid_sample.iterrows():
            print(f"Invalid geometry at index {idx}: {explain_validity(row.geometry)}")
    else:
        print("All geometries are valid")
    
    # Additional topological checks
    print("\nAdditional topological properties:")
    
    # Check for empty geometries
    empty_geoms = gdf[gdf.geometry.is_empty]
    print(f"Empty geometries: {len(empty_geoms)}")
    
    # Check for duplicated geometries
    dup_geoms = gdf[gdf.geometry.duplicated()]
    print(f"Duplicated geometries: {len(dup_geoms)}")
    
    # Check for self-intersections in a sample
    print("\nChecking for self-intersections in a sample of 100 geometries...")
    sample_gdf = gdf.sample(min(100, len(gdf)))
    self_intersections = 0
    for geom in sample_gdf.geometry:
        try:
            if not geom.is_simple:
                self_intersections += 1
        except:
            # Some complex geometries might error on is_simple
            pass
    print(f"Self-intersections detected: {self_intersections} out of 100 sampled")
    
    # Check for very small or zero-area geometries
    small_area_threshold = 1e-10
    small_areas = gdf[gdf.geometry.area < small_area_threshold]
    print(f"Very small area geometries: {len(small_areas)}")
    
    # Check for overlapping geometries in a small sample
    print("\nChecking for overlapping geometries in a sample...")
    sample_size = min(50, len(gdf))
    sample_gdf = gdf.sample(sample_size)
    
    overlaps = 0
    for i in range(sample_size):
        for j in range(i+1, sample_size):
            geom1 = sample_gdf.iloc[i].geometry
            geom2 = sample_gdf.iloc[j].geometry
            try:
                if geom1.intersects(geom2) and not geom1.touches(geom2):
                    overlaps += 1
                    if overlaps <= 5:  # Only show first 5 examples
                        print(f"Overlap between features at indices {sample_gdf.index[i]} and {sample_gdf.index[j]}")
            except:
                # Skip if error in intersection check
                pass
    
    print(f"Found {overlaps} overlapping geometries in the sample")
    
    # Extract a subset for AI analysis
    print("\nExtracting a subset for AI analysis...")
    
    # If some invalid geometries found, include them in the subset
    if invalid_geoms.any():
        subset = gdf[invalid_geoms].head(10)
        print("Including 10 invalid geometries in the subset")
    else:
        # Try to find interesting cases for topology analysis
        # Look for features with the most complex geometries (many points)
        gdf['point_count'] = gdf.geometry.apply(lambda g: sum(len(list(p.exterior.coords)) for p in g.geoms))
        complex_geoms = gdf.sort_values('point_count', ascending=False).head(5)
        
        # Look for features that are nearby each other (potential topology issues)
        sample_indices = gdf.sample(min(50, len(gdf))).index
        nearby_candidates = []
        
        for i in sample_indices:
            for j in sample_indices:
                if i != j:
                    try:
                        if gdf.loc[i, 'geometry'].distance(gdf.loc[j, 'geometry']) < 0.0001:
                            nearby_candidates.append((i, j))
                    except:
                        pass
        
        print(f"Found {len(nearby_candidates)} nearby geometry pairs")
        
        # Create a subset with complex geometries and some nearby features
        subset_indices = list(complex_geoms.index)
        for i, j in nearby_candidates[:5]:  # Take first 5 pairs
            if i not in subset_indices:
                subset_indices.append(i)
            if j not in subset_indices:
                subset_indices.append(j)
        
        subset = gdf.loc[subset_indices]
        print(f"Created a subset with {len(subset)} features")
    
    # Save the subset to a file for AI analysis
    subset_file = 'subset_for_ai.json'
    subset_geojson = json.loads(subset.to_json())
    with open(subset_file, 'w') as f:
        json.dump(subset_geojson, f)
    
    print(f"Saved subset to {subset_file}")
    
    # Example potential topological questions for the AI
    print("\nPotential topological questions for AI analysis:")
    questions = [
        "Can you identify any invalid geometries in this dataset and explain why they're invalid?",
        "How would you fix self-intersecting polygons in this dataset?",
        "What are the best practices for handling overlapping polygons in geospatial data?",
        "Can you identify any polygons with holes that may cause topological issues?",
        "How would you validate if a MultiPolygon has the correct orientation (exterior ring counter-clockwise, holes clockwise)?",
        "What methods would you use to simplify complex geometries while preserving topology?",
        "How would you detect and fix sliver polygons in this dataset?",
        "What approaches would you recommend for fixing gaps between adjacent polygons?",
        "How would you ensure topological consistency when merging adjacent polygons?",
        "Can you identify any potential precision issues in the coordinates of these geometries?"
    ]
    
    for i, q in enumerate(questions):
        print(f"{i+1}. {q}")

except Exception as e:
    print(f"Error analyzing data: {e}") 