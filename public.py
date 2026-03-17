# Standard Library
import os
import glob
import time
import re
import warnings
import subprocess
import itertools
from pathlib import Path
from operator import itemgetter
import importlib.resources as pkg_resources

# Scientific Computing & Plotting
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from skimage.draw import line_nd
import scipy
from scipy.spatial import cKDTree, Delaunay
from pyCRGI.pure import get_value

# 3D Visualization & Mesh Handling
import pyvista as pv
from stl import mesh
import pymeshfix as mf

# Domain-Specific Packages
#import srtm
import wellpathpy as wp
import requests

# Windows-Specific Tools (optional, handled gracefully)
try:
    import pyautogui
    import win32gui
except ImportError:
    print('Ubuntu import error, use pyautogui through Windows')


class SonarPy:

    """
    A Python Class for processing and analyzing sonar data.

    ## Parameters ---------------------------------------------------------------------------------

    surveyxyz : tuple or None
        The (x, y, z) of the survey datum in the input CRS.
    surveyxyzWGS84 : tuple or None
        The (lat, long, elevation) of the survey datum in WGS84.
    year : int, default=2024
        Year of the survey.
    metric : bool, default=False
        Whether elevation and distance units are in meters (True) or feet (False).
    crs : str or pyproj.crs.crs.CRS
        Cordinate Reference System (CRS) of the input data.
        Can be EPSG code string or pyproj CRS object.
    utm_shp_path : str or None optional
        Path to UTM Zone shapefile.
        If not provided, defaults to "C:/GIS/World_UTM_Grid.zip"`, or prompts the user.

    ## Attributes ---------------------------------------------------------------------------------

    crs : str or pyproj.CRS
        Output coordinate reference system.
    metric : bool
        Whether elevation and distance units are in meters (True) or feet (False).
    utm_shp_path : str
        File path to the UTM zone shapefile.
    utmzones : geopandas.GeoDataFrame
        UTM zone polygons.
    zonecrs : str
        EPSG code string representing the UTM zone of the survey point.
    magdec : float
        Magnetic declination in degrees.
    surveyxyz : tuple or None
        The (x, y, z) of the survey datum in the input CRS.
    pntgdf : geopandas.GeoDataFrame
        The survey point as a GeoDataFrame in the input CRS.
    pntgdfUTM : geopandas.GeoDataFrame
        The survey point reprojected to the UTM CRS.
    surveyxyzUTM : tuple
        The survey datum transformed into UTM coordinates.
    xyz_gdf : geopandas.GeoDataFrame
        3D point cloud in UTM coordinates.
    xyz_gdfCRS : geopandas.GeoDataFrame
        3D point cloud reprojected into the user-specified CRS.

    ## Setup --------------------------------------------------------------------------------------

    Download the IGRF13 coefficient file from:
        https://www.ngdc.noaa.gov/IAGA/vmod/coeffs/igrf13coeffs.txt

    Place it in:
        C:/ProgramData/anaconda3/envs/<yourenv>/lib/site-packages/pyCRGI/data/igrf13coeffs.txt

    ## Example ------------------------------------------------------------------------------------

    file = '00-2204.lwt'
    surveyxyz = (938227, 351152, 5790)
    surveyxyzWGS84 = (-105.22, 339.75, 5790)
    year = 2022 + (4-1)/12 + 15/365.25

    # Create a SonarPy instance
    sp = SonarPy(surveyxyz=surveyxyz, surveyxyzWGS84=surveyxyzWGS84, year=year,crs='EPSG:2272')
    print('MagDec:', sp.magdec)
    dflwt = sp.opent_lwt(file)
    dfT = sp.lwt_df_to_dfT(dflwt)
    xyz = sp.dfT_to_xyz_delta_points(dfT)
    xyz_gdf, xyz_gdfCRS = sp.generate_gdf(xyz)

    xyz_gdf.to_file('sonarpointsUTM.gpkg')
    xyz_gdfCRS.to_file('sonarpointsCRS.gpkg')

    ## Goals --------------------------------------------------------------------------------------

    1) K.I.S.S.
    2) Minimize tech debt
    3) Ease of use first; high end function 2nd

    ## To Do --------------------------------------------------------------------------------------

    Add:
    -2D hull geometry output
    -automatic format detection; american, german, french sonar file formats
    -automatic assignment of the metric
    -add/transfer parser for french and german formats
    -Date is in the LWT exports from CWR files ! add

    Fix
    -round outputs in a pseudo signaficant digits
    -after using this on different file types I believe the direction of the package would be to move it toward
        standalone functions for the time being rather than an all alone process. Too much variation inbetween
        data types. In the future after there may be a shift back after the transformed longwall table

    """

    def __init__(self, surveyxyz=None, surveyxyzWGS84=None, year=2024, metric=False, crs='EPSG:4326',
                 utm_shp_path=None):
        self.__version__ = '0.0.0d'
        self.crs = crs
        self.metric = metric

        # Determine UTM shapefile path
        if utm_shp_path:
            self.utm_shp_path = utm_shp_path
        elif os.path.exists(r"C:/GIS/World_UTM_Grid.zip"):
            self.utm_shp_path = r"C:/GIS/World_UTM_Grid.zip"
        else:
            self.utm_shp_path = input('Path of World_UTM_Grid.zip?')

        # Validate that UTM shapefile exists
        if not os.path.exists(self.utm_shp_path):
            raise Exception('UTM Zone Shapefile not found in', self.utm_shp_path,
                            'Place file in C:\GIS\ or define with utm_shp_path parameter')

        # Load UTM zones shapefile
        self.utmzones = gpd.read_file(self.utm_shp_path)

        # Compute magnetic declination if WGS84 coordinates are provided
        if surveyxyzWGS84:
            d, i, h, x, y, z, f = get_value(surveyxyzWGS84[1], surveyxyzWGS84[0], surveyxyzWGS84[2] / 3280.84, year)
            self.magdec = d
        else:
            warnings.warn("Provide a surveyxyz and year to add magnetic declination correction to the sonar.")
            self.magdec = 0

        # If CRS survey point is provided, store and assign UTM zone
        if surveyxyz:
            self.surveyxyz = surveyxyz
            self.utm_epsg_code_at_point(self.surveyxyz, crs=self.crs)

        # Future extension: load sonar file
        # if self.file:
        #    self.open_lwt()
        #    self.lwt_df_to_delta_points()

    def parse_date(date_string):
        """
        Format date to yyyymmdd format. Common use case is parsing Sonarwire CWR file contents for the survey date.

        Parameters
        ----------
        date_string : str
            String containing date in format 'Jul 7, 2024'
        
        Returns
        -------
        formatted_date : str or None
            Date reformatted to yyyymmdd, None if no valid date is found.
        """
        months = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        # Define the regex pattern to match the date string
        pattern = r'\w{3}[ ]{1,2}\d{1,2}, \d{4}'

        # Match the date string with the regex pattern
        match = re.findall(pattern, date_string)

        if match:
            # Extract components of the date
            day = match[0].split(' ')[1].replace(',', '')
            month = months[match[0].split(' ')[0]]
            year = match[0][-4:]

            # Format the date as yyyymmdd
            formatted_date = f'{year}{month}{day}'

            return formatted_date
        else:
            return None

    def build_horizontal_shots(data, sort_by="cAzi"):
        """
        Builds a 3D STL-style mesh from sonar scan layers.

        !! Note: The function assumes consistent ring-like ordering between layers
        for valid surface stitching. Each layer must represent a distinct scan ring.

        Parameters
        ----------
        data : GeoDataFrame or list of GeoDataFrames
            Input sonar layer(s), each with x, y, z, and a sort_by column.
        sort_by : str, default='cAzi'
            Field to sort points within each layer (preserves ring structure).

        Returns
        -------
        vertices : np.ndarray
            Combined point coordinates (N x 3).
        faces : list of lists
            Triangle faces in [3, i1, i2, i3] format.
        """
        if isinstance(data, list):
            layers = data

        elif isinstance(data, gpd.GeoDataFrame):
            gdf = data.copy()
            unique_depths = gdf["depth"].unique()

            if len(unique_depths) > 1:
                grouped = gdf.groupby("depth")
                layers = [grouped.get_group(k) for k in sorted(grouped.groups.keys())]
                print(f"Grouped by 'depth' into {len(layers)} layers.")
            else:
                print("All depths equal — splitting into 2 layers by z.")
                gdf = gdf.sort_values("z").reset_index(drop=True)
                mid = len(gdf) // 2
                gdf.loc[:mid - 1, "layer_id"] = 1
                gdf.loc[mid:, "layer_id"] = 2
                grouped = gdf.groupby("layer_id")
                layers = [grouped.get_group(k) for k in sorted(grouped.groups.keys())]
                print("Assigned 'layer_id' based on z splitting.")

        else:
            raise TypeError("Input must be a GeoDataFrame or list of GeoDataFrames.")

        # Sort and trim all layers to match size
        sorted_layers = []
        min_len = min(len(layer) for layer in layers)
        for layer in layers:
            layer = layer.sort_values(sort_by).reset_index(drop=True)
            layer = layer.iloc[:min_len]
            coords = layer[["x", "y", "z"]].to_numpy()
            sorted_layers.append(coords)

        # Stack vertices
        vertices = np.vstack(sorted_layers)
        n_layers = len(sorted_layers)
        points_per_layer = sorted_layers[0].shape[0]

        # Build triangle faces
        faces = []
        for i in range(n_layers - 1):
            top = i * points_per_layer
            bottom = (i + 1) * points_per_layer
            for j in range(points_per_layer):
                next_j = (j + 1) % points_per_layer
                a, b = top + j, top + next_j
                c, d = bottom + j, bottom + next_j
                faces.append([a, b, c])
                faces.append([b, d, c])

        return vertices, faces

    def build_endcap(layer_df):
        """
        Build a 3D mesh for a single sonar scan layer using 2D Delaunay triangulation in (x, y).

        Parameters
        ----------
        layer_df : pandas.DataFrame or GeoDataFrame
            DataFrame containing sonar points from a single horizontal layer, with columns 'x', 'y', and 'z'.

        Returns
        -------
        vertices : ndarray of shape (N, 3)
            3D coordinates of the mesh vertices.
        faces : list of list of int
            Triangle face indices as index triplets into the vertices array.
        """
        points_2d = layer_df[["x", "y"]].to_numpy()
        points_3d = layer_df[["x", "y", "z"]].to_numpy()

        tri = Delaunay(points_2d)
        faces = tri.simplices.tolist()

        return points_3d, faces


    def combine_mesh_parts(parts, filename="combined_mesh.stl"):
        """
        Combine multiple mesh parts (each with vertices and faces) into a single STL mesh file.

        Parameters
        ----------
        parts : list of tuple (ndarray, list of list of int)
            List of mesh parts, where each element is a tuple of:
            - vertices : ndarray of shape (N, 3)
            - faces : list of index triplets into the vertices array

        filename : str, optional
            Output filename for the combined STL mesh. Default is 'combined_mesh.stl'.
        """
        all_vertices = []
        all_faces = []

        vertex_offset = 0
        for vertices, faces in parts:
            all_vertices.append(vertices)
            # Shift face indices by current vertex offset
            shifted_faces = [[i + vertex_offset for i in face] for face in faces]
            all_faces.extend(shifted_faces)
            vertex_offset += len(vertices)

        # Stack everything
        vertices = np.vstack(all_vertices)
        faces = all_faces

        # Convert to triangle array
        triangles = np.zeros((len(faces), 3, 3), dtype=np.float32)
        for i, (a, b, c) in enumerate(faces):
            triangles[i][0] = vertices[a]
            triangles[i][1] = vertices[b]
            triangles[i][2] = vertices[c]

        # Create and save mesh
        your_mesh = mesh.Mesh(np.zeros(triangles.shape[0], dtype=mesh.Mesh.dtype))
        for i in range(triangles.shape[0]):
            your_mesh.vectors[i] = triangles[i]

        your_mesh.save(filename)
        print(f"Combined mesh saved to: {filename}")

    def las2txt_path(path):
        """
        Converts all LAZ files in a directory to ASCII text files using las2txt64.

        Each output file contains:
        - x, y, z coordinates (columns 1-3)
        - intensity (column 4)
        - gps_time (column 5)
        - a header row for use with txt2las64
        
        Parameters
        ----------
        path : str
            Path to the folder containing .laz files.
        """
        # Save current working directory and change to target directory
        org = os.getcwd()
        os.chdir(path)

        # Convert all .laz files to .txt using las2txt64
        os.system("las2txt64 -i *.laz -parse xyzit -sep comma")

        # Return to original working directory
        os.chdir(org)

    def add_headers_to_LAStxt(path):
        """
        Add column headers to las2txt output and save as csv.

        The input .txt files are expected to contain: X, Y, Z, intensity, and gps_time.

        Parameters
        ----------
        path : str
            Path to the folder containing .txt files exported by las2txt64.
        """
        # Ensure path ends with '/'
        path = path.replace('\\', '/')
        if path[-1] != '/':
            path = path + '/'

        # Find all txt files in directory
        files = [x.replace('\\', '/') for x in glob.glob(path + '*.txt')]

        for file in files:
            try:
                df = pd.read_csv(file, header=None)
                df.columns = ['X', 'Y', 'Z', 'intensity', 'gps_time']
                filename = file.replace('.txt', '.csv')
                df.to_csv(filename, index=False)
            except Exception as e:
                warnings.warn('ERR ' + file + ' ' + str(e))

    def dmv_exported_lwt_to_dfT(self, path):
        """
        Converts LWT files exported by DimCav Viewer to a dfT format DataFrame

        Parameters
        ----------
        path : str
            Path to the LWT file.

        Returns
        -------
        dfT : pandas.DataFrame
            Reformatted long-form DataFrame where each row represents a single sonar shot,
            including attributes such as depth, range, azimuth (cAzi), and tilt.
        """
        with open(path, 'r') as f:
            txt = f.read()

        dfT = pd.DataFrame()

        # Split into tables
        if '\n\n\n' in txt:
            tbls = txt.split('\n\n\n')
        else:
            tbls = txt.split('\n\n')

        # Parse tables into lists
        tbls = [x.split('\n') for x in tbls]
        tbls = [[y.split(';') for y in x] for x in tbls]
        tbls = [[[z for z in y if len(z) > 0] for y in x] for x in tbls]
        tbls = [x for x in tbls if len(x) > 0]
        tbls = [x for x in tbls if x != [[]]]

        for tbl in tbls:
            # Get metadata
            _, depth, _, tilt, _, vos = tbl[0]
            # Get data
            tbl = pd.DataFrame(tbl[2:], columns=tbl[1])
            tbl = tbl.astype(float)

            for index, row in tbl.iterrows():
                for col in list(tbl):
                    if col == 'Bearing':
                        bearing = row[col]
                    else:
                        plus = float(col.replace('+', '').strip())

                        r = pd.DataFrame({'depth': [depth],
                                          'tilt': [tilt],
                                          'vos': [vos],
                                          'cAzi': [bearing + plus],
                                          'r': row[col]})
                        dfT = pd.concat([dfT, r], ignore_index=True)

        dfT = dfT.astype(float)
        return dfT

    def get_well_deviation_delta(self, df, wb):
        """
        Returns the (dx, dy, dz) deviation from a wellbore survey (wb) at the correct measured depth or last depth.

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame containing the sonar data.
        wb : pandas.DataFrame
            Wellbore survey data containing columns 'MDepth', 'dx_ft', 'dy_ft', 'dz_ft'.

        Returns
        -------
        tuple
            Delta (dx, dy, dz) in feet.
        """
        depthmin = int(df.depth.min())
        deeperI = wb[wb.MDepth >= depthmin].index.tolist()

        if len(deeperI) > 0:
            if depthmin not in wb.MDepth.values:
                depths = [x for x in range(wb.MDepth.min(), wb.MDepth.max() + 1) if x not in wb.MDepth.values]
                if depthmin not in wb.MDepth.values:
                    wb = pd.concat([wb, pd.DataFrame({'MDepth': depths})], ignore_index=True)
                    wb.sort_values(by='MDepth', inplace=True)
                wb = wb.interpolate(method='linear', axis=0)
            dx = wb[wb.MDepth == depthmin]['dx_ft'].values[0]
            dy = wb[wb.MDepth == depthmin]['dy_ft'].values[0]
            dz = wb[wb.MDepth == depthmin]['dz_ft'].values[0]
        else:
            # Use last col if survey not deep enough
            dx = wb.dx_ft.values[-1]
            dy = wb.dy_ft.values[-1]
            dz = wb.dz_ft.values[-1]

        return (dx, dy, dz)

    def open_lwt(self, file):
        """
        Parses american format lwt (CWR export) sonar file into a DataFrame.

        Parameters
        ----------
        file : str
            Path to the .lwt sonar file.

        Returns
        -------
        df : pandas.DataFrame
            DataFrame parsed from lwt.
        """
        with open(file, 'r') as f:
            text = f.read()

        lines = text.split('\n')

        dpth_i = [i for i, x in enumerate(lines) if 'DEPTH' in x] + [None]

        # Empty pandas.DataFrame
        df = pd.DataFrame()

        for i0, i1 in zip(dpth_i[:-1], dpth_i[1:]):

            tlines = lines[i0:i1]

            # Drop Junk Lines
            tlines = [x.replace('\x0c', '') for x in tlines if 'Page' not in x]
            tlines = [x for x in tlines if len(x) > 0]

            # Parse section header info
            dpth, tilt, rng, vos = [x.strip().split(' ')[0] for x in tlines[0].split(':')][1:]

            # Parse table data into a dataframe for the tilt/depth/range section
            a = []
            for line in tlines[2:]:
                a.append([float(x) for x in line.strip().split(' ') if len(x) > 0])
            tdf = pd.DataFrame(a)

            # Rename columns
            tdf.columns = ['azi', '0.0', '2.8', '5.6', '8.4', '11.3', '14.1', '16.9', '19.7']  # 360 / shot len 2.8125

            # Set header data to temp table
            tdf['depth'] = dpth
            tdf['tilt'] = tilt
            tdf['range'] = rng
            tdf['vos'] = vos

            # Reorder Columns
            tdf = tdf[
                ['depth', 'tilt', 'range', 'vos', 'azi', '0.0', '2.8', '5.6', '8.4', '11.3', '14.1', '16.9', '19.7']]

            # Add to survey wide table
            df = pd.concat([df, tdf], ignore_index=True)

        # self.df = df
        df.rename(columns={'azi': 'cAzi'}, inplace=True)

        for col in df.columns:
            df[col] = df[col].astype(float)

        return df

    def getMagDev(self, long, lat, alt=0, year=2024):
        """
        Computes magnetic declination at a given location.
        Using pyCRGI : https://github.com/pleiszenburg/pyCRGI?tab=readme-ov-file

        D: declination (+ve east) [degree]
        I: inclination (+ve down) [degree]
        H: horizontal intensity [nT]
        X: north component [nT]
        Y: east component [nT]
        Z: vertical component (+ve down) [nT]
        F: total intensity [nT]

        Parameters
        ----------
        long : float
            Longitude in decimal degrees.
        lat : float
            Latitude in decimal degrees.
        alt : float, default=0
            Altitude in km.
        year : int, default=2024
            Year of the survey.

        Returns
        -------
        d : float
            Magnetic declination (+ve east).
        """

        # Get declination and store and return
        from pyCRGI.pure import get_value

        d, i, h, x, y, z, f = get_value(lat, long, alt, year)
        self.magdec = d
        return d

    def lwt_df_to_dfT(self, df):
        """
        Converts unformated pandas.DataFrame to one row per sonar shot.

        Parameters
        ----------
        df : pandas.DataFrame
            Sonar data parsed from LWT file.
        Returns
        -------
        dfT : pandas.DataFrame
            Reformatted long-form DataFrame where each row represents a single sonar shot,
            including attributes such as depth, range, azimuth (cAzi), and tilt.
        """

        # Seperate offsets to rows
        dfT = pd.DataFrame()

        for index, row in df.iterrows():
            for i, aziplus in enumerate(['0.0', '2.8', '5.6', '8.4', '11.3', '14.1', '16.9', '19.7']):
                d = {'depth': [row['depth']],
                     'tilt': [row['tilt']],
                     'range': [row['range']],
                     'vos': [row['vos']],
                     'cAzi': [row['cAzi'] + (i * 2.8125)],
                     'r': [row[aziplus]]}
                t = pd.DataFrame(d)
                dfT = pd.concat([dfT, t], ignore_index=True)

        for col in list(dfT):
            dfT[col] = dfT[col].astype(float)

        return dfT
    
    def read_lwt_dat_export(self, path):
        """
        Reads a .dat export from CavView II and reformats into LWT
        
        Parameters
        ----------
        path : str
            File path to the `.dat` file exported from CavView II.

        Returns
        -------
        dfT : pandas.DataFrame
            Reformatted long-form DataFrame where each row represents a single sonar shot,
            including attributes such as depth, range, azimuth (cAzi), and tilt.
        """
        
        # Open File
        with open(path, 'r') as f:
            lines = f.readlines()
        
        # Find Depth lines
        dindex = [i for i,x in enumerate(lines) if 'Depth:' in x]
        dindex = dindex + [None]
        
        # Empty container to add data to
        dfT = pd.DataFrame()
        
        # Loop through lwt sub tables
        for start,end in zip(dindex[:-1], dindex[1:]):
            # Grab and clean subtable
            s = lines[start:end]
            s = [x.replace('\n','') for x in s]
            s = [x for x in s if len(x) > 0]
            
            # Depth
            depth = float(s[0].split(' ')[1])
            
            # Grab and clean subtable
            data = [x.split(' ') for x in s[2:]]
            data = [[y for y in x if y != ''] for x in data]
            data = np.array(data)
            data = data.astype(float)
            
            # Calculate radii steps to handle mutliple outputs
            basedeg = data[:,0]
            data = data[:,1:]
            n = data.shape[1]
            delta = basedeg[1] - basedeg[0]
            step = delta / n

            # Build pandas.DataFrame
            r = data.flatten()
            deg = np.arange(0,360,step)
            n = deg.shape[0]
            
            temp = pd.DataFrame({'depth':[depth]*n,
                                 'tilt':[0]*n,
                                 'range':[np.nan]*n,
                                 'vos':[np.nan]*n,
                                 'cAzi':deg,
                                 'r':r,
                                 })
            
            # Concat to master
            dfT = pd.concat([dfT, temp], ignore_index=True)
        
        # Convert to float
        dfT = dfT.astype(float)

        return dfT
    
    def dfT_to_xyz_delta_points(self, dfT):
        """
        Converts dfT (one row per sonar shot with math inc and azi) and calculates delta XYZ coordinates.

        Parameters
        ----------
        dfT : pandas.DataFrame
            Reformatted long-form DataFrame where each row represents a single sonar shot,
            including attributes such as depth, range, azimuth (cAzi), and tilt.

        Returns
        -------
        xyz : pandas.DataFrame
            Formatted pandas DataFrame with calculated dx, dy, dz (delta position) information.

        Notes
        -----
        Conversion from spherical to Cartesian coordinates using:

            r : radius  
            θ : azimuth  
            φ : inclination  

            x = r * sin(φ) * cos(θ)  
            y = r * sin(φ) * sin(θ)  
            z = r * cos(φ)
        """
        ## Magnetic Declination
        dfT['cAziN'] = dfT['cAzi'] + self.magdec
        dfT['mAzi'] = dfT['cAziN'].apply(self.cAzi2mAzi)
        dfT['mInc'] = 90 - dfT['tilt']

        xyz = dfT.copy()

        ## Add check for 0 and 180 mInc, might be not tilt and mInc
        if xyz[xyz.mInc == 0].shape[0] + xyz[xyz.mInc == 180].shape[0] > 0:
            warnings.warn('Double check mInc as it may be "tilt" because a 0 or 180 shot was detected.')

        # Math done in spherical math azimuth - Use cAzi2mAzi to convert from compass azimuth
        xyz['dx'] = xyz['r'] * np.sin(np.deg2rad(xyz['mInc'])) * np.cos(np.deg2rad(xyz['mAzi']))
        xyz['dy'] = xyz['r'] * np.sin(np.deg2rad(xyz['mInc'])) * np.sin(np.deg2rad(xyz['mAzi']))
        xyz['dz'] = xyz['r'] * np.cos(np.deg2rad(xyz['mInc']))

        return xyz

    def utm_epsg_code_at_point(self, surveyxyz, crs='EPSG:4326'):
        """
        Determines the WGS 84 UTM EPSG code for a given geographic point and 
        transforms the survey coordinates to that UTM zone.

        Parameters
        ----------
        surveyxyz : tuple
            The (x, y, z) of the survey datum in the input CRS.
        crs : str, default='EPSG:4326'
            Coordinate reference system of the input surveyxyz point.

        Notes
        ----
        self.zonecrs : str
            EPSG code string of the identified UTM zone.
        self.pntgdf : GeoDataFrame
            Input point as a GeoDataFrame in its original CRS.
        self.pntgdfUTM : GeoDataFrame
            Input point reprojected to the UTM CRS.
        self.surveyxyzUTM : tuple
            (x, y, z) coordinates transformed into UTM.
        """

        # Wrap the input coordinates as a GeoDataFrame
        pntgdf = gpd.GeoDataFrame({'geometry': [Point(surveyxyz)]},
                                  crs=crs)

        # Make sure CRS is consistant
        if pntgdf.crs != self.utmzones.crs:
            pntgdf.to_crs(self.utmzones.crs, inplace=True)

        self.pntgdf = pntgdf

        # Find appropriate UTM EPSG Code
        zone = self.utmzones[self.utmzones.intersects(pntgdf.unary_union)].ZONE.values[0]
        zone = str(zone)

        while len(zone) < 2:
            zone = '0' + zone

        zonecrs = 'EPSG:326' + zone

        self.zonecrs = zonecrs

        # Convert input point to correct UTM CRS
        self.pntgdfUTM = pntgdf.to_crs(self.zonecrs)

        # Extract transformed UTM coords and convert Z to meters
        self.surveyxyzUTM = list(self.pntgdfUTM.geometry.values[0].coords)[0]
        self.surveyxyzUTM = (self.surveyxyzUTM[0],
                             self.surveyxyzUTM[1],
                             self.surveyxyzUTM[2] / 3.28084)

    def generate_gdf(self, xyz, wb_delta=(0, 0, 0)):
        """
        Converts a DataFrame of delta XYZ values into two GeoDataFrames: one in UTM and one in the specified output CRS.

        Parameters
        ----------
        xyz : pandas.DataFrame
            DataFrame with delta 'dx', 'dy', 'dz', and 'depth' columns for each sonar point.
        wb_delta : tuple of float, optional
            (dx, dy, dz) correction from well deviation survey, default is (0, 0, 0).

        Returns
        -------
        xyz_gdf : geopandas.GeoDataFrame
            Point cloud in the UTM CRS defined by the survey location.
        xyz_gdfCRS : geopandas.GeoDataFrame
            Point cloud in the specified output CRS.
        """
        # Extract survey datum from the GeoDataFrame
        x, y, z = tuple(self.pntgdf.geometry[0].coords)[0]

        # Apply wellbore deviation correction
        wb_dx, wb_dy, wb_dz = wb_delta
        xyz['dx'] += wb_dx
        xyz['dy'] += wb_dy
        xyz['dz'] += wb_dz

        # Convert from feet to meters if working in metric mode
        if not self.metric:
            z /= 3.28084
            for col in ['dx', 'dy', 'dz']:
                xyz[col] = xyz[col].astype(float) / 3.28084

        # Compute full UTM coordinates
        xyz['x'] = self.surveyxyzUTM[0] + xyz['dx']
        xyz['y'] = self.surveyxyzUTM[1] + xyz['dy']
        xyz['z'] = self.surveyxyzUTM[2] - ((xyz['depth'] / 3.28084) - xyz['dz'])

        # Create 3D shapely Points (loop version, explicit)
        xyz['geometry'] = ''
        for index, row in xyz.iterrows():
            xyz.at[index, 'geometry'] = Point(row['x'], row['y'], row['z'])

        # Create GeoDataFrame in UTM
        xyz_gdf = gpd.GeoDataFrame(xyz, crs=self.zonecrs)

        # Reproject to target CRS
        xyz_gdfCRS = xyz_gdf.copy().to_crs(self.crs)

        # Fix z-axis units if metric is False (since CRS transform doesn't touch z)
        if not self.metric:
            for index, row in xyz_gdfCRS.iterrows():
                x, y, z = list(row['geometry'].coords)[0]
                z *= 3.28084
                xyz_gdfCRS.at[index, 'geometry'] = Point(x, y, z)
                xyz_gdfCRS.at[index, 'x'] = x
                xyz_gdfCRS.at[index, 'y'] = y
                xyz_gdfCRS.at[index, 'z'] = z

        # Store attributes for reuse
        self.xyz_gdf = xyz_gdf
        self.xyz_gdfCRS = xyz_gdfCRS

        return xyz_gdf, xyz_gdfCRS


    def cAzi2mAzi(self, a):
        """
        Convert compass azimuth to math spherical azimuth.

        Parameters
        ----------
        a : float
            Compass azimuth in degrees

        Returns
        -------
        d : float
            Math spherical azimuth
        """

        # Return NaN if input is not a number
        if pd.isna(a):
            return np.nan
        
        # Convert compass to math azimuth: math = 90 - compass
        d = (90 - a) % 360

        return d

    def degmmss_to_dec_deg(x):
        """
        Converts DMS (degrees minutes seconds) strings to decimal degrees.
        
        Parameters
        ----------
        x : string
            Degrees minutes seconds in format : 93°24'50.61"W

        Returns
        -------
        dd : float
            Decimal degrees
        """
        # confirm " isn't ''
        x = x.replace("''", '"')

        # extract DMS
        d = float(x.split('°')[0])
        m = float(x.split('°')[1].split("'")[0])
        s = float(x.split("'")[1].split('"')[0])

        # Convert do decimal degrees
        dd = d + (m / 60) + ((s / 60) / 60)

        if 'W' in x:
            dd = dd * -1
        elif "S" in x:
            dd = dd * -1

        return dd

