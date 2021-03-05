import json
import os.path
import queue
import threading
import urllib.request
import webbrowser

import PySimpleGUI as sg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from main import config
from stereo import go, bm_sad, bm_ssd, bm_ncc, cv_bm, cv_sgm

# constant variables
BASE_ONLINE_PATH = config["baseURL"]
MAIN_DIR = config["directory"]
ONLINE_PREFiX = "[Online] "
LOADING_TEXT_DEFAULT = "Berechne Disparity..."
LOADING_ANIMATION = "./../resources/loadingAnimation.gif"
DEFAULT_BLOCK_SIZE = config["defaultParameter"]["blockSize"]
DEFAULT_MAX_DISPARITY = config["defaultParameter"]["maxDisparity"]

# global variables
online_jobs = None
window = None
loadingScreen = None
show_loading_animation = False
gui_queue = queue.Queue()


def listAvailableJobs():
    """list all jobs that are available local and online
    :return an array with jobs"""
    global online_jobs
    # list all local jobs (dirs with a stereoVisionJob.json inside)
    files = os.listdir(MAIN_DIR)
    jobs = []
    for file in files:
        path = os.path.join(MAIN_DIR, file)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "stereoVisionJob.json")):
            jobs.append(file)

    # check online
    try:
        result = urllib.request.urlopen(BASE_ONLINE_PATH + "master.json").read().decode("utf-8")
        online_jobs = json.loads(result)["jobs"]
        for onlineJob in online_jobs:
            if not onlineJob["name"] in jobs:
                jobs.append(ONLINE_PREFiX + onlineJob["name"])
    except:
        print("Error during online lockup")

    return jobs


def getOnlineJob(nameWithPrefix):
    """:param nameWithPrefix: the name of the job
    :return: None if not a online job or the parsed json of this job as python dict """
    if nameWithPrefix.startswith(ONLINE_PREFiX):
        name = nameWithPrefix[len(ONLINE_PREFiX):]
        return [x for x in online_jobs if x["name"] == name][0]
    else:
        return None


def downloadAndSaveJob(onlineJob):
    """downloads and saves the images, json and license inside the sub dir
    :param onlineJob: the parsed json that describes the job that should be downloaded"""

    # create dir
    os.chdir(MAIN_DIR)
    os.mkdir(onlineJob["name"])

    # download and save files
    jobURL = BASE_ONLINE_PATH + onlineJob["name"] + "/"
    print("start downloding job " + onlineJob["name"])
    urllib.request.urlretrieve(jobURL + onlineJob["left"], os.path.join(onlineJob["name"], onlineJob["left"]))
    urllib.request.urlretrieve(jobURL + onlineJob["right"], os.path.join(onlineJob["name"], onlineJob["right"]))
    urllib.request.urlretrieve(jobURL + onlineJob["json"], os.path.join(onlineJob["name"], onlineJob["json"]))
    urllib.request.urlretrieve(BASE_ONLINE_PATH + onlineJob["license"],
                               os.path.join(onlineJob["name"], onlineJob["license"]))
    print("download finished")

    # update the job list in the main window
    gui_queue.put('*trigger list reload*', block=True, timeout=50)


def gui_callback(message):
    """can be used to change the text of the loading screen.
    :param message: the new text that should be displayed.
                    use message *default* to display the default loading text (Berechne 3D-Punktwolke...)
                    use message *done* to hide the screen even if the tread is still running.
                    use message *go* to unhide the screen
                    use message (*plot*, a matplot figure, execution time in s) as tuple to render the given figure inside the gui
                    """
    gui_queue.put(message, block=True, timeout=50)


