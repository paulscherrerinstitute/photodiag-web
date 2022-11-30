import time
from datetime import datetime
from functools import partial
from threading import Thread

import epics
import numpy as np
from bokeh.layouts import column, row
from bokeh.models import Button, ColumnDataSource, Select, Spacer, Spinner, TabPanel, Whisker
from bokeh.plotting import curdoc, figure
from cam_server_client import PipelineClient
from scipy.optimize import curve_fit
from uncertainties import unumpy

from photodiag_web import DEVICES

scan_x_range = np.linspace(-0.3, 0.3, 3)
scan_y_range = np.linspace(-0.3, 0.3, 3)

client = PipelineClient()
config = None
targets_pv = None


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
    counters = np.zeros(len(channels), dtype=int)

    arrays = make_arrays(pvs, n_pulses)

    def on_value_change(pv=None, ichannel=None, value=None, **kwargs):
        ivalue = counters[ichannel]
        arrays[ichannel][ivalue] = value

        counters[ichannel] += 1

        if counters[ichannel] == n_pulses:
            pv.clear_callbacks()

    for i, pv in enumerate(pvs):
        pv.add_callback(callback=on_value_change, pv=pv, ichannel=i)

    while not np.all(counters == n_pulses):
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


def pv_scan(pv_name, scan_range, channels, numShots):
    pv = epics.PV(pv_name)

    scan_mean = []
    scan_std = []
    scan_all = []

    for pos in scan_range:
        pv.put(pos, wait=True)
        data = PBPS_get_data(channels, numShots)
        scan_mean.append([i.mean() for i in data])
        scan_std.append([i.std() for i in data])
        scan_all.append(data)

    pv.put(0, wait=True)

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


def _get_device_name():
    return config["name"][:-5]  # remove "_proc" suffix


def _get_device_prefix():
    return _get_device_name() + ":"


def _set_epics_PV(name, value):
    epics.PV(_get_device_prefix() + name).put(bytes(str(value), "utf8"))