class SonarDXF:
    """
    Class for processing and interpolating sonar 3D line data.
    """
    def process_lines(xyz_gdf):
        """
        Converts a GeoDataFrame of 3D points into horizontal and vertical LineString segments
        
        Parameters
        ----------
        xyz_gdf : pandas.DataFrame or geopandas.GeoDataFrame
            DataFrame of points with columns: 'x', 'y', 'z', 'depth', 'tilt', and 'cAziN'.
        
        Returns
        -------
        lines : pandas.DataFrame
            DataFrame with a 'geometry' column containing 3D LineString objects.
        """
        lines = pd.DataFrame()

        # Horizontal lines
        for (depth, inc), group in xyz_gdf.groupby(['depth', 'tilt']):
            group.sort_values('cAziN', inplace=True)
            pnts = group[['x', 'y', 'z']].values
            pnts = np.vstack([pnts, pnts[0]])
            geom = LineString(pnts)
            t = pd.DataFrame({'depth': [depth], 'inc': [inc],})
            t['geometry'] = geom
            t['z_m'] = group.z.mean()
            lines = pd.concat([lines, t], ignore_index=True)

        # Verticle lines : tilt shots
        depths = xyz_gdf[xyz_gdf.tilt != 0].depth.unique()
        for depth in depths:
            group = xyz_gdf[xyz_gdf.depth == depth].copy()
            group['_azi'] = group['cAziN'].where(group['cAziN'] < 180, other=group['cAziN'] - 180)

            for azi, g2 in group.groupby('_azi'):
                ## Sort points by inc, one side then the other
                g20 = g2[g2.cAziN < 180].sort_values('tilt')
                g21 = g2[(g2.cAziN >= 180) & (g2.index.isin(g20.index.tolist()))].sort_values('tilt', ascending=False)

                g2 = pd.concat([g2[g2.cAziN < 180].sort_values('tilt'),
                                g2[g2.cAziN >= 180].sort_values('tilt', ascending=False)],
                               ignore_index=True)

                pnts = g2[['x', 'y', 'z']].values
                t = pd.DataFrame({'depth': [depth],'inc': [np.nan]})
                t['cAziN'] = azi
                t['geometry'] = LineString(pnts)
                t['z_m'] = group.z.mean()

                lines = pd.concat([lines, t], ignore_index=True)

        # Verticle lines : flat shots (inc == 0)
        for azi, group in xyz_gdf[xyz_gdf.tilt == 0].groupby('cAziN'):
            group.sort_values('z', ascending=False, inplace=True)
            pnts = group[['x', 'y', 'z']].values

            t = pd.DataFrame({'depth': [depth],'inc': [np.nan]})
            t['geometry'] = LineString(pnts)
            t['cAziN'] = azi
            t['z_m'] = group.z.mean()

            lines = pd.concat([lines, t], ignore_index=True)

        return lines

