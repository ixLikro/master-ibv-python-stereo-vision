# Master - Industrielle Bildverarbeitung
![readme gif](https://github.com/ixLikro/master-ibv-python-stereo-vision/blob/master/resources/readme_gif.gif)

## Stereo Vision
Takes a stereo image pair as input and calculates the corresponding disparity map plus a scaled 3d point cloud.

The user can choose from the following algorithms:
- Custom block matching implementation with SSD or NCC as similarity measure (using the OpenCV function matchTemplate())
- Custom block matching implementation with SAD as similarity measure (without using OpenCV).
- OpenCV implementation of block matching and semi-global matching.

### Team members
[@LuKlose](https://github.com/LuKlose) and [@kartoffelcake](https://github.com/kartoffelcake)

### Dependencies
A [conda environment file](https://github.com/ixLikro/master-ibv-python-stereo-vision/blob/master/ibv_stereo.yml) is included.
You can install the needed environment with the following command:

```commandline
conda env create -f ibv_stereo.yml
```

### Run
1. activate ibv_stereo environment
    ```commandline
    conda activate ibv_stereo
    ```
2. run main.py
    ```commandline
    cd stereo_3d_cloud
    python main.py
    ```
Linux user? Check out [Bug-Fixing](https://github.com/ixLikro/master-ibv-python-stereo-vision#bug-fixing), in order to fix the pptk-Viewer.
   
### Test data
**Predefined test cases can be downloaded and started within the gui.**

If you want to add you own images, you can do the following:
1. create a sub directory inside your main directory (see [Config](https://github.com/ixLikro/master-ibv-python-stereo-vision#config), for more infos)
2. put your rectified images inside the new created sub directory
3. create the stereoVisionJob.json and put it also in the sub directory. <br />
   (see [stereoVisionJob.json](https://github.com/ixLikro/master-ibv-python-stereo-vision#stereovisionjobjson), for more infos):

4. restart the gui
5. start your case within the gui

### Config
The application can be configured through the config.json
The following parameters can be used:
 - **directory** (string, mandatory):<br />
    The main directory that is used by the application to lookup the test cases and store the downloaded ones. <br />
    The given path is interpreted as the relative path from the stereo_3d_cloud/main.py.<br />
    If the directory didn't exists on your machine, the directory will be created at the application startup.
 - **baseURL** (string, optional):<br />
    The application tries to perform the online lookup against this url.
    A tailing '/' should be included. <br />
    Our server data can be found [here](https://1drv.ms/u/s!AjGP35g8um5wnq4-r2LOSuuzRvIYZg?e=sWN8Rv), if you want to use your own server the data should have the same form. <br />
    Mandatory is the master.json at the root of the server directory.
 - **defaultParameter** (object, mandatory):<br />
    - **blockSize** (int, mandatory):<br />
    The block size that is used for the disparity matching algorithms. Can be overridden inside the gui with sliders.
    The blockSize must be a odd positive integer.
    - **maxDisparity** (int, mandatory):<br />
    The count of max disparity levels that should be used by the disparity matching algorithms. Can be overridden inside the gui with sliders.
    Must be a positive integer that is divisible by 16.
    - **datasets** (object, optional):<br />
        - **{dataset name}** (object, optional, can be used multiple times):<br />
            - **blockSize** (int, mandatory if parent is present):<br />
            Overrides the blockSize for one specific dataset. *
            - **maxDisparity** (int, mandatory if parent is present):<br />
            Overrides the maxDisparity for one specific dataset. *
            
 \* The first word of the job name (until '_') specifies the dataset name and is matched with the {dataset name}.
<br />
A valid example config.json:
```
{
  "baseURL": "http://ibv.schleesselmann.eu/",
  "directory": "./../testdata",
  "defaultParameter": {
    "blockSize": 15,
    "maxDisparity": 80,
    "datasets": {
      "middlebury": {
        "blockSize": 19,
        "maxDisparity": 64
      },
      "hci-bosch": {
        "blockSize": 13,
        "maxDisparity": 76
      }
    }
  }
}
```

### stereoVisionJob.json
The stereoVisionJob.json is placed inside a sub directory, describes one job and has the following form:
```
{
   "intrinsic": {
      "f": 1249.772583,
      "x0": 480.8464661,
      "y0": 237.4095154
   },
   "extrinsic": {
      "b": 0.2339241
   },
   "pathImageLeft": "imgleft000000009.pgm",
   "pathImageRight": "imgright000000009.pgm"
}
```
 - intrinsic
    - **f**: focal length of the left camera in pixels
    - **x0**: the x value of the principal point from the left camera
    - **y0**: the y value of the principal point from the left camera
 - extrinsic
    - **b**: camera baseline in m
 - **pathImageLeft**: path of the left image relative from this .json
 - **pathImageRight**: path of the right image relative from this .json
 
 ### Bug-Fixing
 #### pptk on Linux
 After installing the required conda env as described above, it might occur, that the pptk viewer does not start, but the program keeps running.
 In that case one should navigate to the anaconda directory in which pptk is stored (default, this will be ~/anaconda3/envs/ibv/lib/python3.6/site-packages/pptk/libs) and execute the following commands:
 ```console
 mv libz.so.1 libz.so.1.old
 ln -s /lib/x86_64-linux-gnu/libz.so.1 
 ```
 This should fix the problem and pptk will start
