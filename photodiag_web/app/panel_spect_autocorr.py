from collections import deque
from datetime import datetime
from functools import partial
from threading import Thread

import epics
import numpy as np
from bokeh.layouts import column, row
from bokeh.models import (
    Button,
    ColumnDataSource,
    Select,
    Spacer,
    Spinner,
    TabPanel,
    TextInput,
    Toggle,
)
from bokeh.plotting import curdoc, figure
from lmfit.models import ConstantModel, GaussianModel

from photodiag_web import SPECT_DEV_CONFIG, epics_collect_data, get_device_domain, push_elog

model = (
    GaussianModel(prefix="bkg_")
    + ConstantModel(prefix="const_")
    + GaussianModel(prefix="env_")
    + GaussianModel(prefix="spike_")
)
params = model.make_params(
    bkg_sigma=dict(value=9, min=8, max=11),
    bkg_center=dict(value=0, vary=False),
    bkg_amplitude=dict(value=1, min=0),
    env_sigma=dict(value=5, min=1, max=7),
    env_center=dict(value=0, vary=False),
    env_amplitude=dict(value=1, min=0),
    spike_sigma=dict(value=0.3, min=0.05, max=1.5),
    spike_center=dict(value=0, vary=False),
    spike_amplitude=dict(value=1, min=0),
    const_c=dict(value=0, min=0),
)


def motor_scan(pv_name, scan_range, channels, numShots):
    motor = epics.Motor(pv_name)
    motor_init = motor.get_position()

    scan_mean = []

    for pos in scan_range:
        val = motor.move(pos, wait=True)
        if val != 0:
            if val == -12:
                raise ValueError(f"Motor position outside soft limits: {motor.LLM} {motor.HLM}")
            raise ValueError(f"Error moving the motor {pv_name}, error value {val}")

        data = epics_collect_data(channels, numShots)

        autocorr = []
        for wf in data[0]:
            autocorr.append(np.correlate(wf, wf, mode="same"))
        autocorr_mean = np.mean(autocorr, axis=0)
        scan_mean.append(autocorr_mean / np.max(autocorr_mean))

    motor.move(motor_init, wait=True)

    return np.asarray(scan_mean)


def pv_scan(pv_name, scan_range, channels, numShots):
    pv = epics.PV(pv_name)
    pv_init = pv.value
    scan_mean = []

    for pos in scan_range:
        pv.put(pos, wait=True)

        data = epics_collect_data(channels, numShots)

        autocorr = []
        for wf in data[0]:
            autocorr.append(np.correlate(wf, wf, mode="same"))
        autocorr_mean = np.mean(autocorr, axis=0)
        scan_mean.append(autocorr_mean / np.max(autocorr_mean))

    pv.put(pv_init, wait=True)

    return np.asarray(scan_mean)