def create():
    doc = curdoc()

    # horiz figure
    horiz_fig = figure(
        title=" ",
        x_axis_label="MOTOR_X1.VAL",
        y_axis_label=r"$$I_r-I_l/I_r+I_l$$",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    horiz_scatter_source = ColumnDataSource(dict(x=[], y=[], upper=[], lower=[]))
    horiz_fig.circle(x="x", y="y", source=horiz_scatter_source, legend_label="data")
    horiz_fig.add_layout(
        Whisker(base="x", upper="upper", lower="lower", source=horiz_scatter_source)
    )

    horiz_line_source = ColumnDataSource(dict(x=[], y=[]))
    horiz_fig.line(x="x", y="y", source=horiz_line_source, legend_label="fit")

    horiz_fig.toolbar.logo = None
    horiz_fig.plot.legend.click_policy = "hide"

    # vert_plot
    vert_fig = figure(
        title=" ",
        x_axis_label="MOTOR_Y1.VAL",
        y_axis_label=r"$$I_u-I_d/I_u+I_d$$",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    vert_scatter_source = ColumnDataSource(dict(x=[], y=[], upper=[], lower=[]))
    vert_fig.circle(x="x", y="y", source=vert_scatter_source, legend_label="data")
    vert_fig.add_layout(Whisker(base="x", upper="upper", lower="lower", source=vert_scatter_source))

    vert_line_source = ColumnDataSource(dict(x=[], y=[]))
    vert_fig.line(x="x", y="y", source=vert_line_source, legend_label="fit")

    vert_fig.toolbar.logo = None
    vert_fig.plot.legend.click_policy = "hide"

    def _update_plots(
        device, calib_datetime, x_range, x_norm, x_norm_std, y_range, y_norm, y_norm_std
    ):
        title = f"{device}, {calib_datetime}"
        horiz_fig.title.text = title
        vert_fig.title.text = title

        popt_norm_x = fit(x_range, x_norm)
        popt_norm_y = fit(y_range, y_norm)

        # Update plots
        x_upper = x_norm + x_norm_std if x_norm_std.size > 0 else x_norm
        x_lower = x_norm - x_norm_std if x_norm_std.size > 0 else x_norm
        horiz_scatter_source.data.update(x=x_range, y=x_norm, upper=x_upper, lower=x_lower)
        horiz_line_source.data.update(x=x_range, y=lin_fit(x_range, *popt_norm_x))

        y_upper = y_norm + y_norm_std if y_norm_std.size > 0 else y_norm
        y_lower = y_norm - y_norm_std if y_norm_std.size > 0 else y_norm
        vert_scatter_source.data.update(x=y_range, y=y_norm, upper=y_upper, lower=y_lower)
        vert_line_source.data.update(x=y_range, y=lin_fit(y_range, *popt_norm_y))

    def target_select_callback(_attr, _old, new):
        targets = list(targets_pv.enum_strs)
        if targets_pv.value != targets.index(new):
            targets_pv.put(targets.index(new), wait=True)

    target_select = Select(title="Target:")
    target_select.on_change("value", target_select_callback)

    def _in_pos_callback(value, **_):
        if value:
            doc.add_next_tick_callback(_unlock_gui)
        else:
            doc.add_next_tick_callback(_lock_gui)

    async def _update_target(value, enum_strs):
        target_select.value = enum_strs[value]

    def _probe_sp_callback(value, enum_strs, **_):
        doc.add_next_tick_callback(partial(_update_target, value, enum_strs))

    def device_select_callback(_attr, _old, new):
        global config, targets_pv
        config = client.get_instance_config(new + "_proc")

        # get target options
        targets_pv = epics.PV(_get_device_prefix() + "PROBE_SP")
        targets = list(targets_pv.enum_strs)
        target_select.options = targets
        target_select.value = targets[targets_pv.value]
        targets_pv.add_callback(_probe_sp_callback)

        # set IN_POS callback control
        in_pos_pv = epics.PV(_get_device_prefix() + "IN_POS")
        in_pos_pv.add_callback(_in_pos_callback)

        # load calibration, if present
        x_range = np.array(config.get("calib_x_range", []))
        x_norm = np.array(config.get("calib_x_norm", []))
        x_norm_std = np.array(config.get("calib_x_norm_std", []))
        y_range = np.array(config.get("calib_y_range", []))
        y_norm = np.array(config.get("calib_y_norm", []))
        y_norm_std = np.array(config.get("calib_y_norm_std", []))
        calib_datetime = config.get("calib_datetime", "")
        if x_range.size != 0 and x_norm.size != 0 and y_range.size != 0 and y_norm.size != 0:
            _update_plots(
                _get_device_name(),
                calib_datetime,
                x_range,
                x_norm,
                x_norm_std,
                y_range,
                y_norm,
                y_norm_std,
            )

    device_select = Select(title="Device:", options=DEVICES)
    device_select.on_change("value", device_select_callback)

    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=500, step=100, low=100)

    async def _lock_gui():
        device_select.disabled = True
        num_shots_spinner.disabled = True
        target_select.disabled = True
        calibrate_button.disabled = True
        push_results_button.disabled = True

    async def _unlock_gui():
        device_select.disabled = False
        num_shots_spinner.disabled = False
        target_select.disabled = False
        calibrate_button.disabled = False
        push_results_button.disabled = False

    async def _set_progress(step):
        if step != 3:
            calibrate_button.label = f"Step {step}/3"
        else:
            calibrate_button.label = "Calibrate"

        if step == 1:
            print("Diode response calibrated")
        elif step == 2:
            print("Horizontal position calibrated")
        elif step == 3:
            print("Vertical position calibrated")

    def _calibrate():
        numShots = num_shots_spinner.value
        channels = [config["down"], config["up"], config["right"], config["left"]]
        calib_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("-----", calib_datetime)
        doc.add_next_tick_callback(partial(_set_progress, 0))

        scan_I_mean, scan_I_std, _ = PBPS_I_calibrate(channels, numShots)
        scan_I = unumpy.uarray(scan_I_mean, scan_I_std)
        norm_diodes = np.asarray([1 / tm / 4 for tm in scan_I])
        doc.add_next_tick_callback(partial(_set_progress, 1))

        pv_x_name = _get_device_prefix() + "MOTOR_X1.VAL"
        scan_x_mean, scan_x_std, _ = pv_scan(pv_x_name, scan_x_range, channels, numShots)
        scan_x = unumpy.uarray(scan_x_mean, scan_x_std)
        doc.add_next_tick_callback(partial(_set_progress, 2))

        pv_y_name = _get_device_prefix() + "MOTOR_Y1.VAL"
        scan_y_mean, scan_y_std, _ = pv_scan(pv_y_name, scan_y_range, channels, numShots)
        scan_y = unumpy.uarray(scan_y_mean, scan_y_std)
        doc.add_next_tick_callback(partial(_set_progress, 3))

        scan_x_norm = (scan_x[:, 3] * norm_diodes[0, 3] - scan_x[:, 2] * norm_diodes[0, 2]) / (
            scan_x[:, 3] * norm_diodes[0, 3] + scan_x[:, 2] * norm_diodes[0, 2]
        )

        scan_y_norm = (scan_y[:, 1] * norm_diodes[0, 1] - scan_y[:, 0] * norm_diodes[0, 0]) / (
            scan_y[:, 1] * norm_diodes[0, 1] + scan_y[:, 0] * norm_diodes[0, 0]
        )

        scan_x_norm_std = unumpy.std_devs(scan_x_norm)
        scan_x_norm = unumpy.nominal_values(scan_x_norm)
        scan_y_norm_std = unumpy.std_devs(scan_y_norm)
        scan_y_norm = unumpy.nominal_values(scan_y_norm)
        norm_diodes = unumpy.nominal_values(norm_diodes)

        doc.add_next_tick_callback(
            partial(
                _update_plots,
                _get_device_name(),
                calib_datetime,
                scan_x_range,
                scan_x_norm,
                scan_x_norm_std,
                scan_y_range,
                scan_y_norm,
                scan_y_norm_std,
            )
        )

        # Update config
        config["down_calib"] = norm_diodes[0, 0]
        config["up_calib"] = norm_diodes[0, 1]
        config["right_calib"] = norm_diodes[0, 2]
        config["left_calib"] = norm_diodes[0, 3]
        config["vert_calib"] = (scan_y_range[1] - scan_y_range[0]) / np.diff(scan_y_norm).mean()
        config["horiz_calib"] = (scan_x_range[1] - scan_x_range[0]) / np.diff(scan_x_norm).mean()
        config["calib_x_range"] = scan_x_range.tolist()
        config["calib_x_norm"] = scan_x_norm.tolist()
        config["calib_x_norm_std"] = scan_x_norm_std.tolist()
        config["calib_y_range"] = scan_y_range.tolist()
        config["calib_y_norm"] = scan_y_norm.tolist()
        config["calib_y_norm_std"] = scan_y_norm_std.tolist()
        config["calib_datetime"] = calib_datetime

        doc.add_next_tick_callback(_unlock_gui)

    def calibrate_button_callback():
        doc.add_next_tick_callback(_lock_gui)

        thread = Thread(target=_calibrate)
        thread.start()

    calibrate_button = Button(label="Calibrate", button_type="primary")
    calibrate_button.on_click(calibrate_button_callback)

    def push_results_button_callback():
        if device_select.value not in ("SAROP31-PBPS113", "SAROP31-PBPS149"):
            dev_pref = _get_device_prefix()
            # Intensity
            # Set channels
            # Input data
            _set_epics_PV("INTENSITY.INPA", config["down"])
            _set_epics_PV("INTENSITY.INPB", config["up"])
            _set_epics_PV("INTENSITY.INPC", config["right"])
            _set_epics_PV("INTENSITY.INPD", config["left"])
            # Calibration values
            _set_epics_PV("INTENSITY.E", config["down_calib"])
            _set_epics_PV("INTENSITY.F", config["up_calib"])
            _set_epics_PV("INTENSITY.G", config["right_calib"])
            _set_epics_PV("INTENSITY.H", config["left_calib"])
            # Calculation
            _set_epics_PV("INTENSITY.CALC", "A*E+B*F+C*G+D*H")

            # YPOS
            # Set channels
            _set_epics_PV("YPOS.INPA", config["down"])
            _set_epics_PV("YPOS.INPB", config["up"])
            # Threshold value
            _set_epics_PV("YPOS.D", 0.2)
            # Diode calibration value
            _set_epics_PV("YPOS.E", config["down_calib"])
            _set_epics_PV("YPOS.F", config["up_calib"])
            # Null value
            _set_epics_PV("YPOS.G", 0)
            # Position calibration value
            _set_epics_PV("YPOS.I", config["vert_calib"])
            # Intensity threshold value
            _set_epics_PV("YPOS.INPJ", dev_pref + "INTENSITY")
            # Calculation
            _set_epics_PV("YPOS.CALC", "J<D?G:I*(A*E-B*F)/(A*E+B*F)")

            # XPOS
            # Set channels
            _set_epics_PV("XPOS.INPA", config["right"])
            _set_epics_PV("XPOS.INPB", config["left"])
            # Threshold value
            _set_epics_PV("XPOS.D", 0.2)
            # Diode calibration value
            _set_epics_PV("XPOS.E", config["right_calib"])
            _set_epics_PV("XPOS.F", config["left_calib"])
            # Null value
            _set_epics_PV("XPOS.G", 0)
            # Position calibration value
            _set_epics_PV("XPOS.I", config["horiz_calib"])
            # Intensity threshold value
            _set_epics_PV("XPOS.INPJ", dev_pref + "INTENSITY")
            # Calculation
            _set_epics_PV("XPOS.CALC", "J<D?G:I*(A*E-B*F)/(A*E+B*F)")

        # Push position calibration to pipeline
        pipeline_name = config["name"]
        config["queue_length"] = 5000
        client.save_pipeline_config(pipeline_name, config)
        client.stop_instance(pipeline_name)

    push_results_button = Button(label="Push results")
    push_results_button.on_click(push_results_button_callback)

    push_elog_button = Button(label="Push elog", disabled=True)

    # Trigger the initial device selection
    device_select.value = DEVICES[0]

    tab_layout = column(
        row(horiz_fig, vert_fig),
        row(
            device_select,
            num_shots_spinner,
            target_select,
            column(Spacer(height=18), row(calibrate_button, push_results_button, push_elog_button)),
        ),
    )

    return TabPanel(child=tab_layout, title="calibration")