def theadWorker(methodToCall, onlineJob, params):
    """
    Wrapper method for long running tasks. This method is intended to run in a separate Thread.
    As long as the given Method runs, a loading animation will be shown.
    :param methodToCall: a method reference to the method that do the actual hart work
    :param onlineJob: None or the parsed json that describes the job.
                      If a online job is provided, it will be downloaded and saved.
    :param params: a tuple of arguments that will be passed to the given method.
    """
    # start loading animation
    gui_queue.put("*go*", block=True, timeout=50)
    gui_queue.put("*default*", block=True, timeout=50)

    # perform the download if needed
    if onlineJob:
        gui_queue.put(("Lade Testfall " + onlineJob["name"] + " herunter..."), block=True, timeout=50)
        downloadAndSaveJob(onlineJob)
        gui_queue.put("*default*", block=True, timeout=50)

    # run task
    try:
        methodToCall(*params)
    except Exception as e:
        print("Error during point cloud calculation!")
        print(e)
    finally:
        # hide loading screen
        gui_queue.put("*done*", block=True, timeout=50)


def findLocalLicence(jobName):
    """
    tries to find the licence file in the given local job sub folder.
    :param jobName: the job name
    :return: (path, name) of the licence file or (None, None) if no licence file was found.
    """
    files = os.listdir(os.path.join(MAIN_DIR, jobName))
    for f in files:
        if os.path.isfile(os.path.join(MAIN_DIR, jobName, f)) and f.endswith(".txt"):
            return os.path.join(MAIN_DIR, jobName, f), f
    return None, None


def startMatching(event, values):
    """starts a new thread that perform the heavy calculation
    :param event: the key of the button that was fired by the user
    :param values: the given event values values"""
    # get json path
    onlineJob = getOnlineJob(values['-JOB_LIST-'][0])
    name = values['-JOB_LIST-'][0]
    if onlineJob:
        name = onlineJob["name"]
    jsonPath = os.path.join(MAIN_DIR, name, "stereoVisionJob.json")

    # select the algorithm that should be started
    algorithm = None
    if event == "-GO_BM_SSD-":
        algorithm = bm_ssd
    elif event == "-GO_BM_NCC-":
        algorithm = bm_ncc
    elif event == "-GO_CV_BM-":
        algorithm = cv_bm
    elif event == "-GO_CV_SGM-":
        algorithm = cv_sgm
    elif event == "-GO_BM_SAD-":
        algorithm = bm_sad

    # start a thead with the wrapper method theadWorker, this method will show a loading animation as long the
    # the given operation runs.
    threading.Thread(target=theadWorker,
                     args=(go, onlineJob,
                           (jsonPath, algorithm, int(values["-BLOCK_SIZE-"] + 1), int(values["-DISPARITY-"]),
                            gui_callback,)),
                     daemon=True) \
        .start()


def drawFigure(figure):
    """
    renders the given plot inside the canvas of the 3rd column
    :param figure: the matplot figure that should be rendered
    """
    canvas = window.Find('-CANVAS-').TKCanvas
    # destroy old plots
    if canvas.children:
        for child in canvas.winfo_children():
            child.destroy()
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=0)


def createLoadingScreen():
    """creates the loading screen window"""
    global loadingScreen
    loadingScreen = sg.Window('Loading', [
        [sg.Image(LOADING_ANIMATION, key="-GIF-", background_color='white')],
        [sg.Text(LOADING_TEXT_DEFAULT, key="-TEXT-", background_color='white', font='Arial 14', size=(50, 1))]
    ], no_titlebar=True, grab_anywhere=True, keep_on_top=True, background_color='white')


def setDefaultSliderValues(job):
    """sets the slider to the default position based on the config.json
    :param job: the selected job
    """
    name = job if not getOnlineJob(job) else getOnlineJob(job)["name"]
    dataset = name.split("_")[0]
    bs, md = (DEFAULT_BLOCK_SIZE, DEFAULT_MAX_DISPARITY)
    if "datasets" in config["defaultParameter"] and dataset in config["defaultParameter"]["datasets"]:
        bs, md = (config["defaultParameter"]["datasets"][dataset]["blockSize"],
                  config["defaultParameter"]["datasets"][dataset]["maxDisparity"])
    window.Find("-BLOCK_SIZE-").Update(value=bs - 1)
    window.Find("-BLOCK_SIZE_TEXT-").Update(str(bs))
    window.Find("-DISPARITY-").Update(value=md)
    window.Find("-DISPARITY_TEXT-").Update(str(md))


