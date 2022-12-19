import time
from datetime import datetime
from functools import partial
from threading import Thread

import epics
import numpy as np
from bokeh.layouts import column, gridplot, row
from bokeh.models import Button, ColumnDataSource, Select, Spacer, Spinner, TabPanel, Whisker
from bokeh.plotting import curdoc, figure
from cam_server_client import PipelineClient
from scipy.optimize import curve_fit
from uncertainties import unumpy

from photodiag_web import DEVICES, push_elog

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

    def on_value_change(pv=None, ichannel=None, value=None, **_):
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
    motor = epics.Motor(pv_name)

    scan_mean = []
    scan_std = []
    scan_all = []

    for pos in scan_range:
        val = motor.move(pos, wait=True)
        if val != 0:
            raise ValueError(f"Error moving the motor {pv_name}, error value {val}")

        data = PBPS_get_data(channels, numShots)
        scan_mean.append([i.mean() for i in data])
        scan_std.append([i.std() for i in data])
        scan_all.append(data)

    motor.move(0, wait=True)

    return np.asarray(scan_mean), np.asarray(scan_std), np.asarray(scan_all)


def PBPS_I_calibrate(channels, numShots):
    data = PBPS_get_data(channels, numShots)
    scan_mean = np.array([i.mean() for i in data])
    scan_std = np.array([i.std() for i in data])
    scan_all = np.array(data)

    return scan_mean, scan_std, scan_all


def lin_fit(x, m, a):
    return m * x + a


def fit(xdata, ydata):
    popt, pcov = curve_fit(lin_fit, xdata, ydata)
    return popt


def _get_device_name():
    return config["name"][:-5]  # remove "_proc" suffix


def _set_epics_PV(name, value):
    epics.PV(f"{_get_device_name()}:{name}").put(bytes(str(value), "utf8"))


