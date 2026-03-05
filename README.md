# Chicago Environmental Justice Analysis

This project processes and visualizes socioeconomic vulnerability and environmental exposure data across Chicago census tracts.

## Setup

```bash
conda env create -f environment.yml
conda activate chicago_ej
```

## Project Structure

```
data/
  raw-data/           # Raw data files
    income_24.csv      # Income data -- Socio Index
    renter_24.csv      # Renter data -- Socio Index
    housing_age_24.csv     # Housing age data -- Socio Index
    home_value_24.csv      # Home value data -- Socio Index
    Boundaries_Chicago.geojson    # Boundary tract data of Chicago
    tl_2023/17_tract/      # Shape file for clipping
      tl_2023_17_tract.cpg
      tl_2023_17_tract.dbf
      tl_2023_17_tract.prj
      tl_2023_17_tract.shp
      tl_2023_17_tract.shx
      tl_2023_17_tract.shp.ea.iso.xml
      tl_2023_17_tract.shp.iso.xml
    Boundaries_-_Community_Areas_20260228.geojson  # Chicago community areas
    chicago_impervious.tif         # Impervious surface raster
    chicago_summer_LST.tif         # Summer land surface temperature raster
    chicago_winter_LST.tif         # Winter land surface temperature raster
    chicago_summer_NDVI.tif        # NDVI vegetation index raster
    EPA_TRI_IL_2022.csv            # EPA Toxic Release Inventory data
    tl_2022_17_prisecroads.*       # Census TIGER road shapefile
    tl_2022_17_tract.*             # Census tract shapefile

  derived-data/       # Filtered data and output plots
    income_clean.csv      # Clean Income data -- Socio Index
    renter_clean.csv      # Clean Renter data -- Socio Index
    housing_age_clean.csv     # Clean Housing age data -- Socio Index
    home_value_clean.csv      # Clean Home value data -- Socio Index
    combined.geojson      # Combined data of both indexes
    env_tracts_chicago_2022.gpkg   # Cleaned Chicago census tract boundaries
    env_roads_chicago_2022.gpkg    # Chicago road network
    env_tri_chicago_2022.gpkg      # TRI facilities filtered to Chicago

    env_lst_summer_3435_clip.tif   # Summer LST clipped to Chicago
    env_lst_winter_3435_clip.tif   # Winter LST clipped to Chicago
    env_ndvi_summer_3435_clip.tif  # NDVI clipped to Chicago
    env_impervious_3435_clip.tif   # Impervious surface clipped to Chicago

    env_metrics_tracts.gpkg        # Environmental indicators aggregated to census tracts
    env_metrics_tracts.csv         # Same dataset in CSV format

    env_exposure_final.gpkg        # Final environmental exposure index by tract
    env_exposure_final.csv         # Final index dataset in CSV format


code/
  preprocessing.py    # Proprocessing data for both indexes
```

## Usage

1. Run final_project.qmd file since it contains everything including preprocessing:
   ```bash
   python final_project.qmd
   ```

2. Run app.py for the dashboard:
   ```bash
   python /streamlit-app final_project.qmd
   ```
