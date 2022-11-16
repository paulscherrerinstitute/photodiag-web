import time

import epics
import numpy as np
from bokeh.layouts import column, row
from bokeh.models import (
    BasicTicker,
    Button,
    ColumnDataSource,
    DataRange1d,
    Grid,
    Legend,
    Line,
    LinearAxis,
    Plot,
    Scatter,
    Select,
    Spacer,
    Spinner,
    TabPanel,
)
from cam_server_client import PipelineClient
from scipy.optimize import curve_fit

from photodiag_web import DEVICES

TARGETS = ["target1", "target2", "target3"]
scan_x_range = np.linspace(-0.3, 0.3, 3)
scan_y_range = np.linspace(-0.3, 0.3, 3)
client = PipelineClient()

channels = [
    "SAROP11-CVME-PBPS2:Lnk9Ch11-DATA-SUM",
    "SAROP11-CVME-PBPS2:Lnk9Ch13-DATA-SUM",
    "SAROP11-CVME-PBPS2:Lnk9Ch14-DATA-SUM",
    "SAROP11-CVME-PBPS2:Lnk9Ch15-DATA-SUM",
]

device_prefix = "SAROP11-PBPS110:"

pipeline_name = "SAROP11-PBPS110_proc"

PBPS_x_PV_name = device_prefix + "MOTOR_X1.VAL"
PBPS_y_PV_name = device_prefix + "MOTOR_Y1.VAL"

PBPS_x_PV = epics.PV(PBPS_x_PV_name)
PBPS_y_PV = epics.PV(PBPS_y_PV_name)


def set_PBPS_x(pos):
    PBPS_x_PV.put(pos, wait=True)


def set_PBPS_y(pos):
    PBPS_y_PV.put(pos, wait=True)


def make_arrays(pvs, n_pulses):
    arrays = []
    for pv in pvs:
        val = pv.value

        dtype = get_dtype(val)
        shape = get_shape(val)
        shape = (n_pulses,) + shape

        arr = np.empty(shape, dtype)
        arrays.append(arr)

    return arrays


def PBPS_get_data(channels, n_pulses=100, wait_time=0.5):
    pvs = [epics.PV(ch) for ch in channels]
    n_channels = len(channels)
    counters = np.zeros(n_channels, dtype=int)

    arrays = make_arrays(pvs, n_pulses)

    def on_value_change(pv=None, ichannel=None, value=None, **kwargs):
        ivalue = counters[ichannel]
        arrays[ichannel][ivalue] = value

        counters[ichannel] += 1

        if counters[ichannel] == n_pulses:
            pv.clear_callbacks()

    for i, pv in enumerate(pvs):
        pv.add_callback(callback=on_value_change, pv=pv, ichannel=i)

    if not np.all(counters == n_pulses):
        time.sleep(wait_time)

    return arrays


def get_dtype(v):
    if isinstance(v, np.ndarray):
        return v.dtype
    else:
        return type(v)


def get_shape(v):
    if isinstance(v, np.ndarray):
        return v.shape
    else:
        return tuple()


def PBPS_x_scan(scan_x_range, channels, numShots):
    scan_mean = []
    scan_std = []
    scan_all = []

    for pos in scan_x_range:
        set_PBPS_x(pos)
        data = PBPS_get_data(channels, numShots)
        scan_mean.append([i.mean() for i in data])
        scan_std.append([i.std() for i in data])
        scan_all.append(data)

    return np.asarray(scan_mean), np.asarray(scan_std), np.asarray(scan_all)


def PBPS_y_scan(scan_y_range, channels, numShots):
    scan_mean = []
    scan_std = []
    scan_all = []

    for pos in scan_y_range:
        set_PBPS_y(pos)
        data = PBPS_get_data(channels, numShots)
        scan_mean.append([i.mean() for i in data])
        scan_std.append([i.std() for i in data])
        scan_all.append(data)

    return np.asarray(scan_mean), np.asarray(scan_std), np.asarray(scan_all)


def PBPS_I_calibrate(channels, numShots):
    scan_mean = []
    scan_std = []
    scan_all = []

    data = PBPS_get_data(channels, numShots)
    scan_mean.append([i.mean() for i in data])
    scan_std.append([i.std() for i in data])
    scan_all.append(data)

    return np.asarray(scan_mean), np.asarray(scan_std), np.asarray(scan_all)


def lin_fit(x, m, a):
    return m * x + a


def fit(xdata, ydata):
    popt, pcov = curve_fit(lin_fit, xdata, ydata)
    return popt


