"""Heuristic offline fallbacks for SoilGrids data in India.

Provides typical soil properties based on the state or broad agro-ecological zone
when live satellite/gridded sensor readings (SoilGrids) fail or time out.
This prevents the system from returning a single hardcoded (e.g. Clay) profile
for all of India.
"""

from typing import Any

# Representative soil profiles by state/region
# Values approximate (sand, silt, clay add up to ~100)
# 'soc' is Soil Organic Carbon in dg/kg (e.g. 50 = 5 g/kg = 0.5%)
# 'phh2o' is pH x 10 (e.g. 75 = 7.5)
# 'nitrogen' in cg/kg (e.g. 1000 = 10 g/kg)
# 'cec' in mmol(c)/kg (e.g. 150 = 15 cmol/kg)
# 'bdod' is Bulk Density x 100 (e.g. 140 = 1.4 kg/dm3)
# 'cfvo' is coarse fragments volumetric % x 10 (e.g. 50 = 5%)
_REGIONS = {
    # Arid / Desert Soils (Sandy)
    "Rajasthan": {
        "sand": 850, "silt": 100, "clay": 50, "phh2o": 82, "soc": 20, 
        "nitrogen": 400, "cec": 50, "bdod": 155, "cfvo": 20, "wrb": "Arenosols"
    },
    
    # Black Cotton Soils (Vertisols - Clay)
    "Maharashtra": {
        "sand": 200, "silt": 250, "clay": 550, "phh2o": 78, "soc": 80, 
        "nitrogen": 800, "cec": 350, "bdod": 130, "cfvo": 50, "wrb": "Vertisols"
    },
    "Gujarat": {
        "sand": 250, "silt": 250, "clay": 500, "phh2o": 76, "soc": 70, 
        "nitrogen": 700, "cec": 300, "bdod": 135, "cfvo": 40, "wrb": "Vertisols"
    },
    "Madhya Pradesh": {
        "sand": 250, "silt": 300, "clay": 450, "phh2o": 74, "soc": 90, 
        "nitrogen": 800, "cec": 320, "bdod": 135, "cfvo": 60, "wrb": "Vertisols"
    },

    # Indo-Gangetic Alluvial Soils (Loam / Silt Loam)
    "Punjab": {
        "sand": 400, "silt": 400, "clay": 200, "phh2o": 72, "soc": 60, 
        "nitrogen": 900, "cec": 120, "bdod": 140, "cfvo": 10, "wrb": "Fluvisols"
    },
    "Haryana": {
        "sand": 450, "silt": 350, "clay": 200, "phh2o": 74, "soc": 50, 
        "nitrogen": 800, "cec": 110, "bdod": 145, "cfvo": 10, "wrb": "Fluvisols"
    },
    "Uttar Pradesh": {
        "sand": 350, "silt": 450, "clay": 200, "phh2o": 70, "soc": 70, 
        "nitrogen": 900, "cec": 150, "bdod": 140, "cfvo": 10, "wrb": "Fluvisols"
    },
    "Bihar": {
        "sand": 300, "silt": 500, "clay": 200, "phh2o": 68, "soc": 80, 
        "nitrogen": 950, "cec": 160, "bdod": 135, "cfvo": 10, "wrb": "Fluvisols"
    },
    "West Bengal": {
        "sand": 250, "silt": 500, "clay": 250, "phh2o": 65, "soc": 90, 
        "nitrogen": 1000, "cec": 180, "bdod": 130, "cfvo": 20, "wrb": "Gleysols"
    },

    # Laterite / Acidic Soils (Sandy Clay Loam / High Coarse Fragments)
    "Kerala": {
        "sand": 600, "silt": 150, "clay": 250, "phh2o": 55, "soc": 150, 
        "nitrogen": 1200, "cec": 80, "bdod": 125, "cfvo": 150, "wrb": "Ferralsols"
    },
    "Goa": {
        "sand": 550, "silt": 200, "clay": 250, "phh2o": 58, "soc": 140, 
        "nitrogen": 1100, "cec": 90, "bdod": 130, "cfvo": 120, "wrb": "Ferralsols"
    },
    
    # Default (Sandy Loam - generic intermediate profile)
    "Default": {
        "sand": 600, "silt": 200, "clay": 200, "phh2o": 68, "soc": 60, 
        "nitrogen": 700, "cec": 100, "bdod": 140, "cfvo": 40, "wrb": "Luvisols"
    }
}

def get_regional_fallback(state: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Returns a synthetic SoilGrids properties and classification payload for the region.
    
    Data is formatted to mimic the structure returned by SoilGrids REST API,
    so it can be passed transparently into `normalise_properties`.
    """
    region_data = _REGIONS.get(state) if state else None
    if not region_data:
        region_data = _REGIONS["Default"]

    properties_payload = {
        "properties": {
            "layers": []
        }
    }
    
    # Map the scalar values back to a SoilGrids-like depth layer structure (0-5, 5-15, 15-30)
    for prop in ["sand", "silt", "clay", "phh2o", "soc", "nitrogen", "cec", "bdod", "cfvo"]:
        properties_payload["properties"]["layers"].append({
            "name": prop,
            "unit_measure": {"d_factor": 10 if prop not in ["nitrogen", "bdod"] else 100},
            "depths": [
                {"label": "0-5cm", "values": {"mean": region_data[prop], "uncertainty": 0}},
                {"label": "5-15cm", "values": {"mean": region_data[prop], "uncertainty": 0}},
                {"label": "15-30cm", "values": {"mean": region_data[prop], "uncertainty": 0}}
            ]
        })
        
    classification_payload = {
        "wrb_class_name": region_data["wrb"],
        "wrb_class_probability": [[region_data["wrb"], 100]]
    }
    
    return properties_payload, classification_payload
