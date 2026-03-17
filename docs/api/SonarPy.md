# SonarPy

A Python Class for processing and analyzing sonar data.

---

## Parameters

| Name            | Type                          | Description                                                                 |
|-----------------|-------------------------------|-----------------------------------------------------------------------------|
| `surveyxyz`     | `tuple` or `None`             | The (x, y, z) coordinates of the survey datum in the input CRS.             |
| `surveyxyzWGS84`| `tuple` or `None`             | The (lat, lon, elevation) of the survey datum in WGS84.                     |
| `year`          | `int`, default=`2024`         | Year of the survey.                                                         |
| `metric`        | `bool`, default=`False`       | Whether units are in meters (True) or feet (False).                         |
| `crs`           | `str` or `pyproj.CRS`         | Input coordinate reference system.                                          |
| `utm_shp_path`  | `str` or `None`, optional     | Path to the UTM zone shapefile. Defaults to a world UTM grid if not set.    |

---

## Attributes

| Name             | Type                          | Description                                                                |
|------------------|-------------------------------|----------------------------------------------------------------------------|
| `crs`            | `str` or `pyproj.CRS`         | Output coordinate reference system.                                        |
| `metric`         | `bool`                        | True for meters, False for feet.                                           |
| `utm_shp_path`   | `str`                         | Path to the UTM shapefile.                                                 |
| `utmzones`       | `geopandas.GeoDataFrame`      | UTM zone polygons.                                                         |
| `zonecrs`        | `str`                         | EPSG code of the correct UTM zone.                                         |
| `magdec`         | `float`                       | Magnetic declination in degrees.                                           |
| `surveyxyz`      | `tuple`                       | Survey point in original CRS.                                              |
| `pntgdf`         | `geopandas.GeoDataFrame`      | Survey point as GeoDataFrame.                                              |
| `pntgdfUTM`      | `geopandas.GeoDataFrame`      | Survey point reprojected to UTM.                                           |
| `surveyxyzUTM`   | `tuple`                       | Survey datum in UTM coordinates.                                           |
| `xyz_gdf`        | `geopandas.GeoDataFrame`      | 3D point cloud in UTM.                                                     |
| `xyz_gdfCRS`     | `geopandas.GeoDataFrame`      | 3D point cloud in final user-specified CRS.                                |

---

## Setup

To calculate magnetic declination, download the IGRF13 coefficient file from:

> https://www.ngdc.noaa.gov/IAGA/vmod/coeffs/igrf13coeffs.txt

Place it here:
```text
C:/ProgramData/anaconda3/envs/<yourenv>/lib/site-packages/pyCRGI/data/igrf13coeffs.txt
```

---

## Methods

### `build_horizontal_shots(data, sort_by='cAzi')`

Builds a 3D STL-style mesh from sonar scan layers.

> **Note:** Assumes consistent ring-like ordering between layers for valid surface stitching. Each layer must represent a distinct scan ring.

**Parameters:**

- `data` (`GeoDataFrame` or list of `GeoDataFrame`): Input sonar layer(s), each with x, y, z, and a `sort_by` column.
- `sort_by` (str, default `'cAzi'`): Field to sort points within each layer.

**Returns:**

- `vertices` (`np.ndarray`): Combined point coordinates (N x 3).
- `faces` (list of lists): Triangle faces in `[3, i1, i2, i3]` format.

---

### `build_endcap(layer_df)`

Builds a 3D mesh for a single sonar scan layer using 2D Delaunay triangulation in (x, y).

**Parameters:**

- `layer_df` (`pandas.DataFrame` or `GeoDataFrame`): Must contain columns `x`, `y`, and `z`.

**Returns:**

- `vertices` (`ndarray`): 3D coordinates of the mesh vertices.
- `faces` (list of lists): Triangle face indices as index triplets.

---

### `combine_mesh_parts(parts, filename='combined_mesh.stl')`

Combines multiple mesh parts (each with vertices and faces) into a single STL mesh file.

**Parameters:**

- `parts` (list): List of `(vertices, faces)` tuples.
- `filename` (str): Output STL filename (default: `'combined_mesh.stl'`).

---

### `las2txt_path(path)`

Converts all `.laz` files in a directory to ASCII text files using `las2txt64`.

Each output `.txt` file includes:

- X, Y, Z coordinates (columns 1–3)
- Intensity (column 4)
- GPS time (column 5)
- A header row for compatibility with `txt2las64`

**Parameters:**

- `path` (str): Path to the folder containing `.laz` files.s

### `add_headers_toLAStxt`

Add column headers to las2txt output and save as csv.

**Parameters:**

- `path` (str): Path to the folder containing .txt files exported by las2txt64.

---

### `dmv_exported_lwt_to_dfT(path)`

Converts LWT files exported by DimCav Viewer to a `dfT`-formatted DataFrame.

Each row in the DataFrame represents a single sonar shot and includes:

- Depth  
- Range  
- Azimuth (`cAzi`)  
- Tilt

**Parameters:**

- `path` (`str`): Path to the `.LWT` file exported by DimCav Viewer.

**Returns:**

- `dfT` (`pandas.DataFrame`): Reformatted long-form DataFrame.

---

### `get_well_deviation_delta(df, wb)`

