import json
import time

import cv2 as cv
import numpy as np
import pptk
from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec

default_block_size = 15
default_d_max = 5 * 16


def disparity_to_3d_cloud(disparity, intrinsic_parameters, extrinsic_parameters, left_img):
    """
    reprojects a given image and disparity map to a 3d space with the q projection matrix.
    intrinsic and extrinsic parameters must be provided
    :param disparity: disparity map as matrix
    :param intrinsic_parameters: dictionary of intrinsic parameters
    :param extrinsic_parameters:  dictionary of extrinisc parameters
    :param left_img: matrix representation of the left stereo image
    :return:
    """
    f = intrinsic_parameters["f"]
    b = extrinsic_parameters["b"]
    c_x = intrinsic_parameters["x0"]
    c_y = intrinsic_parameters["y0"]
    height, width = disparity.shape

    cloud, color = [], []
    Q = np.array([[1, 0, 0, -c_x],
                  [0, 1, 0, -c_y, ],
                  [0, 0, 0, f],
                  [0, 0, -b, 0]])
    for y in range(0, height):
        for x in range(0, width):
            pix = Q @ [x, y, disparity[y, x], 1]
            # done no regularisation, because of large of numbers and problems displaying them
            # prevent division by zero
            if pix[3] == 0:
                continue

            result = [pix[0] / pix[3], pix[1] / pix[3], pix[2] / pix[3]]
            if np.any(np.isnan(result)) or np.any(np.isinf(result)):
                pass
            elif result[2] <= 0:
                cloud.append([result[1], result[0], result[2]])
                color.append(left_img[y, x])

    return cloud, color


def load(image_path):
    """
    Reads the image in grayscale with support for the .pgm mime type.
    Does some basic preprocessing by blurring and doing a histogram equalization.
    :param image_path: path to the image to load
    :return: the preprocessed grayscale image
    """
    if image_path.endswith(".pgm"):
        img = cv.imread(image_path, cv.IMREAD_UNCHANGED)
        img = (img * 255.0 / 4096.0).astype(np.uint8)
    else:
        img = cv.imread(image_path, cv.IMREAD_GRAYSCALE)

    img = cv.blur(img, (3, 3))
    img = cv.equalizeHist(img)
    return img


def bm_sad(left, right, block_size=default_block_size, d_max=default_d_max):
    """
    Does basic block matching to calculate the disparity between the left and right image.
    Therefore the sum of absolute differences (SAD) has been implemented by hand.
    Afterwards does a median blur to eliminate outliers.
    :param left: the left image
    :param right: the right image
    :param block_size: the block size for block matching
    :param d_max: the maximum allowed disparity
    :return: the disparity map
    """
    h, w = left.shape
    k = block_size // 2
    disparity = np.zeros_like(left)
    for y in range(k, h - k):
        for x in range(k, w - k):
            left_bound = max(0, x - d_max - k + 1)
            search_image = right[y - k:y + k + 1, left_bound:x + k + 1]
            template = left[y - k:y + k + 1, x - k:x + k + 1].astype(int)

            match_result = []
            for d in range(x - k - left_bound + 1):
                compare_image = search_image[:, d:d + block_size]
                sad = np.sum(np.abs(template - compare_image))
                match_result.append(sad)

            disparity[y, x] = np.argmin(match_result[::-1])

    return cv.medianBlur(disparity, 3)


def bm_ssd(left, right, block_size=default_block_size, d_max=default_d_max):
    """
    Does basic block matching to calculate the disparity between the left and right image.
    Therefore the CV method matchTemplate is used with the square diff mode (SSD).
    Afterwards does a median blur to eliminate outliers.
    :param left: the left image
    :param right: the right image
    :param block_size: the block size for block matching
    :param d_max: the maximum allowed disparity
    :return: the disparity map
    """
    h, w = left.shape
    k = block_size // 2
    disparity = np.zeros_like(left)
    for y in range(k, h - k):
        for x in range(k, w - k):
            left_bound = max(0, x - d_max - k + 1)
            search_image = right[y - k:y + k + 1, left_bound:x + k + 1]

            template = left[y - k:y + k + 1, x - k:x + k + 1]
            match_result = cv.matchTemplate(search_image, template, cv.TM_SQDIFF)
            disparity[y, x] = np.argmin(match_result[:, ::-1])

    return cv.medianBlur(disparity, 3)


def bm_ncc(left, right, block_size=default_block_size, d_max=default_d_max):
    """
    Does basic block matching to calculate the disparity between the left and right image.
    Therefore the CV method matchTemplate is used with the normed co-correlation mode (NCC).
    Afterwards does a median blur to eliminate outliers.
    :param left: the left image
    :param right: the right image
    :param block_size: the block size for block matching
    :param d_max: the maximum allowed disparity
    :return: the disparity map
    """
    h, w = left.shape
    k = block_size // 2
    disparity = np.zeros_like(left)
    for y in range(k, h - k):
        for x in range(k, w - k):
            left_bound = max(0, x - d_max - k + 1)
            search_image = right[y - k:y + k + 1, left_bound:x + k + 1]

            template = left[y - k:y + k + 1, x - k:x + k + 1]
            match_result = cv.matchTemplate(search_image, template, cv.TM_CCORR_NORMED)
            disparity[y, x] = np.argmax(match_result[:, ::-1])

    return cv.medianBlur(disparity, 3)


