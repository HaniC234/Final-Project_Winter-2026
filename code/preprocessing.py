# preprocessing

import pandas as pd
from pathlib import Path
import os
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt

print("CWD =", os.getcwd())

DATA_DIR = Path("data/raw")

income = pd.read_csv(DATA_DIR / "income_24.csv")
renter = pd.read_csv(DATA_DIR / "renter_24.csv")
housing_age = pd.read_csv(DATA_DIR / "housing_age_24.csv")
home_value = pd.read_csv(DATA_DIR / "home_value_24.csv")

##### cleaning the geo id
def clean_geoid(df):
    possible_cols = ['GEO_ID', 'geo_id', 'index']
    
    for col in possible_cols:
        if col in df.columns:
            df['GEOID'] = df[col].astype(str)
            break

    # remove '1400000US'
    df['GEOID'] = df['GEOID'].str.replace('1400000US', '', regex=False)
    df['GEOID'] = df['GEOID'].str.zfill(11)

    return df

income = clean_geoid(income)
renter = clean_geoid(renter)
housing_age = clean_geoid(housing_age)
home_value = clean_geoid(home_value)

### income
income.head()
income['median_income'].dtype
income['median_income'] = pd.to_numeric(income['median_income'], errors='coerce')

income = income.dropna(subset = 'median_income')
income = income.rename(columns = {'B19013_001E': 'median_income'})
income = income[['GEOID', 'NAME', 'median_income']]

income['median_income'].describe()
income.head()

### renter share
renter.head()
renter = renter.rename(columns={
    'B25003_001E': 'total_units',
    'B25003_003E': 'renter_units'
})
print(renter[['total_units','renter_units']].dtypes)
renter['total_units'] = pd.to_numeric(renter['total_units'], errors='coerce')
renter['renter_units'] = pd.to_numeric(renter['renter_units'], errors='coerce')
print(renter[['total_units','renter_units']].dtypes)

renter = renter.dropna(subset=['total_units', 'renter_units'])
renter = renter[renter['total_units'] > 0]
renter['renter_share'] = renter['renter_units'] / renter['total_units']
renter = renter[['GEOID', 'NAME', 'total_units', 'renter_units', 'renter_share']]

print(renter['renter_share'].describe())
renter.head()

### housing age
for col in housing_age.columns:
    if col not in ['GEOID', 'NAME'] and housing_age[col].dtype == 'object':
        housing_age[col] = pd.to_numeric(
            housing_age[col].astype(str)
                             .str.replace(',', '', regex=False)
                             .str.strip(),
            errors='coerce'
        )
housing_age.head()

housing_age = housing_age.rename(columns={
    'B25034_001E': 'total_units',
    'B25034_008E': 'built_1960_69',
    'B25034_009E': 'built_1950_59',
    'B25034_010E': 'built_1940_49',
    'B25034_011E': 'built_1939_before'
})

housing_age['old_units'] = (
    housing_age['built_1960_69'] +
    housing_age['built_1950_59'] +
    housing_age['built_1940_49'] +
    housing_age['built_1939_before']
)
housing_age = housing_age.dropna(subset = 'old_units')

housing_age = housing_age[housing_age['total_units'] > 0]
housing_age['old_housing_share'] = (housing_age['old_units'] / housing_age['total_units'])

housing_age = housing_age[['GEOID', 'NAME', 'total_units', 'old_units', 'old_housing_share']]
print(housing_age['old_housing_share'].describe())
housing_age.head()

### home value
home_value.head()
home_value = home_value.rename(columns = {'B25077_001E': 'median_home_value'})

home_value['median_home_value'] = pd.to_numeric(home_value['median_home_value'], errors='coerce')
home_value = home_value.dropna(subset = 'median_home_value')

home_value = home_value[['GEOID', 'NAME', 'median_home_value']]
print(home_value['median_home_value'].describe())
home_value.head()

income.to_csv('income_clean.csv', index=False)
renter.to_csv('renter_clean.csv', index=False)
housing_age.to_csv('housing_age_clean.csv', index=False)
home_value.to_csv('home_value_clean.csv', index=False)