Returns the (dx, dy, dz) deviation from a wellbore survey (`wb`) at the correct measured depth or last available depth.

**Parameters:**

- `df` (`pandas.DataFrame`): DataFrame containing the sonar data.
- `wb` (`pandas.DataFrame`): Wellbore survey data with columns:
      - `MDepth`
      - `dx_ft`
      - `dy_ft`
      - `dz_ft`

**Returns:**

- `tuple`: Delta `(dx, dy, dz)` in feet.

---

### `open_lwt(file)`

Parses American format `.lwt` (CWR export) sonar file into a DataFrame.

**Parameters:**

- `file` (`str`): Path to the `.lwt` sonar file.

**Returns:**

- `df` (`pandas.DataFrame`): DataFrame parsed from the `.lwt` file.

---

### `getMagDev(long, lat, alt=0, year=2024)`

Computes magnetic declination at a given location using [pyCRGI](https://github.com/pleiszenburg/pyCRGI?tab=readme-ov-file).

**Parameters:**

- `long` (`float`): Longitude in decimal degrees.  
- `lat` (`float`): Latitude in decimal degrees.  
- `alt` (`float`, default=`0`): Altitude in kilometers.  
- `year` (`int`, default=`2024`): Year of the survey.

**Returns:**

- `d` (`float`): Magnetic declination (+ve east) in degrees.

---

### `lwt_df_to_dfT(df)`

Converts an unformatted `pandas.DataFrame` to a long-form format with one row per sonar shot.

**Parameters:**

- `df` (`pandas.DataFrame`): Sonar data parsed from an LWT file.

**Returns:**

- `dfT` (`pandas.DataFrame`): Reformatted long-form DataFrame where each row represents a single sonar shot, including attributes such as:
  - Depth  
  - Range  
  - Azimuth (`cAzi`)  
  - Tilt


---

### `read_lwt_dat_export(path)`

Reads a `.dat` export file from CavView II and reformats it into a long-form sonar DataFrame (`dfT`).

Each block of data in the `.dat` file corresponds to a depth level and includes sonar return values recorded at multiple angles.

**Parameters:**

- `path` (str): File path to the `.dat` file exported from CavView II.

**Returns:**

- `dfT` (`pandas.DataFrame`): Reformatted long-form DataFrame where each row represents a single sonar shot. Columns include:
  - `depth`: Depth of the scan
  - `cAzi`: Azimuth angle
  - `r`: Range (distance)
  - `tilt`: Defaulted to 0
  - `vos`: (Velocity of sound) defaulted to NaN


---

### `dfT_to_xyz_delta_points(dfT)`

Converts a `dfT` DataFrame (one row per sonar shot) into delta XYZ coordinates using spherical-to-Cartesian transformation.

**Parameters:**

- `dfT` (`pandas.DataFrame`): Long-form DataFrame with columns for `depth`, `range`, `tilt`, and `cAzi`.

**Returns:**

- `xyz` (`pandas.DataFrame`): DataFrame with calculated delta `dx`, `dy`, and `dz` columns.

**Notes:**

- Converts `tilt` into inclination (`mInc = 90 - tilt`)
- Applies magnetic declination correction
- Uses spherical coordinate conversion:


---

### `utm_epsg_code_at_point(surveyxyz, crs='EPSG:4326')`

Finds the correct WGS 84 UTM EPSG code based on the geographic location of the survey and converts coordinates to UTM.

**Parameters:**

- `surveyxyz` (`tuple`): (x, y, z) coordinates in the input CRS.
- `crs` (`str`, optional): Input coordinate reference system (default: `'EPSG:4326'`).

**Sets Attributes:**

- `self.zonecrs`: EPSG code string of UTM zone  
- `self.pntgdf`: Original point as a GeoDataFrame  
- `self.pntgdfUTM`: Reprojected point in UTM  
- `self.surveyxyzUTM`: Transformed (x, y, z) in UTM coordinates

---

### `generate_gdf(xyz, wb_delta=(0, 0, 0))`

Converts XYZ delta coordinates into full 3D UTM and projected GeoDataFrames.

**Parameters:**

- `xyz` (`pandas.DataFrame`): Must include `dx`, `dy`, `dz`, and `depth`.
- `wb_delta` (`tuple`, optional): Wellbore deviation correction in `(dx, dy, dz)`.

**Returns:**

- `xyz_gdf` (`GeoDataFrame`): 3D point cloud in UTM.
- `xyz_gdfCRS` (`GeoDataFrame`): 3D point cloud reprojected to the specified CRS.

**Notes:**

- Applies feet-to-meter conversion if `self.metric` is False
- Stores both output GeoDataFrames as attributes for reuse

---

### `cAzi2mAzi(a)`

Converts a compass azimuth (0° = North, clockwise) to a math azimuth (0° = East, counter-clockwise).

**Parameters:**

- `a` (`float`): Compass azimuth in degrees

**Returns:**

- `d` (`float`): Math spherical azimuth (0–360°)

---

### `degmmss_to_dec_deg(x)`

Converts a DMS (degrees° minutes' seconds") string to decimal degrees.

**Parameters:**

- `x` (`str`): DMS-formatted string like `93°24'50.61"W`

**Returns:**

- `dd` (`float`): Decimal degree value (negative if S or W)
