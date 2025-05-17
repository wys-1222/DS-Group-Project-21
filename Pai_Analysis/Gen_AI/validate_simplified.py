import json
import geopandas as gpd
from shapely.geometry import shape, mapping
import matplotlib.pyplot as plt
import os
import glob

def validate_simplified_features():
    """
    Validate if the simplified features still contain the self-intersections.
    This script will:
    1. Load the original dataset with known self-intersections
    2. Load the simplified features from the Json directory
    3. Check each simplified feature for self-intersections
    4. Compare results to see if self-intersections were preserved
    """
    print("Validating simplified features for self-intersections...")
    
    # 1. Load the original dataset with known self-intersections
    with open('subset_with_error.json', 'r') as f:
        original_data = json.load(f)
    
    # Convert to GeoDataFrame for analysis and make sure to get the id as a column
    original_gdf = gpd.GeoDataFrame.from_features(original_data['features'])
    
    # Get the IDs from the properties or feature itself
    feature_ids = []
    for feature in original_data['features']:
        feature_ids.append(feature.get('id', str(len(feature_ids))))
    
    # Add the id column explicitly
    original_gdf['feature_id'] = feature_ids
    
    # Check each original geometry for self-intersections
    original_results = {}
    for idx, row in original_gdf.iterrows():
        geom = row.geometry
        feature_id = row['feature_id']
        
        # Check if geometry is simple (no self-intersections)
        try:
            is_simple = geom.is_simple
            original_results[feature_id] = not is_simple  # True if it has self-intersections
            if not is_simple:
                print(f"Original feature {feature_id} has self-intersections")
            else:
                print(f"Original feature {feature_id} does not have self-intersections")
        except Exception as e:
            print(f"Error checking original feature {feature_id}: {e}")
            original_results[feature_id] = None
    
    # 2. Load and validate simplified features
    simplified_files = glob.glob('Json/simplified_feature_*.json')
    simplified_results = {}
    
    for file_path in simplified_files:
        with open(file_path, 'r') as f:
            feature = json.load(f)
        
        feature_id = feature.get('id', os.path.basename(file_path).replace('simplified_feature_', '').replace('.json', ''))
        
        # Convert to shapely geometry
        geom = shape(feature['geometry'])
        
        # Check if geometry is simple (no self-intersections)
        try:
            is_simple = geom.is_simple
            simplified_results[feature_id] = not is_simple  # True if it has self-intersections
            if not is_simple:
                print(f"Simplified feature {feature_id} has self-intersections")
            else:
                print(f"Simplified feature {feature_id} does NOT have self-intersections")
        except Exception as e:
            print(f"Error checking simplified feature {feature_id}: {e}")
            simplified_results[feature_id] = None
    
    # 3. Compare results
    print("\nComparison of self-intersections:")
    print("=" * 50)
    print(f"{'Feature ID':<15} {'Original':<15} {'Simplified':<15} {'Preserved?':<10}")
    print("-" * 50)
    
    preserved_count = 0
    total_compared = 0
    
    for feature_id in original_results:
        if feature_id in simplified_results:
            orig = original_results[feature_id]
            simp = simplified_results[feature_id]
            
            if orig is not None and simp is not None:
                preserved = orig == simp
                if orig and preserved:
                    preserved_count += 1
                total_compared += 1
                
                print(f"{feature_id:<15} {'Yes' if orig else 'No':<15} {'Yes' if simp else 'No':<15} {'Yes' if preserved else 'NO':<10}")
    
    if total_compared > 0:
        percent = (preserved_count / total_compared) * 100
        print(f"\nPreservation rate: {preserved_count}/{total_compared} ({percent:.1f}%)")
    
    # 4. Visualize both original and simplified geometries with self-intersections
    visualize_comparison(original_gdf, simplified_results)

def visualize_comparison(original_gdf, simplified_results):
    """Visualize original and simplified geometries side by side for comparison"""
    
    # Get the features that have self-intersections in original data
    intersecting_features = []
    
    for idx, row in original_gdf.iterrows():
        feature_id = row['feature_id']
        if not row.geometry.is_simple:
            intersecting_features.append(feature_id)
    
    if not intersecting_features:
        print("No self-intersecting features to visualize")
        return
    
    # Create figure for visualization
    fig, axes = plt.subplots(len(intersecting_features), 2, figsize=(20, 5*len(intersecting_features)))
    if len(intersecting_features) == 1:
        axes = [axes]  # Make 2D even with single feature
    
    # Plot each self-intersecting feature
    for i, feature_id in enumerate(intersecting_features):
        # Find original geometry
        orig_row = original_gdf[original_gdf['feature_id'] == feature_id].iloc[0]
        
        # Plot original
        ax0 = axes[i][0]
        if orig_row.geometry.geom_type == 'MultiPolygon':
            for polygon in orig_row.geometry.geoms:
                x, y = polygon.exterior.xy
                ax0.plot(x, y, 'r-', linewidth=1.5)
                ax0.fill(x, y, alpha=0.1, fc='red', ec='none')
        else:
            x, y = orig_row.geometry.exterior.xy
            ax0.plot(x, y, 'r-', linewidth=1.5)
            ax0.fill(x, y, alpha=0.1, fc='red', ec='none')
        
        ax0.set_title(f"Original Feature {feature_id}")
        ax0.grid(True)
        
        # Load the simplified feature
        try:
            with open(f'Json/simplified_feature_{feature_id}.json', 'r') as f:
                simp_feature = json.load(f)
            
            simp_geom = shape(simp_feature['geometry'])
            
            # Plot simplified
            ax1 = axes[i][1]
            if simp_geom.geom_type == 'MultiPolygon':
                for polygon in simp_geom.geoms:
                    x, y = polygon.exterior.xy
                    ax1.plot(x, y, 'b-', linewidth=1.5)
                    ax1.fill(x, y, alpha=0.1, fc='blue', ec='none')
            else:
                x, y = simp_geom.exterior.xy
                ax1.plot(x, y, 'b-', linewidth=1.5)
                ax1.fill(x, y, alpha=0.1, fc='blue', ec='none')
            
            # Indicate if self-intersection was preserved
            preserved = not simp_geom.is_simple
            status = "Preserved" if preserved else "LOST"
            ax1.set_title(f"Simplified Feature {feature_id} - Self-Intersection {status}")
            ax1.grid(True)
            
        except Exception as e:
            print(f"Error plotting simplified feature {feature_id}: {e}")
            axes[i][1].text(0.5, 0.5, f"Error: {str(e)}", ha='center', va='center')
            axes[i][1].set_title(f"Simplified Feature {feature_id} - Error")
    
    plt.tight_layout()
    plt.savefig('simplified_comparison.png')
    print("Visualization saved as 'simplified_comparison.png'")

if __name__ == "__main__":
    validate_simplified_features() 