def init_and_run_gui():
    """initializes and starts the gui. This method blocks until the main window is closed"""
    global window, show_loading_animation, loadingScreen, last_execution_time

    # layout of the left side (job selector)
    left_col = [[sg.Listbox(values=listAvailableJobs(), enable_events=True, size=(40, 40), key='-JOB_LIST-')]]

    # layout for settings and start buttons
    slider_and_go_frame = [
        [sg.Text('Blocksize:', size=(13, 1), key="-BLOCK_SIZE_DESCRIPTION-"),
         sg.Slider(key="-BLOCK_SIZE-", range=(4, 32), default_value=DEFAULT_BLOCK_SIZE - 1, orientation='horizontal',
                   disable_number_display=True, enable_events=True, size=(14, 20), resolution=2),
         sg.Text(str(DEFAULT_BLOCK_SIZE), key="-BLOCK_SIZE_TEXT-", size=(8, 1))
         ],
        [sg.Text('max. Disparities:', key="-DISPARITY_DESCRIPTION-", size=(13, 1)),
         sg.Slider(key="-DISPARITY-", range=(16, 320), default_value=DEFAULT_MAX_DISPARITY, orientation='horizontal',
                   disable_number_display=True, enable_events=True, size=(14, 20), resolution=16),
         sg.Text(str(DEFAULT_MAX_DISPARITY), key="-DISPARITY_TEXT-", size=(8, 1))
         ],
        [sg.Button(button_text="Block-Matching (SSD) ausführen", key="-GO_BM_SSD-")],
        [sg.Button(button_text="Block-Matching (NCC) ausführen", key="-GO_BM_NCC-")],
        [sg.Button(button_text="CV Block-Matching (CV_BM) ausführen", key="-GO_CV_BM-")],
        [sg.Button(button_text="CV Semi-Global-Matching (CV_SGM) ausführen", key="-GO_CV_SGM-")],
        [sg.Button(button_text="Block-Matching (SAD, langsam!) ausführen", key="-GO_BM_SAD-")],
        [sg.Text("")],
        [sg.Text("Achtung pptk-Bug: Im 3D-Viewer erst scrollen, dann klicken!", text_color="red", font='Arial 14' ,size=(30,2))]
    ]

    # the 2nd col, that holds detailed information of the selected job
    selected_col = [
        [sg.Text('Noch kein Testfall ausgewählt. Bitte wähle links einen Fall.', key="-HEADER_JOB-", size=(35, 2),
                 font='Arial 14')],
        [sg.Frame(layout=[[sg.Text('', size=(35, 7), key='-DETAILS-', visible=False)]], title="", border_width=0)],
        [sg.Frame(key='-LICENCE_FRAME-', layout=[[sg.Text('Lizenz: '),
                                                  sg.Text('', text_color='blue', enable_events=True, key='-LICENCE-',
                                                          size=(25, 1))
                                                  ]], title="", border_width=0, size=(30, 1), visible=False)],
        [sg.Text("", size=(1, 1))],
        [sg.Frame(key="-FRAME-", layout=slider_and_go_frame, title="", border_width=0, visible=False)]
    ]

    # the 3rd column, that show the plot
    plot_col = [
        [sg.Text('', key='-CANVAS_HEADER-', size=(45, 1))],
        [sg.Canvas(key='-CANVAS-', size=(35, 14))]
    ]

    # full layout (put everything in one row)
    layout = [[
        sg.Column(left_col),
        sg.VSeperator(),
        sg.Column(selected_col, key='-DETAILS_COLUMN-', size=(35, 15)),
        sg.VSeperator(),
        sg.Column(plot_col, key="-PLOT_COLUMN-", visible=False, pad=(0, 0))
    ]]

    # create the window and loading screen
    window = sg.Window('Stereo Vision', layout)

    # event loop
    while True:
        event, values = window.Read(timeout=50)
        if event in (None, 'Exit'):
            # exit
            break
        if event == '-JOB_LIST-':
            # A file was chosen from the listbox
            try:
                onlineJob = getOnlineJob(values['-JOB_LIST-'][0])
                if onlineJob:
                    # a online job was selected
                    window.Find('-LICENCE_FRAME-').Update(visible=True)
                    window.Find('-LICENCE-').Update(onlineJob["license"])
                    details = "Fundort: Online\nJson: " + BASE_ONLINE_PATH + onlineJob['name'] \
                              + "/stereoVisionJob.json\n\nDie Bilder werden vor der ersten Ausfühung heruntergeladen."
                else:
                    # a local job was selected
                    details = "Fundort: Lokal\nJson: " + os.path.join(MAIN_DIR, values['-JOB_LIST-'][0],
                                                                      "stereoVisionJob.json")
                    # display licence
                    lPath, lName = findLocalLicence(values['-JOB_LIST-'][0])
                    if lPath and lName:
                        window.Find('-LICENCE_FRAME-').Update(visible=True)
                        window.Find('-LICENCE-').Update(lName)
                    else:
                        window.Find('-LICENCE_FRAME-').Update(visible=False)
                window.Find("-HEADER_JOB-").Update(values['-JOB_LIST-'][0] + ":")
                window.Find('-DETAILS-').Update(details, visible=True)
                window.Find('-FRAME-').Update(visible=True)
                setDefaultSliderValues(values['-JOB_LIST-'][0])
            except Exception as e:
                print("Error during item selection")
                print(e)
                pass
        if event.startswith("-GO_"):
            # a start button was pressed
            startMatching(event, values)
        if event == "-LICENCE-":
            # licence was clicked
            onlineJob = getOnlineJob(values['-JOB_LIST-'][0])
            if onlineJob:
                webbrowser.open(BASE_ONLINE_PATH + onlineJob["license"])
            else:
                lPath, lName = findLocalLicence(values['-JOB_LIST-'][0])
                if lPath and lName:
                    webbrowser.open(lPath)
        if event == "-DISPARITY-":
            # the disparity slider was changed
            window.Find("-DISPARITY_TEXT-").Update(str(int(values["-DISPARITY-"])))
        if event == "-BLOCK_SIZE-":
            # the block size slider was changed
            window.Find("-BLOCK_SIZE_TEXT-").Update(str(int(values["-BLOCK_SIZE-"] + 1)))

        # display loading screen
        if show_loading_animation:
            if loadingScreen is None:
                createLoadingScreen()
            loadingScreen.UnHide()
            loadingScreen.Read(timeout=10)
            loadingScreen.Find("-GIF-").UpdateAnimation(LOADING_ANIMATION)
        else:
            if loadingScreen is not None:
                loadingScreen.Hide()

        # Check for incoming messages from threads
        try:
            message = gui_queue.get_nowait()
        except queue.Empty:
            message = None

        # if message received from queue, display the message in the loading screen
        if message:
            if message == "*go*":
                show_loading_animation = True
            elif message == "*done*":
                show_loading_animation = False
            elif message == "*default*":
                if loadingScreen:
                    loadingScreen.Find("-TEXT-").Update(LOADING_TEXT_DEFAULT)
            elif message == "*trigger list reload*":
                job = values['-JOB_LIST-'][0]
                name = job if not getOnlineJob(job) else getOnlineJob(job)["name"]
                jobs = listAvailableJobs()
                window.Find('-JOB_LIST-').Update(jobs, set_to_index=jobs.index(name))
            elif type(message) is tuple and message[0] == "*plot*":
                # new plot
                window.Find("-PLOT_COLUMN-").Update(visible=True)
                window.Find("-CANVAS_HEADER-").Update("Ausführung: " + values['-JOB_LIST-'][0] + ", "
                                                      + "Dauer: " + str(round(message[2], 3)) + "s")
                drawFigure(message[1])
            else:
                # just a message -> display it on the loading screen
                if loadingScreen:
                    loadingScreen.Find("-TEXT-").Update(message)

    window.Close()


if __name__ == '__main__':
    # start gui
    init_and_run_gui()