class SonarPyVista:
    """
    Class for creating PyVista-based visualizations from sonar-derived cavern data.
    """
    def __init__(self):
        self.__version__ = '0.0.0a'

    def wireframe_from_cavlines2(lines):
        """
        Builds a PyVista wireframe mesh from cavern survey line geometries.

        Parameters
        ----------
        lines : pandas.DataFrame or geopandas.GeoDataFrame
            DataFrame with 'geometry' column with 3D LineString objects.

        Returns
        -------
        mesh : pyvista.PolyData
            Merged wireframe mesh.
        """

        data = []
        for index, row in lines.iterrows():
            poly_line = pv.MultipleLines(points=list(row['geometry'].coords))
            data.append(poly_line)

        mesh = pv.merge(data)

        return mesh
    
    def add_rind(array_3d, rind_width):
        """
        Add a rind (border) of zeros to a 3D array.

        Parameters
        ----------
        array_3d : np.ndarray
            3D NumPy array to be padded
        rind_widith : int
            Number of zeros to pad on each side of every axis
        
        Returns
        -------
        padded_array : np.ndarray
            Padded 3D array
        """
        padded_array = np.pad(array_3d, pad_width=rind_width, mode='constant', constant_values=0)

        return padded_array

    def remove_rind(array_3d, rind_width):
        """
        Remove rind (border) of zeros from a 3D array
        
        Parameters
        ----------
        array_3d : np.ndarray
            3D NumPy array to remove padding
        rind_width : int
            Number of layers to remove from each side of the array.
        
        Returns
        -------
        array_cleaned : np.ndarray
            Array with padding removed.
        """
        # Calculate the slices to remove the rind
        slices = tuple(slice(rind_width, -rind_width) if dim != 0 else slice(None) for dim in range(array_3d.ndim))

        # Slice the array to remove the rind
        # array_cleaned = array_3d[slices]
        array_cleaned = array_3d[rind_width:-1 * rind_width,
                        rind_width:-1 * rind_width,
                        rind_width:-1 * rind_width]
        return array_cleaned

    def mesh_xyz(xyz, iterations=3, n_iter=200, rf=0.1):
        """
        Takes a geopandas.GeoDataFrame of processed xyz date (UTM) and creates
        a surface of the exterior of the cavern.  

        Parameters
        ----------
        xyz : geopandas.GeoDataFrame
            GeoDataFrame containing processed sonar data with columns:
            ['x', 'y', 'z', 'dx', 'dy', 'dz'].
        iterations : int, optional
            Number of dilation/erosion passes, default is 3.
        n_iter : int, optional
            Number of smoothing iterations, default is 200.
        rf : float, optional
            Relaxation factor for smoothing (0 disables smoothing).

        Returns
        -------
        envelope : pyvista.PolyData
            The final triangulated mesh surface of the cavern.
        """
        
        ## Make Array -------------------------------------------------------
        # Try using the val - minimum as an index then refrence later on
        minx, miny, maxx, maxy = xyz.total_bounds
        minz, maxz = xyz.z.min(), xyz.z.max()
        dx = int(maxx - minx + 1)
        dy = int(maxy - miny + 1)
        dz = int(maxz - minz + 1)
        new_variable = np.zeros((dx, dy, dz))
        #dx, dy, dz
        
        # Shot origins
        xyz['x0'] = xyz.x - xyz.dx
        xyz['y0'] = xyz.y - xyz.dy
        xyz['z0'] = xyz.z - xyz.dz
        
        ## Check for shots originating outside the pointcloud (upshots)
        n = sum(xyz['z0'] > maxz + 2) + sum(xyz['z0'] < minz - 2)
        if n > 0:
            raise Exception('n:',n,'minz:', minz, 'maxz:', maxz, 'z0min:',xyz.z0.min(), 'z0max:',xyz.z0.max(),
                            'Shot origin outside of point cloud. Upshot/Downshot survey xyz geodataframes need to be concated with the xyz geodataframes(s) of the rest of the survey for this method')


        for index, row in xyz.iterrows():
            x0 = int(xyz['x0'].values[index] - minx)
            y0 = int(xyz['y0'].values[index] - miny)
            z0 = int(xyz['z0'].values[index] - maxz) * -1

            x1 = int(xyz['x'].values[index] - minx)
            y1 = int(xyz['y'].values[index] - miny)
            z1 = int(xyz['z'].values[index] - maxz) * -1

            # Use Bresenham's Line Algorithm to get the indices of the points along the line
            indices = line_nd((x0, y0, z0),
                            (x1, y1, z1))

            # Set the corresponding points in the array to 1
            new_variable[indices] = 1

        new_variable = add_rind(new_variable, iterations + 1) #testing rind

        struct = scipy.ndimage.generate_binary_structure(3,3)

        dilated = scipy.ndimage.binary_dilation(new_variable, 
                                                iterations=iterations, 
                                                structure=struct)

        eroded = scipy.ndimage.binary_erosion(dilated,
                                                iterations=iterations, 
                                                structure=struct)

        eroded = remove_rind(eroded, iterations + 1) #testing rind

        ## Make Voxel --------------------------------------------------------
        grid = pv.ImageData()
        grid.dimensions = np.array([dx, dy, dz]) + 1 # new_variable.shape
        grid.spacing = (1, 1, 1)                     # Adjust as needed
        grid.origin = (minx, miny, minz)  # bottom SW corner, should be UTM 
        #                                 # but StatePlane would work if you 
        #                                 # adjust the iterations
        grid.cell_data["values"] = eroded[:, :, ::-1].flatten(order="F")
        
        thresh = grid.threshold(0.5)
        surface = thresh.extract_geometry()
        
        # Apply Laplacian smoothing -------------------------------------------
        if rf != 0:
            smoothed_surface = surface.smooth(n_iter=n_iter, relaxation_factor=rf)
        else:
            print('raw')
            smoothed_surface = surface
        
        
        # Fix edges -----------------------------------------------------------
        meshfix = mf.MeshFix(smoothed_surface)

        # Repair also fills holes
        meshfix.repair(verbose=True)

        envelope = meshfix.mesh.clean().triangulate()
        
        return envelope


