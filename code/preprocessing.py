# preprocessing

import pandas as pd
from pathlib import Path
import os
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.mask import mask
from rasterstats import zonal_stats

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



### environmental layer

ENV_RAW_DIR = Path("data/raw-data")
ENV_DERIVED_DIR = Path("data/derived-data")
ENV_DERIVED_DIR.mkdir(parents=True, exist_ok=True)

TARGET_CRS = "EPSG:3435"

TRACTS_PATH  = ENV_RAW_DIR / "tl_2022_17_tract.shp"
CHICAGO_PATH = ENV_RAW_DIR / "Boundaries_Chicago.geojson"
ROADS_PATH   = ENV_RAW_DIR / "tl_2022_17_prisecroads.shp"
TRI_CSV_PATH = ENV_RAW_DIR / "EPA_TRI_IL_2022.csv"

RASTERS = {
    "lst_summer":  ENV_RAW_DIR / "chicago_summer_LST.tif",
    "lst_winter":  ENV_RAW_DIR / "chicago_winter_LST.tif",
    "ndvi_summer": ENV_RAW_DIR / "chicago_summer_NDVI.tif",
    "impervious":  ENV_RAW_DIR / "chicago_impervious.tif",
}

OUT_TRACTS_GPKG = ENV_DERIVED_DIR / "env__tracts_chicago_2022.gpkg"
OUT_ROADS_GPKG  = ENV_DERIVED_DIR / "env__roads_chicago_2022.gpkg"
OUT_TRI_GPKG    = ENV_DERIVED_DIR / "env__tri_chicago_2022.gpkg"