def create():
    doc = curdoc()
    log = doc.logger

    # horiz figure
    horiz_fig = figure(
        title=" ",
        y_axis_label=r"$$I_r-I_l/I_r+I_l$$",
        height=500,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    horiz_scatter_source = ColumnDataSource(dict(x=[], y=[], upper=[], lower=[]))
    horiz_fig.circle(source=horiz_scatter_source, legend_label="data")
    # TODO: fix errorbars
    horiz_fig.add_layout(
        Whisker(base="x", upper="upper", lower="lower", source=horiz_scatter_source, visible=False)
    )

    horiz_line_source = ColumnDataSource(dict(x=[], y=[]))
    horiz_fig.line(source=horiz_line_source, legend_label="fit")

    horiz_fig.plot.legend.click_policy = "hide"

    # vert_plot
    vert_fig = figure(
        title=" ",
        y_axis_label=r"$$I_u-I_d/I_u+I_d$$",
        height=500,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    vert_scatter_source = ColumnDataSource(dict(x=[], y=[], upper=[], lower=[]))
    vert_fig.circle(source=vert_scatter_source, legend_label="data")
    vert_fig.add_layout(
        Whisker(base="x", upper="upper", lower="lower", source=vert_scatter_source, visible=False)
    )

    vert_line_source = ColumnDataSource(dict(x=[], y=[]))
    vert_fig.line(source=vert_line_source, legend_label="fit")

    vert_fig.plot.legend.click_policy = "hide"

    def _update_plots():
        calib_datetime = config.get("calib_datetime", "")
        x_range = np.array(config.get("calib_x_range", []))
        x_norm = np.array(config.get("calib_x_norm", []))
        x_norm_std = np.array(config.get("calib_x_norm_std", []))
        y_range = np.array(config.get("calib_y_range", []))
        y_norm = np.array(config.get("calib_y_norm", []))
        y_norm_std = np.array(config.get("calib_y_norm_std", []))

        device_name = _get_device_name()
        title = f"{device_name}, {calib_datetime}"
        horiz_fig.title.text = title
        vert_fig.title.text = title

        horiz_fig.xaxis.axis_label = f"{device_name}:MOTOR_X1"
        vert_fig.xaxis.axis_label = f"{device_name}:MOTOR_Y1"

        # Update data
        x_upper = x_norm + x_norm_std if x_norm_std.size > 0 else x_norm
        x_lower = x_norm - x_norm_std if x_norm_std.size > 0 else x_norm
        horiz_scatter_source.data.update(x=x_range, y=x_norm, upper=x_upper, lower=x_lower)

        y_upper = y_norm + y_norm_std if y_norm_std.size > 0 else y_norm
        y_lower = y_norm - y_norm_std if y_norm_std.size > 0 else y_norm
        vert_scatter_source.data.update(x=y_range, y=y_norm, upper=y_upper, lower=y_lower)

        # Update fits
        if x_range.size and x_norm.size:
            horiz_line_source.data.update(x=x_range, y=lin_fit(x_range, *fit(x_range, x_norm)))
        else:
            horiz_line_source.data.update(x=[], y=[])

        if y_range.size and y_norm.size:
            vert_line_source.data.update(x=y_range, y=lin_fit(y_range, *fit(y_range, y_norm)))
        else:
            vert_line_source.data.update(x=[], y=[])

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
        config = client.get_pipeline_config(new + "_proc")
        device_name = _get_device_name()

        # get target options
        targets_pv = epics.PV(f"{device_name}:PROBE_SP")
        targets = list(targets_pv.enum_strs)
        target_select.options = targets
        target_select.value = targets[targets_pv.value]
        targets_pv.add_callback(_probe_sp_callback)

        # set IN_POS callback control
        in_pos_pv = epics.PV(f"{device_name}:IN_POS")
        in_pos_pv.add_callback(_in_pos_callback)

        _update_plots()

    device_select = Select(title="Device:", options=DEVICES)
    device_select.on_change("value", device_select_callback)

    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=500, step=100, low=100)

    async def _lock_gui():
        device_select.disabled = True
        num_shots_spinner.disabled = True
        target_select.disabled = True
        calibrate_button.disabled = True
        push_results_button.disabled = True
        push_elog_button.disabled = True

    async def _unlock_gui():
        device_select.disabled = False
        num_shots_spinner.disabled = False
        target_select.disabled = False
        calibrate_button.disabled = False
        push_results_button.disabled = False
        push_elog_button.disabled = False

    def _calibrate():
        device_name = _get_device_name()
        numShots = num_shots_spinner.value
        channels = [config["down"], config["up"], config["right"], config["left"]]
        calib_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        I_mean, I_std, _ = PBPS_I_calibrate(channels, numShots)
        u_I = unumpy.uarray(I_mean, I_std)
        u_I_norm = 1 / u_I / 4
        log.info("Diode response calibrated")

        pv_x_name = f"{device_name}:MOTOR_X1"
        try:
            x_mean, x_std, _ = pv_scan(pv_x_name, scan_x_range, channels, numShots)
        except ValueError as e:
            log.error(e)
            doc.add_next_tick_callback(_unlock_gui)
            return
        else:
            log.info("Horizontal position calibrated")

        u_x = unumpy.uarray(x_mean, x_std)

        pv_y_name = f"{device_name}:MOTOR_Y1"
        try:
            y_mean, y_std, _ = pv_scan(pv_y_name, scan_y_range, channels, numShots)
        except ValueError as e:
            log.error(e)
            doc.add_next_tick_callback(_unlock_gui)
            return
        else:
            log.info("Vertical position calibrated")

        u_y = unumpy.uarray(y_mean, y_std)

        u_x_norm = (u_x[:, 3] * u_I_norm[3] - u_x[:, 2] * u_I_norm[2]) / (
            u_x[:, 3] * u_I_norm[3] + u_x[:, 2] * u_I_norm[2]
        )

        u_y_norm = (u_y[:, 1] * u_I_norm[1] - u_y[:, 0] * u_I_norm[0]) / (
            u_y[:, 1] * u_I_norm[1] + u_y[:, 0] * u_I_norm[0]
        )

        x_norm_std = unumpy.std_devs(u_x_norm)
        x_norm = unumpy.nominal_values(u_x_norm)
        y_norm_std = unumpy.std_devs(u_y_norm)
        y_norm = unumpy.nominal_values(u_y_norm)
        I_norm = unumpy.nominal_values(u_I_norm)

        # Update config
        config["down_calib"] = I_norm[0]
        config["up_calib"] = I_norm[1]
        config["right_calib"] = I_norm[2]
        config["left_calib"] = I_norm[3]
        config["vert_calib"] = (scan_y_range[1] - scan_y_range[0]) / np.diff(y_norm).mean()
        config["horiz_calib"] = (scan_x_range[1] - scan_x_range[0]) / np.diff(x_norm).mean()
        config["calib_x_range"] = scan_x_range.tolist()
        config["calib_x_norm"] = x_norm.tolist()
        config["calib_x_norm_std"] = x_norm_std.tolist()
        config["calib_y_range"] = scan_y_range.tolist()
        config["calib_y_norm"] = y_norm.tolist()
        config["calib_y_norm_std"] = y_norm_std.tolist()
        config["calib_datetime"] = calib_datetime

        doc.add_next_tick_callback(_update_plots)
        doc.add_next_tick_callback(_unlock_gui)

    def calibrate_button_callback():
        doc.add_next_tick_callback(_lock_gui)

        thread = Thread(target=_calibrate)
        thread.start()

    calibrate_button = Button(label="Calibrate", button_type="primary")
    calibrate_button.on_click(calibrate_button_callback)

    def push_results_button_callback():
        if device_select.value not in ("SAROP31-PBPS113", "SAROP31-PBPS149"):
            device_name = _get_device_name()
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
            _set_epics_PV("YPOS.INPJ", f"{device_name}:INTENSITY")
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
            _set_epics_PV("XPOS.INPJ", f"{device_name}:INTENSITY")
            # Calculation
            _set_epics_PV("XPOS.CALC", "J<D?G:I*(A*E-B*F)/(A*E+B*F)")
            log.info("EPICS PVs updated")

        # Push position calibration to pipeline
        pipeline_name = config["name"]
        client.save_pipeline_config(pipeline_name, config)
        client.stop_instance(pipeline_name)
        log.info("camera_server config updated")

    push_results_button = Button(label="Push results")
    push_results_button.on_click(push_results_button_callback)

    def push_elog_button_callback():
        calib_res = [
            f"{key} = {config[key]}"
            for key in (
                "up_calib",
                "down_calib",
                "left_calib",
                "right_calib",
                "horiz_calib",
                "vert_calib",
            )
        ]

        msg_id = push_elog(
            figures=((horiz_fig, "horiz.png"), (vert_fig, "vert.png")),
            message="\n".join(calib_res),
            attributes={
                "Author": "sf-photodiag",
                "Entry": "Configuration",
                "Domain": "ARAMIS",
                "System": "Diagnostics",
                "Title": _get_device_name(),
            },
        )
        log.info(f"Logbook entry created: https://elog-gfa.psi.ch/SF-Photonics-Data/{msg_id}")

    push_elog_button = Button(label="Push elog")
    push_elog_button.on_click(push_elog_button_callback)

    # Trigger the initial device selection
    device_select.value = DEVICES[0]

    tab_layout = column(
        gridplot([[horiz_fig, vert_fig]], toolbar_options={"logo": None}),
        row(
            device_select,
            num_shots_spinner,
            target_select,
            column(Spacer(height=18), row(calibrate_button, push_results_button, push_elog_button)),
        ),
    )

    return TabPanel(child=tab_layout, title="calibration")
