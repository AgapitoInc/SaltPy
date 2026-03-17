# SonarPlots

A collection of methods for processing, visualizing, and analyzing sonar cavern data.

---

## Methods

### `ckdnearest(gdfA, gdfB, gdfB_cols=['Place'])`

Finds the nearest neighbors between two point cloud GeoDataFrames and returns a `GeoDataFrame` containing the line geometry between each point in `gdfA` and its nearest point in `gdfB`.

This method is useful for estimating **web thickness** or proximity-based relationships in 3D space.

**Parameters:**

- `gdfA` (`geopandas.GeoDataFrame`): Source point cloud.
- `gdfB` (`geopandas.GeoDataFrame`): Target point cloud to find nearest neighbors in.
- `gdfB_cols` (`list`, optional): Columns to include from `gdfB` in the output. Default is `['Place']`.

**Returns:**

- `line` (`geopandas.GeoDataFrame`): A GeoDataFrame containing LineStrings between each point in `gdfA` and its nearest point in `gdfB`.

---

### `addXY2RadiusAziM(gdf)`

Adds radius and azimuth (mathematical and compass) to a DataFrame containing XY or dx/dy coordinates.

**Parameters:**

- `gdf` (`pandas.DataFrame` or `geopandas.GeoDataFrame`): Must contain either `X` and `Y` or `dx` and `dy`.

**Returns:**

- `gdf` (`pandas.DataFrame`): The original DataFrame with added columns:
  - `mAzi`: Mathematical azimuth (0° = x-axis, counter-clockwise)
  - `cAzi`: Compass azimuth (0° = North, clockwise)
  - `radiusXY`: 2D radial distance in XY plane
  - `radiusXYZ`: 3D radius from origin (if z is included)

---

### `cAzi_2from_mAzi(a)`

Converts between compass azimuth and mathematical (spherical) azimuth.

**Parameters:**

- `a` (`float`): Input azimuth in degrees, either mathematical or compass-style.

**Returns:**

- `d` (`float`): Converted azimuth in degrees.

---

### `xyzexterior(gdf, overridebuff=None)`

Creates an exterior polygon from a 3D point cloud.

**Parameters:**

- `gdf` (`geopandas.GeoDataFrame`): 3D point cloud (typically in XYZ format).
- `overridebuff` (`float`, optional): Optional fixed buffer. Use this if the auto-fit is too tight for irregular geometries.

**Returns:**

- `buff` (`shapely.geometry.Polygon`): Exterior polygon encompassing the cloud.

---

### `remove_interiors(poly)`

Removes all interior holes (rings) from a polygon.

**Parameters:**

- `poly` (`shapely.geometry.Polygon`): Input polygon with potential holes.

**Returns:**

- `poly` (`shapely.geometry.Polygon`): Polygon with only the outer shell.

---

### `volume_df_from_stl(polydatamesh, dstep=10, correction=True)`

Computes the cumulative volume profile of a 3D mesh along the vertical (Z) axis.

**Parameters:**

- `polydatamesh` (`pyvista.PolyData`): Input cavern mesh.
- `dstep` (`int`, optional): Depth slice interval along the Z-axis (default: `10`).
- `correction` (`bool`, optional): If `True`, applies a scale factor so that the sum of slice volumes equals the mesh’s actual volume.

**Returns:**

- `df` (`pandas.DataFrame`): A DataFrame of cumulative volume vs. depth (in cubic units).

---

### `old_volume_df_from_stl(polydatamesh, dstep=10)`

Provides a Z-axis volume profile of a cavern in the same cubic units as the mesh (e.g., m³ or ft³).

**Parameters:**

- `polydatamesh` (`pyvista.PolyData`): 3D mesh representing the cavern geometry.
- `dstep` (`int`, optional): Vertical step size for slicing. Default is `10`.

**Returns:**

- `df` (`pandas.DataFrame`): DataFrame with depth and cumulative volume in mesh units³.

---

### `read_inv_file(path)`

Reads a Sonarwire inventory file and parses it into a DataFrame.

**Parameters:**

- `path` (`str`): File path to the inventory file.

**Returns:**

- `df` (`pandas.DataFrame`): Inventory data with columns:
  - `'Depth'`
  - `'BBL_ft'` (barrels per foot)
  - `'BBL'` (cumulative barrels)

---

### `half_cav_rgba(path, cav=None, xy0=None)`

Generates a clipped RGBA image from a 3D cavern mesh.

Slices the mesh vertically at a specified `(x0, y0)` location or automatically at the highest point. Useful for visual inspection of cavern profiles.

**Parameters:**

- `path` (`str`): Path to the STL mesh file.
- `cav` (`pyvista.PolyData`, optional): Preloaded mesh. If `None`, loads from `path`.
- `xy0` (`tuple`, optional): `(x0, y0)` coordinates for vertical slice. Defaults to topmost point.

**Returns:**

- `crop_img` (`np.array`): RGBA image array of the clipped mesh, cropped to remove white borders.

---

### `parse_depth_chart(df, dstep=10)`

Parses a depth-volume DataFrame at uniform depth intervals for plotting or comparison with sonar volume profiles.

> **Note:** Output is spaced in Z (vertical) units — convert as needed to match sonar mesh convention.

**Parameters:**

- `df` (`pandas.DataFrame`): Output from `read_inv_file()`.
- `dstep` (`int`, optional): Depth interval to resample at. Default is `10`.

**Returns:**

- `t` (`pandas.DataFrame`): Regularly spaced DataFrame with cumulative volumes by depth.
