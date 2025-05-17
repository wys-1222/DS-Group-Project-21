import json
import geopandas as gpd
from shapely.geometry import shape, mapping
import matplotlib.pyplot as plt
import numpy as np

def validate_self_intersection():
    """
    Validate if there are self-intersections in the subset_with_error.json file.
    This script will:
    1. Load the GeoJSON file
    2. Convert features to Shapely geometries
    3. Check for self-intersections
    4. Visualize the problematic feature
    """
    print("Validating self-intersections in subset_with_error.json...")
    
    # Load the GeoJSON file
    with open('subset_with_error.json', 'r') as f:
        data = json.load(f)
    
    # Print basic info about the dataset
    print(f"Dataset has {len(data['features'])} features")
    
    # Convert to GeoDataFrame for analysis
    gdf = gpd.GeoDataFrame.from_features(data['features'])
    
    # Check each geometry for self-intersections
    self_intersections = []
    for idx, row in gdf.iterrows():
        geom = row.geometry
        feature_id = row.get('id', str(idx))
        
        # Check if geometry is simple (no self-intersections)
        try:
            if not geom.is_simple:
                print(f"Self-intersection detected in feature {feature_id}")
                self_intersections.append((idx, feature_id, geom))
            else:
                print(f"Feature {feature_id} does not have self-intersections")
        except Exception as e:
            print(f"Error checking feature {feature_id}: {e}")
    
    print(f"\nFound {len(self_intersections)} features with self-intersections")
    
    # Visualize the problematic geometries
    if self_intersections:
        fig, axes = plt.subplots(len(self_intersections), 1, figsize=(10, 5*len(self_intersections)))
        if len(self_intersections) == 1:
            axes = [axes]
        
        for i, (idx, feature_id, geom) in enumerate(self_intersections):
            # Plot the geometry
            if geom.geom_type == 'MultiPolygon':
                xs, ys = [], []
                for polygon in geom.geoms:
                    x, y = polygon.exterior.xy
                    xs.extend(x)
                    ys.extend(y)
                    xs.append(None)  # Add None to create a break between polygons
                    ys.append(None)
                axes[i].plot(xs, ys, 'r-')
            else:
                x, y = geom.exterior.xy
                axes[i].plot(x, y, 'r-')
            
            # Add markers for self-intersection points
            if hasattr(geom, 'interiors'):
                for interior in geom.interiors:
                    ix, iy = interior.xy
                    axes[i].plot(ix, iy, 'b--')
            
            axes[i].set_title(f"Feature {feature_id} with self-intersection")
            axes[i].grid(True)
        
        plt.tight_layout()
        plt.savefig('self_intersection_visualization.png')
        print("Visualization saved as 'self_intersection_visualization.png'")
    
    # Explain why the Mistral 7B model might have missed the self-intersection
    print("\nExplanation of why Mistral 7B missed the self-intersection:")
    print("1. Feature Simplification: The test.py code simplifies features by taking every nth point")
    print("   to reduce token count. This might have removed the self-intersection points.")
    print("2. Resolution Issues: Small self-intersections might be undetectable at certain scales.")
    print("3. Model Limitations: The 7B model has less parameter capacity to correctly identify")
    print("   complex geometric issues compared to larger models.")
    print("4. Understanding of Coordinates: The model might lack proper understanding of")
    print("   how to evaluate spatial coordinates for self-intersections.")
    print("5. Prompt Structure: The prompt might not have emphasized checking for self-intersections")
    print("   or explained what to look for specifically.")

# Explain the purpose of simplifying polygons
def explain_simplification():
    """Explain why we simplify polygons and what it means for each feature."""
    print("\nExplanation of polygon simplification:")
    print("1. Token Reduction: GeoJSON features often contain thousands of points. Simplification")
    print("   reduces the number of points to fit within the token limits of language models.")
    print("2. Processing Efficiency: Fewer points means faster processing and analysis.")
    print("3. Impact on Features:")
    print("   - Reduced Detail: Simplification removes vertices, decreasing the detail of the polygon.")
    print("   - Changed Shape: The outline of features becomes more angular and less precise.")
    print("   - Potential Loss of Critical Points: Some points that define important topology")
    print("     (like self-intersections) might be removed during simplification.")
    print("   - Modified Spatial Relationships: Simplification might change the relationships")
    print("     between features (e.g., removing overlap or creating artificial gaps).")
    print("4. Simplification Methods: The code uses a stride-based approach, taking every nth point")
    print("   rather than Douglas-Peucker or other topology-preserving methods.")
    print("5. Trade-offs: There's always a balance between keeping token count low and preserving")
    print("   enough detail to enable accurate topological analysis.")

if __name__ == "__main__":
    validate_self_intersection()
    explain_simplification() 