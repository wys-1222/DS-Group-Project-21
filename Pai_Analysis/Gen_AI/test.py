import requests
import json
import os
import time
import shutil
import re

# Create directory if it doesn't exist
def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

# Clean up previous outputs
for directory in ["Json", "Logs", "Model_Output", "Summary"]:
    if os.path.exists(directory):
        shutil.rmtree(directory)
    ensure_dir(directory)

# API key for OpenRouter
api_key = "[Insert API key here]"

# Load the subset data with self-intersection
subset_file = 'subset_with_error.json'
with open(subset_file, 'r') as f:
    geospatial_data = json.load(f)

# Extract all feature IDs for reference
feature_ids = [feature.get('id', str(i)) for i, feature in enumerate(geospatial_data['features'])]
print(f"Loaded {len(feature_ids)} features with IDs: {', '.join(feature_ids)}...")

# Function to simplify features to reduce token count
def simplify_feature(feature):
    """
    Simplify a GeoJSON feature to reduce token count while preserving 
    important characteristics like self-intersections.
    """
    simplified_feature = {
        "type": "Feature",
        "id": feature.get('id', None),
        "properties": {
            "fclass": feature.get('properties', {}).get('fclass', None)
        },
        "geometry": {
            "type": feature['geometry']['type'],
            "coordinates": []
        }
    }
    
    # Handle different geometry types
    if feature['geometry']['type'] == 'MultiPolygon':
        simplified_polygons = []
        
        for polygon in feature['geometry']['coordinates']:
            simplified_polygon = []
            
            for ring in polygon:
                # Keep a reasonable stride of points to preserve topology
                # We sample points from the full ring to ensure any self-intersections are preserved
                stride = max(1, len(ring) // 15)  # Ensure stride is at least 1
                simplified_ring = [ring[i] for i in range(0, len(ring), stride)]
                
                # Ensure we have the first/last point to close the ring
                if ring[0] != simplified_ring[-1]:
                    simplified_ring.append(ring[0])
                    
                simplified_polygon.append(simplified_ring)
            
            simplified_polygons.append(simplified_polygon)
            
        simplified_feature['geometry']['coordinates'] = simplified_polygons
    
    # Other geometry types would be handled here if needed
    
    return simplified_feature

# Helper function to detect if the response indicates "Yes" for an issue
def has_issue(response, issue_type):
    """
    Check if the response contains a "Yes" answer for the specified issue type,
    handling different capitalizations and formatting.
    """
    # Pattern to match various forms of "Yes" including with asterisks, different capitalization
    pattern = f"{issue_type}:.*?(yes|YES|Yes|\\*\\*Yes\\*\\*|\\*\\*YES\\*\\*)"
    return bool(re.search(pattern, response, re.IGNORECASE))

# Save the full dataset for reference
with open('Json/full_dataset.json', 'w') as f:
    json.dump(geospatial_data, f)
print(f"Saved full dataset to Json/full_dataset.json")

# Models to test
models = [
    "qwen/qwen3-14b:free",
    "microsoft/phi-4-reasoning-plus:free",
    "mistralai/mistral-7b-instruct:free",
    "qwen/qwen3-32b:free",
    "meta-llama/llama-3.3-8b-instruct:free",
    "opengvlab/internvl3-14b:free",
    # "qwen/qwen3-235b-a22b:free",
    "nousresearch/deephermes-3-mistral-24b-preview:free",
]

# System prompt for all models
system_prompt = """
You are a geospatial data expert analyzing GeoJSON features for topological issues.

Specifically evaluate ONLY the following categories:
1. Self-intersections: When a polygon boundary crosses over itself, creating an invalid geometry
2. Invalid geometries: Unclosed rings, duplicate vertices, or other issues that make a geometry invalid
3. Ring orientation issues: Outer ring not counterclockwise or inner ring not clockwise
4. Precision/coordinate issues: Extreme coordinate values or excessive precision

When checking for self-intersections, carefully trace all polygon boundaries to identify any points where the boundary crosses itself. This often appears like a bowtie or figure-8 shape when visualized. 

Self-intersections are a common issue where a line crosses over itself, and they can be detected by:
- Analyzing the coordinate sequence for points where a boundary segment crosses another segment
- Looking for unusual patterns in the coordinates that create crossing paths
- Examining areas where the polygon appears to fold or cross over itself

Provide a clear assessment using ONLY these specific headings, and indicate YES/NO for each issue:

FEATURE [ID]:
Self-intersections: [Yes/No]
Invalid geometries: [Yes/No]
Ring orientation issues: [Yes/No]
Precision/coordinate issues: [Yes/No]

Then provide a brief explanation of your findings, focusing on any issues detected.
"""

# Results for each model
model_results = {}
valid_responses = {}

# Process each model
for model in models:
    print("\n" + "=" * 30)
    print(f"Processing with model: {model}")
    print("=" * 30 + "\n")
    
    model_results[model] = {}
    valid_count = 0
    
    # Process only the first 3 features to limit API usage
    for i, feature_id in enumerate(feature_ids[:3]):
        # Get the feature
        feature = next((f for f in geospatial_data['features'] if f.get('id') == feature_id), None)
        if not feature:
            continue
        
        print(f"Processing feature ID: {feature_id} with {model}")
        
        # Simplify the feature to reduce token count
        simplified_feature = simplify_feature(feature)
        
        # Save the simplified feature for reference
        simplified_file = f"Json/simplified_feature_{feature_id}.json"
        with open(simplified_file, 'w') as f:
            json.dump(simplified_feature, f, indent=2)
        print(f"Saved simplified feature to {simplified_file}")
        
        # Create the user prompt
        user_prompt = f"""
        Analyze this GeoJSON feature for topological issues. Pay special attention to self-intersections where the polygon boundary crosses over itself.

        ```
        {json.dumps(simplified_feature)}
        ```
        
        Focus on identifying self-intersections (boundary crosses itself), invalid geometries, ring orientation issues, and precision/coordinate problems.
        """
        
        # Prepare the API request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        
        # Send the API request
        print(f"Sending request to {model} for feature {feature_id}...")
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            print(f"Response status code: {response.status_code}")
            
            # Save the raw API response for debugging
            log_file = f"Logs/{model.replace('/', '_')}_{feature_id}_response.json"
            with open(log_file, 'w') as f:
                f.write(response.text)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    model_response = result['choices'][0]['message']['content'].strip()
                    
                    # Check if the response is too short (could be an error or limitation)
                    if len(model_response) < 10:  # Arbitrary threshold
                        print(f"Warning: Received empty or very short response from {model}")
                        model_results[model][feature_id] = f"FEATURE {feature_id}:\nNo valid response received from model."
                    else:
                        model_results[model][feature_id] = model_response
                        valid_count += 1
                except Exception as e:
                    print(f"Error parsing response: {e}")
                    model_results[model][feature_id] = f"FEATURE {feature_id}:\nError parsing model response: {str(e)}"
            else:
                print("\n=== ERROR ===")
                print(f"Status code: {response.status_code}")
                print(response.text)
                print("    ", end="")
                model_results[model][feature_id] = f"FEATURE {feature_id}:\nAPI Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            print(f"Request error: {e}")
            model_results[model][feature_id] = f"FEATURE {feature_id}:\nRequest error: {str(e)}"
        
        # Print feature analysis
        print(f"\n=== ANALYSIS FOR FEATURE {feature_id} ===")
        print(f" {model_results[model][feature_id]}")
        
        # Wait between requests to avoid rate limiting
        if i < len(feature_ids[:3]) - 1:  # Don't wait after the last request
            print(f"Waiting 2 seconds before processing next feature...")
            time.sleep(2)
    
    # Track models with valid responses
    valid_responses[model] = valid_count
    
    if valid_count > 0:
        print(f"Model {model} produced {valid_count} valid responses out of {len(feature_ids[:3])} features")
    else:
        print(f"Model {model} did not produce any valid responses")
    
    # Save individual model results immediately after processing
    model_name = model.replace('/', '_')
    
    # Save individual model results
    output_file = f"Model_Output/{model_name}_analysis.txt"
    with open(output_file, 'w') as f:
        f.write(f"ANALYSIS RESULTS FOR {model}\n")
        f.write("=" * 50 + "\n\n")
        
        for feature_id in feature_ids[:3]:
            if feature_id in model_results[model]:
                f.write(f"FEATURE {feature_id}:\n")
                f.write(model_results[model][feature_id] + "\n\n")
    
    print(f"\nResults for {model} saved to {output_file}")
    
    # Create a summary for this model
    summary_file = f"Summary/{model_name}_summary.txt"
    with open(summary_file, 'w') as f:
        f.write(f"SUMMARY FOR {model}\n")
        f.write("=" * 50 + "\n\n")
        
        # If the model produced valid responses
        if valid_responses[model] > 0:
            detected_issues = []
            
            for feature_id in feature_ids[:3]:
                if feature_id in model_results[model]:
                    response = model_results[model][feature_id]
                    
                    # Check for issue detection using the helper function
                    if has_issue(response, "Self-intersections"):
                        detected_issues.append(f"Feature {feature_id}: Self-intersection detected")
                    if has_issue(response, "Invalid geometries"):
                        detected_issues.append(f"Feature {feature_id}: Invalid geometry detected")
                    if has_issue(response, "Ring orientation issues"):
                        detected_issues.append(f"Feature {feature_id}: Ring orientation issue detected")
                    if has_issue(response, "Precision/coordinate issues"):
                        detected_issues.append(f"Feature {feature_id}: Precision/coordinate issue detected")
            
            if detected_issues:
                f.write("Issues detected:\n")
                for issue in detected_issues:
                    f.write(f"- {issue}\n")
            else:
                f.write("No issues detected in any features.\n")
            
            f.write(f"\nModel produced {valid_responses[model]} valid responses out of {len(feature_ids[:3])} features.")
        else:
            f.write("Model did not produce any valid responses.")
    
    print(f"Summary for {model} saved to {summary_file}")
    
    # Wait between models to avoid rate limiting
    if model != models[-1]:  # Don't wait after the last model
        print(f"Waiting 5 seconds before trying next model...")
        time.sleep(5)

# Save debug logs
print("Debug logs saved to Logs/ directory")

# Create a combined comparison summary at the end
comparison_file = "Summary/combined_model_comparison.txt"
with open(comparison_file, 'w') as f:
    f.write("COMBINED SUMMARY OF TOPOLOGICAL ANALYSES\n")
    f.write("=" * 50 + "\n\n")
    
    f.write("Feature Analysis by Model:\n")
    f.write("-" * 30 + "\n\n")
    
    for feature_id in feature_ids[:3]:
        f.write(f"FEATURE {feature_id}:\n")
        f.write("-" * 20 + "\n")
        
        for model in models:
            if valid_responses[model] > 0 and feature_id in model_results[model]:
                model_response = model_results[model][feature_id]
                
                # Extract the key issues using the helper function
                si_detected = has_issue(model_response, "Self-intersections")
                geom_detected = has_issue(model_response, "Invalid geometries")
                ring_detected = has_issue(model_response, "Ring orientation issues")
                prec_detected = has_issue(model_response, "Precision/coordinate issues")
                
                issues = []
                if si_detected:
                    issues.append("Self-intersection")
                if geom_detected:
                    issues.append("Invalid geometry")
                if ring_detected:
                    issues.append("Ring orientation issue")
                if prec_detected:
                    issues.append("Precision/coordinate issue")
                
                if issues:
                    issues_str = ", ".join(issues)
                    f.write(f"{model}: Detected issues: {issues_str}\n")
                else:
                    f.write(f"{model}: No issues detected\n")
            else:
                f.write(f"{model}: No valid response\n")
        
        f.write("\n")
    
    f.write("\nModel Performance Summary:\n")
    f.write("-" * 30 + "\n\n")
    
    for model in models:
        valid_count = valid_responses[model]
        if valid_count > 0:
            detected_counts = {'si': 0, 'geom': 0, 'ring': 0, 'prec': 0}
            
            for feature_id in feature_ids[:3]:
                if feature_id in model_results[model]:
                    response = model_results[model][feature_id]
                    
                    # Use helper function for consistent issue detection
                    if has_issue(response, "Self-intersections"):
                        detected_counts['si'] += 1
                    if has_issue(response, "Invalid geometries"):
                        detected_counts['geom'] += 1
                    if has_issue(response, "Ring orientation issues"):
                        detected_counts['ring'] += 1
                    if has_issue(response, "Precision/coordinate issues"):
                        detected_counts['prec'] += 1
            
            total_issues = sum(detected_counts.values())
            
            f.write(f"{model}:\n")
            f.write(f"- Valid responses: {valid_count}/{len(feature_ids[:3])}\n")
            f.write(f"- Total issues detected: {total_issues}\n")
            f.write(f"  - Self-intersections: {detected_counts['si']}\n")
            f.write(f"  - Invalid geometries: {detected_counts['geom']}\n")
            f.write(f"  - Ring orientation: {detected_counts['ring']}\n")
            f.write(f"  - Precision/coordinate: {detected_counts['prec']}\n\n")
        else:
            f.write(f"{model}: No valid responses\n\n")

print(f"\nCombined model comparison saved to {comparison_file}")
print("\nAnalysis complete!")