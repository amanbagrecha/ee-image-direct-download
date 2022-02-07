import ee
import geopandas as gpd
import pandas as pd
import os
import rasterio as rs
import numpy as np

# Initialize the library. Also make sure to authenticate using ee.Authenticate()
# if you do not have earthengine token on your machine
ee.Initialize()


def maskS2clouds(image):
    
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(
        qa.bitwiseAnd(cirrusBitMask).eq(0))

    return image.updateMask(mask).set("system:time_start", image.get("system:time_start"))


def addNDVI(image):
    ndvi_s = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    ndvi = ndvi_s.set("system:time_start", image.get("system:time_start"))
    return image.addBands(ndvi)

# generate points


def xcor(y_pt, crs):
    def wrap(x_each):

        feat = ee.FeatureCollection(y_pt.map(lambda y_each: ee.Feature(
            ee.Geometry.Point([x_each, y_each], ee.Projection(crs)))))
        return feat
    return wrap


def generatePoints(file_name, pixel_size):

    # read the farm and convert to geojson
    feature = gpd.read_file(file_name).__geo_interface__
    # extract bounds
    minx, miny, maxx, maxy = feature['bbox']

    x_pt = ee.List.sequence(minx, maxx, pixel_size)
    y_pt = ee.List.sequence(miny, maxy, pixel_size)

    return x_pt, y_pt, minx, maxy


def getDataframe(img_col, feature, input_band, crs):

    imgcol = ee.ImageCollection(img_col).select(input_band)
    df = pd.DataFrame(imgcol.getRegion(feature.geometry(), 10, crs).getInfo())
    df, df.columns = df[1:], df.iloc[0]
    df = df.drop(["id", "time"], axis=1)

    return df


def saveTiff(nut, data_array, transform, crs):

    file_name = os.path.basename(nut).split('.')[0]

    options = {
        "driver": "Gtiff",
        "height": data_array.shape[0],
        "width": data_array.shape[1],
        "count": 1,
        "dtype": np.float32,
        "crs": crs,
        "transform": transform
    }

    with rs.open(f"{file_name}.tif", 'w', **options) as src:
        src.write(data_array, 1)

    return None


if __name__ == "__main__":

    dirname = os.path.dirname(os.path.abspath(__file__))
    os.chdir(dirname)
    file_name = r"./mygpkg.gpkg"
    save_path_tiff = './'

    pixel_size = 10
    CRS = 'EPSG:32643'

    input_bands = ['B4']
    start_date = '2020-02-01'
    end_date = '2020-02-08'

    x_pt, y_pt, minx, maxy = generatePoints(file_name, pixel_size)
    geometry = ee.FeatureCollection(x_pt.map(xcor(y_pt, CRS))).flatten()

    s2_sr = ee.ImageCollection("COPERNICUS/S2_SR")

    imgCollection = s2_sr.filterBounds(geometry.geometry())\
        .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 50))\
        .filterDate(ee.Date(start_date), ee.Date(end_date))\
        .map(maskS2clouds)\
        .map(addNDVI)\
        .median()

    len_y = len(y_pt.getInfo())
    len_x = len(x_pt.getInfo())

    df = getDataframe(imgCollection, geometry, input_bands, CRS)
    data_matrix = df[input_bands].values.reshape(len_y, len_x)
    data_matrix = np.flip(data_matrix, axis=0)
    transform = rs.transform.from_origin(minx, maxy, pixel_size, pixel_size)

    saveTiff("b4_band", data_matrix, transform, CRS)