def cv_bm(left, right, block_size=default_block_size, d_max=default_d_max):
    """
    CV's standard implementation of block matching.
    Just used for comparison to our own algorithms.
    :param left: the left image
    :param right: the right image
    :param block_size: the block size for block matching
    :param d_max: the maximum allowed disparity
    :return: the disparity map
    """
    matcher = cv.StereoBM_create(
        numDisparities=d_max,
        blockSize=block_size,
    )

    disparity = matcher.compute(left, right)
    return np.int16(disparity / 16)


def cv_sgm(left, right, block_size=default_block_size, d_max=default_d_max):
    """
    CV's standard implementation of semi global matching.
    Just used for comparison to our own algorithms.
    :param left: the left image
    :param right: the right image
    :param block_size: the block size for block matching
    :param d_max: the maximum allowed disparity
    :return: the disparity map
    """
    matcher = cv.StereoSGBM_create(
        numDisparities=d_max,
        blockSize=block_size,
        mode=cv.STEREO_SGBM_MODE_HH,
    )

    disparity = matcher.compute(left, right)
    return np.int16(disparity / 16)


def deserialize_json(path_to_job_json):
    """
    Read and deserialize the given json string and returns the job parameter as dict.
    :param path_to_job_json: the path of the job
    :return: dict of the following form: {
        "pathImageLeft": path to the left image, as string, relative from the json
        "pathImageRight": path to the right image as string, relative from the json
        "intrinsic": dict of intrinsic cam parameters
        "extrinsic": dict of extrinsic cam parameters}
    """
    last_delimiter_index = path_to_job_json.rfind("\\") \
        if path_to_job_json.rfind("/") < path_to_job_json.rfind("\\") else path_to_job_json.rfind("/")
    path_prefix = ""
    if last_delimiter_index != -1:
        path_prefix = path_to_job_json[:last_delimiter_index + 1]
    json_file = open(path_to_job_json, "r")
    json_obj = json.loads(json_file.read())
    json_file.close()
    return {
        "pathImageLeft": path_prefix + json_obj["pathImageLeft"],
        "pathImageRight": path_prefix + json_obj["pathImageRight"],
        "intrinsic": json_obj["intrinsic"],
        "extrinsic": json_obj["extrinsic"]
    }


def go(path_to_job_json, algorithm, blockSize, maxDisparity, gui_callback):
    """Reads the job json, reads the images, runs the given disparity algorithm, calculates the 3d cloud and open pptk
    :param path_to_job_json: path to the json that describes the current job, as string
    :param algorithm: the disparity algorithm to use, as method reference
    :param blockSize: the block size that should be used, as int
    :param maxDisparity: the count of max disparity levels that should be used, as int
    :param gui_callback: callback function to interact thread safe with the main-gui thread.
                         use parameter *default* to display the default loading text (Berechne Disparity...).
                         use parameter *done* to hide the screen even if the tread is still running.
                         use parameter *go* to unhide the loading screen.
                         use parameter (*plot*, a matplot figure, execution time) as tuple to render the given figure inside the gui.
                         All other strings will be displayed as loading text inside the loading window.
    """
    # load and preprocess images
    job = deserialize_json(path_to_job_json)
    left = load(job["pathImageLeft"])
    right = load(job["pathImageRight"])

    # calculate disparity and time it
    start = time.time()
    disparity = algorithm(left, right, blockSize, maxDisparity)
    end = time.time()

    # create figure for gui (disparity map, right image and left image)
    fig = plt.figure(figsize=(8, 6))
    gs = GridSpec(2, 2, figure=fig)
    fig.add_subplot((gs[0, :]))
    plt.imshow(disparity, cmap='jet')
    plt.title("Disparity map"), plt.xticks([]), plt.yticks([])
    fig.add_subplot((gs[1, 0]))
    plt.imshow(left, cmap='gray')
    plt.title("Left Image"), plt.xticks([]), plt.yticks([])
    fig.add_subplot((gs[1, 1]))
    plt.imshow(right, cmap='gray')
    plt.title("Right Image"), plt.xticks([]), plt.yticks([])
    gui_callback(("*plot*", fig, end - start))

    # calculate 3d coordinates
    gui_callback("Bereche 3D-Punktwolke aus Disparity-Map")
    cloud, color = disparity_to_3d_cloud(disparity, job["intrinsic"], job["extrinsic"], left)

    # show 3d coordinate with pptk
    # need to scroll before clicking, otherwise view jumps to random position
    v = pptk.viewer(cloud, color_map='gray')
    v.set(lookat=(0, 0, -50), theta=np.pi / 2, phi=np.pi, r=50)
    v.set(show_grid=False, show_axis=False)
    v.set(point_size=0.001)
    v.attributes(color)
