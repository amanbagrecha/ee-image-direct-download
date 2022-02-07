# How to save Earth Engine Image directly to your local machine

Oftentimes, you are required to download satellite images for your Area of Interest (AOI) and Google Earth Engine is probably a good place to avail processed satellite images for free and more importantly, only for the area you need.

One hindrance when you download from earth engine is that the images get saved in google drive, which can fill up fast for large numbers of downloads. To avoid this additional step, there is a hacky trick to download images directly.

Note: Earth Engine does provide downloadURL option, but is limited in the size of download and thus not feasible in this case. Pixel grid dimensions for getDownloadURL must be less than or equal to 10000 i.e, you can have a maximum of 100 x 100 pixel size images.

In this post I show a trick which can let you download upto 100 times larger size images, directly to your local machine. Spoiler: `getRegion` method plays a significant role to help accomplish this task. Added to that, creating a gridded bounding box for our AOI, with spacing equivalent to the pixel size will aid in our task.

We will utilize earth engine python client so that all the geopython goodies can be simultaneously utilised.

To begin with, I have a geopackage containing a polygon, which is our AOI. We aim to download sentinel-2 B4 band for the region. The ideal way would be to use the in-built `Export` option, but in our case we would use the `getRegion` method along with creating a point grid over our AOI with spacing equivalent to the pixel size.

![](https://i.imgur.com/IA5OTuN.png)

To accomplish creation of points at spacing equal to pixel width and height, we use the following function

```py
# generate points
def xcor(y_pt, crs):
    def wrap(x_each):
        feat = ee.FeatureCollection(y_pt.map(lambda y_each: ee.Feature(
            ee.Geometry.Point([x_each, y_each], ee.Projection(crs)))))
        return feat
    return wrap
```

The above code can be interpreted as a nested loop.
```
# Pseudo code
for each_x in x_pt:
    for each_y in y_pt:
        create_Point(each_x, each_y)
```
x_pt and y_pt are generated from the geopackage (AOI) using geopandas library as follows

```py
def generate_points(file_name, pixel_size):

    # read the farm and convert to geojson
    feature = gpd.read_file(file_name).__geo_interface__
    # extract bounds
    minx, miny, maxx, maxy = feature['bbox']
    # create a list with spacing equal to pixel_size
    x_pt = ee.List.sequence(minx, maxx, pixel_size)
    y_pt = ee.List.sequence(miny, maxy, pixel_size)
   
    return x_pt, y_pt, minx, maxy
```
Here we are basically creating a new `Point` feature for each x and y point.

Once we have the grid over our AOI, we can go ahead and call `getRegion` method

The documentation does a good job in explaining what `getRegion` is all about

>Output an array of values for each [pixel, band, image] tuple in an ImageCollection. The output contains rows of id, lon, lat, time, and all bands for each image that intersects each pixel in the given region. Attempting to extract more than 1048576 values will result in an error.

The limit 1048576 results in a max tile width and height of 1024 x 1024 pixels. By combining the previously created grid and `getRegion`, we could potentially get 100 times more pixels than getDownloadURL. Let us do that!

```py
len_y = len(y_pt.getInfo())
len_x = len(x_pt.getInfo())

imgCollection = ee.ImageCollection("COPERNICUS/S2_SR").filters(filters_to_add)
geometry = ee.FeatureCollection(x_pt.map(xcor(y_pt, CRS))).flatten()
input_bands = "B4"
pixel_size = 10

df = get_dataframe(imgCollection, geometry, input_bands, CRS )
data_matrix = df[input_bands].values.reshape(len_y, len_x)
data_matrix = np.flip(data_matrix, axis = 0)
transform = rasterio.transform.from_origin(minx, maxy, pixel_size, pixel_size)
save_tiff("output.tif", data_matrix, transform, CRS)
```
The above code first gets the count of points in each of the 2-dimensions followed by fetching the dataframe which contains the lat, lon and pixel value as shown in the image.

![](https://i.imgur.com/5SjjW0E.png)

Now we reshape the dataframe and flip it to make the pixel arrange in image format. Lastly, we save the image by passing the transformation of the image. Make sure to have an imageCollection for the `getRegion` method to work. Currently, the above code can only download 1 band at a time, but with simple modification to the `get_dataframe` function, that too can be changed.


```py
def get_dataframe(img_col, feature, input_band, crs):
   
    imgcol = ee.ImageCollection(img_col).select(input_band)
    df = pd.DataFrame(imgcol.getRegion(feature.geometry(), 10, crs).getInfo())
    df, df.columns = df[1:], df.iloc[0]
    df = df.drop(["id", "time"], axis=1)

    return df

def save_tiff(output_name, data_array, transform, crs):

    options = {
        "driver": "Gtiff",
        "height": data_array.shape[0],
        "width": data_array.shape[1],
        "count": 1,
        "dtype": np.float32,
        "crs": crs,
        "transform": transform
    }

    with rs.open(output_name, 'w', **options) as src:
        src.write(data_array, 1)

    return None
```

The output of the exercise is that you have a raster directly downloaded to your local machine, without google drive/ cloud intermediaries. One thing worth pointing out, is for extremely large images, you are better off downloading via the specified steps in docs. This hacky way is to simplify things and avoid google drive (which is never empty for me).

![](https://i.imgur.com/Z8DEJHh.jpg)

The full code can be accessed [here]()