def get_igrf_path():
    """
    Returns the full path to the IGRF13 coefficient file.
    Priority:
    1. Use packaged version (from saltpy/data/)
    2. Fallback to user cache at ~/.saltpy/
    3. Download if not found, or instruct user to manually install
    """
    # 1. Try to load the file from the installed package
    try:
        with pkg_resources.path("saltpy.data", "igrf13coeffs.txt") as p:
            return str(p)
    except (FileNotFoundError, ModuleNotFoundError):
        pass

    # 2. Fallback: ~/.saltpy/igrf13coeffs.txt
    cache_path = Path.home() / ".saltpy" / "igrf13coeffs.txt"
    if not cache_path.exists():
        print("Could not find IGRF13 file in package. Attempting download...")
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            r = requests.get("https://www.ngdc.noaa.gov/IAGA/vmod/coeffs/igrf13coeffs.txt", timeout=10)
            with open(cache_path, "w") as f:
                f.write(r.text)
            print(f"Downloaded IGRF13 file to: {cache_path}")
        except Exception as e:
            print("\n Download failed.")
            print("Manual install instructions:")
            print("  1. Download from:")
            print("     https://www.ngdc.noaa.gov/IAGA/vmod/coeffs/igrf13coeffs.txt")
            print("  2. Save to:")
            print(f"     {cache_path}")
            print("  or to your environment's site-packages in:")
            print("     <env_path>/lib/site-packages/pyCRGI/data/igrf13coeffs.txt")
            raise RuntimeError("IGRF file missing and could not be downloaded.") from e

    return str(cache_path)