def create(title):
    doc = curdoc()
    log = doc.logger

    fit_result = None

    config = SPECT_DEV_CONFIG
    devices = list(config.keys())

    pvs_x = {}
    pvs_y = {}
    pvs_m = {}
    for device in devices:
        pvs_x[device] = epics.PV(f"{device}:SPECTRUM_X")
        pvs_y[device] = epics.PV(f"{device}:SPECTRUM_Y")
        pvs_m[device] = epics.PV(config[device]["motor"])
    doc.pvs.extend([*pvs_x.values(), *pvs_y.values(), *pvs_m.values()])

    # single shot spectrum figure
    autocorr_fig = figure(
        height=250, width=1000, x_axis_label="Lags [eV]", tools="pan,wheel_zoom,save,reset"
    )

    autocorr_lines_source = ColumnDataSource(
        dict(x=[], y_autocorr=[], y_fit=[], y_bkg=[], y_const=[], y_env=[], y_spike=[])
    )
    autocorr_fig.line(source=autocorr_lines_source, y="y_autocorr", legend_label="Autocorrelation")
    autocorr_fig.line(
        source=autocorr_lines_source, y="y_fit", line_color="orange", legend_label="Fit"
    )
    autocorr_fig.line(
        source=autocorr_lines_source, y="y_bkg", line_color="green", legend_label="Background"
    )
    autocorr_fig.line(
        source=autocorr_lines_source, y="y_const", line_color="green", legend_label="Background"
    )
    autocorr_fig.line(
        source=autocorr_lines_source, y="y_env", line_color="red", legend_label="Spectral envelope"
    )
    autocorr_fig.line(
        source=autocorr_lines_source,
        y="y_spike",
        line_color="purple",
        legend_label="Spectral spike",
    )

    autocorr_fig.toolbar.logo = None
    autocorr_fig.legend.click_policy = "hide"
    autocorr_fig.y_range.only_visible = True

    # fwhm over time figure
    fwhm_fig = figure(
        height=250,
        width=1000,
        x_axis_label="Wall time",
        x_axis_type="datetime",
        y_axis_label="FWHM [eV]",
        tools="pan,wheel_zoom,save,reset",
    )

    fwhm_lines_source = ColumnDataSource(dict(x=[], fwhm_bkg=[], fwhm_env=[], fwhm_spike=[]))
    fwhm_fig.line(
        source=fwhm_lines_source, y="fwhm_bkg", line_color="green", legend_label="Background"
    )
    fwhm_fig.line(
        source=fwhm_lines_source, y="fwhm_env", line_color="red", legend_label="Spectral envelope"
    )
    fwhm_fig.line(
        source=fwhm_lines_source, y="fwhm_spike", line_color="purple", legend_label="Spectral spike"
    )

    fwhm_fig.toolbar.logo = None
    fwhm_fig.legend.click_policy = "hide"
    fwhm_fig.y_range.only_visible = True

    # calibration figure
    calib_fig = figure(
        height=500,
        width=500,
        x_axis_label="Position",
        y_axis_label="Spectral spike FWHM [eV]",
        tools="pan,wheel_zoom,save,reset",
    )

    calib_line_source = ColumnDataSource(dict(x=[], y=[]))
    calib_fig.line(source=calib_line_source)

    calib_fig.toolbar.logo = None

    lags = []
    buffer_autocorr = deque()

    def update_x(value, **_):
        nonlocal lags
        lags = value - value[int(value.size / 2)]
        buffer_autocorr.clear()

    def update_y(value, **_):
        buffer_autocorr.append(np.correlate(value, value, mode="same"))

    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)
    from_spinner = Spinner(title="From:")
    to_spinner = Spinner(title="To:")
    step_spinner = Spinner(title="Step:")
    motor_textinput = TextInput(title="Motor:", disabled=True, width=300)

    def pos_spinner_callback(_attr, _old, new):
        if new is not None and pvs_m[device_select.value].value != new:
            try:
                pvs_m[device_select.value].put(new, wait=True)
            except Exception as e:
                log.error(e)

    pos_spinner = Spinner(title="Postition:")
    pos_spinner.on_change("value", pos_spinner_callback)

    async def _update_pos(value):
        pos_spinner.value = value

    def _motor_callback(value, **_):
        doc.add_next_tick_callback(partial(_update_pos, value))

    update_plots_periodic_callback = None

    def update_toggle_callback(_attr, _old, new):
        nonlocal update_plots_periodic_callback, lags, buffer_autocorr
        pv_x = pvs_x[device_select.value]
        pv_y = pvs_y[device_select.value]
        if new:
            value = pv_x.value
            lags = value - value[int(value.size / 2)]
            buffer_autocorr = deque(maxlen=num_shots_spinner.value)

            pv_x.add_callback(update_x)
            pv_y.add_callback(update_y)

            update_plots_periodic_callback = doc.add_periodic_callback(_update_plots, 3000)
            doc.add_next_tick_callback(_lock_gui)

            update_toggle.label = "Stop"
            update_toggle.button_type = "success"
        else:
            pv_x.clear_callbacks()
            pv_y.clear_callbacks()

            doc.remove_periodic_callback(update_plots_periodic_callback)
            doc.add_next_tick_callback(_unlock_gui)

            update_toggle.label = "Update"
            update_toggle.button_type = "primary"

    update_toggle = Toggle(label="Update", button_type="primary")
    update_toggle.on_change("active", update_toggle_callback)

    async def _lock_gui():
        device_select.disabled = True
        num_shots_spinner.disabled = True
        from_spinner.disabled = True
        to_spinner.disabled = True
        step_spinner.disabled = True
        pos_spinner.disabled = True
        calibrate_button.disabled = True
        push_fit_elog_button.disabled = True
        push_calib_elog_button.disabled = True

    async def _unlock_gui():
        device_select.disabled = False
        num_shots_spinner.disabled = False
        from_spinner.disabled = False
        to_spinner.disabled = False
        step_spinner.disabled = False
        pos_spinner.disabled = False
        calibrate_button.disabled = False
        push_fit_elog_button.disabled = False
        push_calib_elog_button.disabled = False

    async def _lock_update():
        update_toggle.disabled = True

    async def _unlock_update():
        update_toggle.disabled = False

    async def _update_calib_plot(x, wfs):
        pv_x = pvs_x[device_select.value]
        value = pv_x.value
        lags = value - value[int(value.size / 2)]

        fwhm_spike = []
        for wf in wfs:
            fit_result = model.fit(wf, params, x=lags)
            fwhm_spike.append(fit_result.values["spike_fwhm"] / 1.4)

        calib_line_source.data.update(x=x, y=fwhm_spike)

    def _calibrate():
        device_name = device_select.value
        numShots = num_shots_spinner.value

        pv_name = motor_textinput.value
        scan_range = np.arange(from_spinner.value, to_spinner.value, step_spinner.value)
        channels = [f"{device_name}:SPECTRUM_Y"]

        # TODO: find a simpler way to scan PVs and Motors
        if device_name == "SARFE10-PSSS059":
            scan_func = motor_scan
        else:
            scan_func = pv_scan

        try:
            wf_mean = scan_func(pv_name, scan_range, channels, numShots)
        except ValueError as e:
            log.error(e)
            doc.add_next_tick_callback(_unlock_gui)
            doc.add_next_tick_callback(_unlock_update)
            return
        else:
            log.info(f"{device_name} calibrated")

        doc.add_next_tick_callback(partial(_update_calib_plot, x=scan_range, wfs=wf_mean))
        doc.add_next_tick_callback(_unlock_gui)
        doc.add_next_tick_callback(_unlock_update)

    def calibrate_button_callback():
        doc.add_next_tick_callback(_lock_gui)
        # extra lock update button
        doc.add_next_tick_callback(_lock_update)

        thread = Thread(target=_calibrate)
        thread.start()

    calibrate_button = Button(label="Calibrate", button_type="primary")
    calibrate_button.on_click(calibrate_button_callback)

    async def _update_plots():
        nonlocal fit_result
        if len(buffer_autocorr) < 4:
            autocorr_lines_source.data.update(
                x=[], y_autocorr=[], y_fit=[], y_bkg=[], y_const=[], y_env=[], y_spike=[]
            )
            fwhm_lines_source.data.update(x=[], fwhm_bkg=[], fwhm_env=[], fwhm_spike=[])
            return

        autocorr = np.array(buffer_autocorr)
        y_autocorr = autocorr.mean(axis=0)
        y_autocorr /= np.max(y_autocorr)

        fit_result = model.fit(y_autocorr, params, x=lags)
        y_fit = fit_result.best_fit

        components = fit_result.eval_components(x=lags)
        y_bkg = components["bkg_"]
        y_const = components["const_"]
        y_env = components["env_"]
        y_spike = components["spike_"]

        # Convert sigma of autocorrelation to fwhm of corresponding gaussian
        fwhm_bkg = fit_result.values["bkg_fwhm"] / 1.4
        fwhm_env = fit_result.values["env_fwhm"] / 1.4
        fwhm_spike = fit_result.values["spike_fwhm"] / 1.4

        # update glyph sources
        autocorr_lines_source.data.update(
            x=lags,
            y_autocorr=y_autocorr,
            y_fit=y_fit,
            y_bkg=y_bkg,
            y_const=y_const,
            y_env=y_env,
            y_spike=y_spike,
        )
        fwhm_lines_source.stream(
            dict(
                x=[datetime.now()],
                fwhm_bkg=[fwhm_bkg],
                fwhm_env=[fwhm_env],
                fwhm_spike=[fwhm_spike],
            ),
            rollover=3600,
        )

    def device_select_callback(_attr, _old, new):
        nonlocal lags
        # reset figures
        lags = []
        buffer_autocorr.clear()
        doc.add_next_tick_callback(_update_plots)
        doc.add_next_tick_callback(partial(_update_calib_plot, x=[], wfs=[]))

        # update default widget values
        dev_conf = config[new]
        from_spinner.value = dev_conf["from"]
        to_spinner.value = dev_conf["to"]
        step_spinner.value = dev_conf["step"]
        motor_textinput.value = dev_conf["motor"]

        # connect pos_spinner widget to the PV
        for pv in pvs_m.values():
            pv.clear_callbacks()

        pvs_m[new].add_callback(_motor_callback)
        pvs_m[new].run_callbacks()

    device_select = Select(title="Device:", options=devices)
    device_select.on_change("value", device_select_callback)
    device_select.value = devices[0]

    def push_fit_elog_button_callback():
        device_name = device_select.value
        domain = get_device_domain(device_name)

        msg_id = push_elog(
            figures=((autocorr_layout, "fit.png"),),
            message=fit_result.fit_report(),
            attributes={
                "Author": "sf-photodiag",
                "Entry": "Info",
                "Domain": domain,
                "System": "Diagnostics",
                "Title": f"{device_name} fit",
            },
        )
        log.info(
            f"Logbook entry created for {device_name}: "
            f"https://elog-gfa.psi.ch/SF-Photonics-Data/{msg_id}"
        )

    push_fit_elog_button = Button(label="Push fit elog")
    push_fit_elog_button.on_click(push_fit_elog_button_callback)

    def push_calib_elog_button_callback():
        device_name = device_select.value
        domain = get_device_domain(device_name)

        msg_id = push_elog(
            figures=((calib_layout, "calibration.png"),),
            message="",
            attributes={
                "Author": "sf-photodiag",
                "Entry": "Configuration",
                "Domain": domain,
                "System": "Diagnostics",
                "Title": f"{device_name} resolution",
            },
        )
        log.info(
            f"Logbook entry created for {device_name} callibration: "
            f"https://elog-gfa.psi.ch/SF-Photonics-Data/{msg_id}"
        )

    push_calib_elog_button = Button(label="Push calib elog")
    push_calib_elog_button.on_click(push_calib_elog_button_callback)

    autocorr_layout = column(autocorr_fig, fwhm_fig)
    calib_layout = calib_fig
    fig_layout = row(autocorr_layout, calib_layout)
    tab_layout = column(
        fig_layout,
        row(
            device_select,
            num_shots_spinner,
            column(
                Spacer(height=18),
                row(
                    Spacer(width=30),
                    update_toggle,
                    push_fit_elog_button,
                    Spacer(width=30),
                    calibrate_button,
                    push_calib_elog_button,
                ),
            ),
        ),
        row(motor_textinput, pos_spinner, from_spinner, to_spinner, step_spinner),
    )

    return TabPanel(child=tab_layout, title=title)