def create():
    # horiz_plot
    horiz_plot = Plot(
        x_range=DataRange1d(),
        y_range=DataRange1d(),
        height=300,
        width=500,
        toolbar_location="left",
    )

    horiz_plot.toolbar.logo = None

    horiz_plot.add_layout(LinearAxis(axis_label=PBPS_x_PV_name), place="below")
    horiz_plot.add_layout(
        LinearAxis(axis_label="Ir-Il/Ir+Il", major_label_orientation="vertical"), place="left"
    )

    horiz_plot.add_layout(Grid(dimension=0, ticker=BasicTicker()))
    horiz_plot.add_layout(Grid(dimension=1, ticker=BasicTicker()))

    horiz_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    horiz_scatter = horiz_plot.add_glyph(
        horiz_scatter_source, Scatter(x="x", y="y", line_color="blue", fill_color="blue")
    )

    horiz_line_source = ColumnDataSource(dict(x=[], y=[]))
    horiz_line = horiz_plot.add_glyph(horiz_line_source, Line(x="x", y="y", line_color="red"))

    horiz_plot.add_layout(
        Legend(
            items=[("data", [horiz_scatter]), ("fit", [horiz_line])],
            location="top_left",
            click_policy="hide",
        )
    )

    # vert_plot
    vert_plot = Plot(
        x_range=DataRange1d(), y_range=DataRange1d(), height=300, width=500, toolbar_location="left"
    )

    vert_plot.toolbar.logo = None

    vert_plot.add_layout(LinearAxis(axis_label=PBPS_y_PV_name), place="below")
    vert_plot.add_layout(
        LinearAxis(axis_label="Iu-Id/Iu+Id", major_label_orientation="vertical"), place="left"
    )

    vert_plot.add_layout(Grid(dimension=0, ticker=BasicTicker()))
    vert_plot.add_layout(Grid(dimension=1, ticker=BasicTicker()))

    vert_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    vert_scatter = vert_plot.add_glyph(
        vert_scatter_source, Scatter(x="x", y="y", line_color="blue", fill_color="blue")
    )

    vert_line_source = ColumnDataSource(dict(x=[], y=[]))
    vert_line = vert_plot.add_glyph(
        vert_line_source, Scatter(x="x", y="y", line_color="red", fill_color="red")
    )

    vert_plot.add_layout(
        Legend(
            items=[("data", [vert_scatter]), ("fit", [vert_line])],
            location="top_left",
            click_policy="hide",
        )
    )

    device_select = Select(title="Device:", value=DEVICES[0], options=DEVICES)
    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=500, step=100, low=100)
    target_select = Select(title="Target:", value=TARGETS[0], options=TARGETS, disabled=True)
    norm_diodes = np.zeros((1, 4))
    scan_x_norm = None
    scan_y_norm = None

    def calibrate_button_callback():
        nonlocal norm_diodes, scan_x_norm, scan_y_norm
        numShots = num_shots_spinner.value
        scan_I_mean, _, _ = PBPS_I_calibrate(channels, numShots)
        norm_diodes = np.asarray([1 / tm / 4 for tm in scan_I_mean])

        scan_x_mean, _, _ = PBPS_x_scan(scan_x_range, channels, numShots)
        set_PBPS_x(0)

        scan_y_mean, _, _ = PBPS_y_scan(scan_y_range, channels, numShots)
        set_PBPS_y(0)

        scan_x_norm = (
            scan_x_mean[:, 3] * norm_diodes[0, 3] - scan_x_mean[:, 2] * norm_diodes[0, 2]
        ) / (scan_x_mean[:, 3] * norm_diodes[0, 3] + scan_x_mean[:, 2] * norm_diodes[0, 2])

        scan_y_norm = (
            scan_y_mean[:, 1] * norm_diodes[0, 1] - scan_y_mean[:, 0] * norm_diodes[0, 0]
        ) / (scan_y_mean[:, 1] * norm_diodes[0, 1] + scan_y_mean[:, 0] * norm_diodes[0, 0])

        popt_norm_x = fit(scan_x_range, scan_x_norm)
        popt_norm_y = fit(scan_y_range, scan_y_norm)

        # Update plots
        horiz_scatter_source.data.update(x=scan_x_range, y=scan_x_norm)
        horiz_line_source.data.update(x=scan_x_range, y=lin_fit(scan_x_range, *popt_norm_x))

        vert_scatter_source.data.update(x=scan_y_range, y=scan_y_norm)
        vert_line_source.data.update(x=scan_y_range, y=lin_fit(scan_y_range, *popt_norm_y))

    calibrate_button = Button(label="Calibrate", button_type="primary")
    calibrate_button.on_click(calibrate_button_callback)

    def push_results_button_callback():
        # Intensity
        # Set channels
        # Input data
        epics.PV(device_prefix + "INTENSITY.INPA").put(bytes(channels[0], "utf8"))
        epics.PV(device_prefix + "INTENSITY.INPB").put(bytes(channels[1], "utf8"))
        epics.PV(device_prefix + "INTENSITY.INPC").put(bytes(channels[2], "utf8"))
        epics.PV(device_prefix + "INTENSITY.INPD").put(bytes(channels[3], "utf8"))
        # Calibration values
        epics.PV(device_prefix + "INTENSITY.E").put(bytes(str(norm_diodes[0, 0]), "utf8"))
        epics.PV(device_prefix + "INTENSITY.F").put(bytes(str(norm_diodes[0, 1]), "utf8"))
        epics.PV(device_prefix + "INTENSITY.G").put(bytes(str(norm_diodes[0, 2]), "utf8"))
        epics.PV(device_prefix + "INTENSITY.H").put(bytes(str(norm_diodes[0, 3]), "utf8"))
        # Calculation
        epics.PV(device_prefix + "INTENSITY.CALC").put(bytes("A*E+B*F+C*G+D*H", "utf8"))

        # XPOS
        # Set channels
        epics.PV(device_prefix + "XPOS.INPA").put(bytes(channels[2], "utf8"))
        epics.PV(device_prefix + "XPOS.INPB").put(bytes(channels[3], "utf8"))
        # Threshold value
        epics.PV(device_prefix + "XPOS.D").put(bytes(str(0.2), "utf8"))
        # Diode calibration value
        epics.PV(device_prefix + "XPOS.E").put(bytes(str(norm_diodes[0, 2]), "utf8"))
        epics.PV(device_prefix + "XPOS.F").put(bytes(str(norm_diodes[0, 3]), "utf8"))
        # Null value
        epics.PV(device_prefix + "XPOS.G").put(bytes(str(0), "utf8"))
        # Position calibration value
        epics.PV(device_prefix + "XPOS.I").put(
            bytes(str((scan_x_range[1] - scan_x_range[0]) / np.diff(scan_x_norm).mean()), "utf8")
        )
        # Intensity threshold value
        epics.PV(device_prefix + "XPOS.INPJ").put(bytes(device_prefix + "INTENSITY", "utf8"))
        # Calculation
        epics.PV(device_prefix + "XPOS.CALC").put(bytes("J<D?G:I*(A*E-B*F)/(A*E+B*F)", "utf8"))

        # YPOS
        # Set channels
        epics.PV(device_prefix + "YPOS.INPA").put(bytes(channels[0], "utf8"))
        epics.PV(device_prefix + "YPOS.INPB").put(bytes(channels[1], "utf8"))
        # Threshold value
        epics.PV(device_prefix + "YPOS.D").put(bytes(str(0.2), "utf8"))
        # Diode calibration value
        epics.PV(device_prefix + "YPOS.E").put(bytes(str(norm_diodes[0, 0]), "utf8"))
        epics.PV(device_prefix + "YPOS.F").put(bytes(str(norm_diodes[0, 1]), "utf8"))
        # Null value
        epics.PV(device_prefix + "YPOS.G").put(bytes(str(1), "utf8"))
        # Position calibration value
        epics.PV(device_prefix + "YPOS.I").put(
            bytes(str((scan_y_range[1] - scan_y_range[0]) / np.diff(scan_y_norm).mean()), "utf8")
        )
        # Intensity threshold value
        epics.PV(device_prefix + "YPOS.INPJ").put(bytes(device_prefix + "INTENSITY", "utf8"))
        # Calculation
        epics.PV(device_prefix + "YPOS.CALC").put(bytes("J<D?G:I*(A*E-B*F)/(A*E+B*F)", "utf8"))

        # Push position calibration to pipeline
        config = client.get_instance_config(pipeline_name)
        config["right_calib"] = norm_diodes[0, 2]
        config["left_calib"] = norm_diodes[0, 3]
        config["up_calib"] = norm_diodes[0, 1]
        config["down_calib"] = norm_diodes[0, 0]
        config["vert_calib"] = (scan_y_range[1] - scan_y_range[0]) / np.diff(scan_y_norm).mean()
        config["horiz_calib"] = (scan_x_range[1] - scan_x_range[0]) / np.diff(scan_x_norm).mean()
        config["queue_length"] = 5000
        client.save_pipeline_config(pipeline_name, config)
        client.stop_instance(pipeline_name)

    push_results_button = Button(label="Push results", disabled=True)
    push_results_button.on_click(push_results_button_callback)

    push_elog_button = Button(label="Push elog", disabled=True)

    tab_layout = column(
        row(horiz_plot, vert_plot),
        row(
            device_select,
            num_shots_spinner,
            target_select,
            column(Spacer(height=18), row(calibrate_button, push_results_button, push_elog_button)),
        ),
    )

    return TabPanel(child=tab_layout, title="calibration")