def _drop_empty(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

def _fix_geom(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.make_valid()
    return gdf

def _dissolve_to_single_polygon(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf.dissolve()

def _reproject_and_clip_raster_to_mask(
    src_path: Path,
    dst_path: Path,
    mask_gdf: gpd.GeoDataFrame,
    target_crs: str = TARGET_CRS
) -> None:
    """
    Reproject raster to target CRS, then clip to mask geometry.
    Writes GeoTIFF to dst_path.
    """
    with rasterio.open(src_path) as src:
        if src.crs is None:
            raise ValueError(f"Raster has no CRS: {src_path}")

        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds
        )

        dst_meta = src.meta.copy()
        dst_meta.update({
            "crs": target_crs,
            "transform": transform,
            "width": width,
            "height": height
        })

        tmp_path = ENV_DERIVED_DIR / f"__tmp_reproject_{src_path.stem}.tif"
        with rasterio.open(tmp_path, "w", **dst_meta) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear,
                )

    with rasterio.open(tmp_path) as reproj:
        geoms = list(mask_gdf.geometry)
        out_img, out_transform = mask(reproj, geoms, crop=True)
        out_meta = reproj.meta.copy()
        out_meta.update({
            "height": out_img.shape[1],
            "width": out_img.shape[2],
            "transform": out_transform
        })

    with rasterio.open(dst_path, "w", **out_meta) as out:
        out.write(out_img)

    try:
        tmp_path.unlink()
    except OSError:
        pass

def _add_zonal_mean(gdf: gpd.GeoDataFrame, raster_path: Path, out_col: str) -> gpd.GeoDataFrame:
    zs = zonal_stats(gdf, raster_path, stats=["mean"], all_touched=False)
    gdf[out_col] = [d["mean"] for d in zs]
    return gdf


env_tracts = _fix_geom(_drop_empty(gpd.read_file(TRACTS_PATH)))
env_chicago = _fix_geom(_drop_empty(gpd.read_file(CHICAGO_PATH)))

env_tracts = env_tracts.to_crs(TARGET_CRS)
env_chicago = env_chicago.to_crs(TARGET_CRS)

env_chicago_poly = _dissolve_to_single_polygon(env_chicago)
env_tracts_chicago = gpd.clip(env_tracts, env_chicago_poly)
print("Chicago tracts:", len(env_tracts_chicago))

env_roads = _fix_geom(_drop_empty(gpd.read_file(ROADS_PATH))).to_crs(TARGET_CRS)
env_roads_chicago = gpd.clip(env_roads, env_chicago_poly)
print("Road segments (clipped):", len(env_roads_chicago))

env_tri = pd.read_csv(TRI_CSV_PATH)
env_tri = env_tri.dropna(subset=["12. LATITUDE", "13. LONGITUDE"]).copy()

env_tri_gdf = gpd.GeoDataFrame(
    env_tri,
    geometry=gpd.points_from_xy(env_tri["13. LONGITUDE"], env_tri["12. LATITUDE"]),
    crs="EPSG:4326"
).to_crs(TARGET_CRS)

env_tri_gdf = gpd.clip(env_tri_gdf, env_chicago_poly)
print("TRI points (clipped):", len(env_tri_gdf))

env_tracts_chicago.to_file(OUT_TRACTS_GPKG, layer="tracts", driver="GPKG")
env_roads_chicago.to_file(OUT_ROADS_GPKG, layer="roads", driver="GPKG")
env_tri_gdf.to_file(OUT_TRI_GPKG, layer="tri", driver="GPKG")


for name, path in RASTERS.items():
    out_path = ENV_DERIVED_DIR / f"env__{name}_3435_clip.tif"
    _reproject_and_clip_raster_to_mask(path, out_path, env_chicago_poly, target_crs=TARGET_CRS)

print("Rasters reprojected & clipped to", TARGET_CRS)


env_tracts = gpd.read_file(OUT_TRACTS_GPKG, layer="tracts")
env_roads  = gpd.read_file(OUT_ROADS_GPKG, layer="roads")
env_tri    = gpd.read_file(OUT_TRI_GPKG, layer="tri")

env_tracts = _add_zonal_mean(env_tracts, ENV_DERIVED_DIR / "env__lst_summer_3435_clip.tif", "lst_summer_mean")
env_tracts = _add_zonal_mean(env_tracts, ENV_DERIVED_DIR / "env__lst_winter_3435_clip.tif", "lst_winter_mean")
env_tracts = _add_zonal_mean(env_tracts, ENV_DERIVED_DIR / "env__ndvi_summer_3435_clip.tif", "ndvi_mean")
env_tracts = _add_zonal_mean(env_tracts, ENV_DERIVED_DIR / "env__impervious_3435_clip.tif", "impervious_mean")

env_roads_x = gpd.overlay(
    env_roads[["geometry"]],
    env_tracts[["GEOID", "geometry"]],
    how="intersection"
)
env_roads_x["road_len_ft"] = env_roads_x.geometry.length

env_road_sum = env_roads_x.groupby("GEOID")["road_len_ft"].sum().reset_index()

env_tracts["tract_area_ft2"] = env_tracts.geometry.area
env_tracts = env_tracts.merge(env_road_sum, on="GEOID", how="left")
env_tracts["road_len_ft"] = env_tracts["road_len_ft"].fillna(0)
env_tracts["road_density"] = env_tracts["road_len_ft"] / env_tracts["tract_area_ft2"]

env_tri = env_tri.copy()
env_tri["total_releases"] = pd.to_numeric(env_tri["107. TOTAL RELEASES"], errors="coerce").fillna(0)

env_tri_join = gpd.sjoin(
    env_tri,
    env_tracts[["GEOID", "geometry"]],
    how="inner",
    predicate="within"
)

env_tri_summary = (
    env_tri_join.groupby("GEOID")
    .agg(
        tri_release_total=("total_releases", "sum"),
        tri_facility_count=("2. TRIFD", "nunique")
    )
    .reset_index()
)

env_tracts = env_tracts.merge(env_tri_summary, on="GEOID", how="left")
env_tracts["tri_release_total"] = env_tracts["tri_release_total"].fillna(0)
env_tracts["tri_facility_count"] = env_tracts["tri_facility_count"].fillna(0)

env_tracts.to_file(ENV_DERIVED_DIR / "env__metrics_tracts.gpkg", layer="tracts", driver="GPKG")
env_tracts.drop(columns="geometry").to_csv(ENV_DERIVED_DIR / "env__metrics_tracts.csv", index=False)

print("\n✅ Done. Environmental metrics saved to:")
print(" -", (ENV_DERIVED_DIR / "env__metrics_tracts.gpkg"))
print(" -", (ENV_DERIVED_DIR / "env__metrics_tracts.csv"))









