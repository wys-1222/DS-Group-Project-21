import json
import os
import copy
import math

# Load the GeoJSON file
input_file = 'subset_for_ai.json'
output_file = 'subset_with_error.json'

def create_self_intersection(feature, feature_index):
    """Create a self-intersection in a feature's geometry"""
    
    # Make a deep copy of the feature for modification
    modified_feature = copy.deepcopy(feature)
    
    # Check if it's a MultiPolygon
    if feature['geometry']['type'] == 'MultiPolygon':
        # Get the first polygon, first ring
        original_coords = feature['geometry']['coordinates'][0][0]
        modified_coords = modified_feature['geometry']['coordinates'][0][0]
        
        # Calculate key indices for self-intersection
        ring_len = len(original_coords)
        stride = max(1, ring_len // 15)  # Ensure stride is at least 1
        
        print(f"Feature {feature.get('id', 'unknown')} coordinates length: {ring_len}")
        print(f"Simplification stride: {stride}")
        
        # Create more pronounced self-intersections by swapping strategically placed points
        if ring_len >= 15:  # Only if we have enough points
            # For Feature 0: Create an X-shaped self-intersection
            if feature_index == 0:
                # Take points at specific indices to ensure they remain after simplification
                swap_index1 = stride * 3  # Near the beginning
                swap_index2 = stride * 10 # Near the end
                
                print(f"Creating self-intersection by swapping points at indices {swap_index1} and {swap_index2}")
                
                # Swap the points to create a crossing
                temp = modified_coords[swap_index1]
                modified_coords[swap_index1] = modified_coords[swap_index2]
                modified_coords[swap_index2] = temp
                
            # For Feature 1: Create a pinched polygon by moving a mid-point inside
            elif feature_index == 1:
                mid_index = len(original_coords) // 2
                far_index = len(original_coords) // 4
                
                # Calculate vector between two points
                vec_x = original_coords[mid_index][0] - original_coords[far_index][0]
                vec_y = original_coords[mid_index][1] - original_coords[far_index][1]
                
                # Normalize and scale vector to create a significant displacement
                magnitude = math.sqrt(vec_x**2 + vec_y**2)
                scale = magnitude * 0.8  # Scale to create a pronounced crossing
                
                # Create a new point that's guaranteed to cross the polygon boundary
                new_x = original_coords[mid_index][0] + (vec_x / magnitude) * scale
                new_y = original_coords[mid_index][1] + (vec_y / magnitude) * scale
                
                print(f"Creating self-intersection by moving point at index {mid_index}")
                modified_coords[mid_index] = [new_x, new_y]
                
            # For Feature 2: Create a loop that crosses itself
            elif feature_index == 2:
                # Choose points about a third of the way through
                index1 = stride * 5
                index2 = stride * 8
                
                # Move two points to create a loop that crosses over itself
                temp = modified_coords[index1]
                modified_coords[index1] = modified_coords[index2]
                modified_coords[index2] = temp
                
                print(f"Creating self-intersection loop using indices {index1} and {index2}")
        else:
            print(f"Feature has too few points ({ring_len}) to create a reliable self-intersection")
            return None  # Skip this feature
        
        print(f"Created self-intersection in feature ID: {feature.get('id', 'unknown')}")
        return modified_feature
    else:
        print(f"Feature {feature_index} is not a MultiPolygon, it's a {feature['geometry']['type']}")
        return None  # Skip this feature

# Main code execution
with open(input_file, 'r') as f:
    data = json.load(f)

# Make sure we have features
if 'features' in data and len(data['features']) > 0:
    # Make a deep copy of the original data
    modified_data = copy.deepcopy(data)
    
    # Count of successful modifications
    modified_count = 0
    
    # Process the first 3 features (or fewer if less are available)
    features_to_process = min(3, len(data['features']))
    
    for i in range(features_to_process):
        # Get the feature
        feature = data['features'][i]
        
        print(f"\nProcessing feature {i+1}/{features_to_process}: ID {feature.get('id', 'unknown')}")
        
        # Create a self-intersection
        modified_feature = create_self_intersection(feature, i)
        
        # If modification was successful, update the feature in our modified data
        if modified_feature:
            modified_data['features'][i] = modified_feature
            modified_count += 1
    
    # Save modified GeoJSON to a new file
    with open(output_file, 'w') as f:
        json.dump(modified_data, f)
    
    print(f"\nModified {modified_count} features with self-intersections")
    print(f"Modified GeoJSON saved to {output_file}")
else:
    print("No features found in the GeoJSON file") 