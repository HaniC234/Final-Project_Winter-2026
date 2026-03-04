README.md
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

  derived-data/       # Filtered data and output plots
    income_clean.csv      # Clean Income data -- Socio Index
    renter_clean.csv      # Clean Renter data -- Socio Index
    housing_age_clean.csv     # Clean Housing age data -- Socio Index
    home_value_clean.csv      # Clean Home value data -- Socio Index
    combined.geojson      # Combined data od both indexes

code/
  preprocessing.py    # Proprocessing data for both indexs
```

## Usage

1. Run preprocessing to filter data:
   ```bash
   python code/preprocessing.py
   ```

2. Generate the fire perimeter plot:
   ```bash
   python code/plot_fires.py
   ```
