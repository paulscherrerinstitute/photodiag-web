from collections import deque
from datetime import datetime

import epics
import numpy as np
from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, Select, Spacer, Spinner, TabPanel, Toggle
from bokeh.plotting import curdoc, figure
from lmfit.models import GaussianModel

model = GaussianModel(prefix="bkg_") + GaussianModel(prefix="env_") + GaussianModel(prefix="spike_")
params = model.make_params(
    bkg_sigma=dict(value=9, min=8, max=11),
    bkg_center=dict(value=0, vary=False),
    env_sigma=dict(value=5, min=4, max=7),
    env_center=dict(value=0, vary=False),
    spike_sigma=dict(value=0.3, min=0.05, max=1.5),
    spike_center=dict(value=0, vary=False),
)


def create(title, devices):
    doc = curdoc()
    log = doc.logger

    pvs_x = {}
    pvs_y = {}
    for device in devices:
        pvs_x[device] = epics.PV(f"{device}:SPECTRUM_X")
        pvs_y[device] = epics.PV(f"{device}:SPECTRUM_Y")
    doc.pvs.extend([*pvs_x.values(), *pvs_y.values()])

    # single shot spectrum figure
    autocorr_fig = figure(
        height=250, width=1000, x_axis_label="Photon energy [eV]", tools="pan,wheel_zoom,save,reset"
    )
    autocorr_fig.toolbar.logo = None

    autocorr_lines_source = ColumnDataSource(
        dict(x=[], y_autocorr=[], y_fit=[], y_bkg=[], y_env=[], y_spike=[])
    )
    autocorr_fig.line(source=autocorr_lines_source, y="y_autocorr", legend_label="Autocorrelation")
    autocorr_fig.line(
        source=autocorr_lines_source, y="y_fit", line_color="orange", legend_label="Fit"
    )
    autocorr_fig.line(
        source=autocorr_lines_source, y="y_bkg", line_color="green", legend_label="Background"
    )
    autocorr_fig.line(
        source=autocorr_lines_source, y="y_env", line_color="red", legend_label="Spectral envelope"
    )
    autocorr_fig.line(
        source=autocorr_lines_source,
        y="y_spike",
        line_color="purple",
        legend_label="Spectral spike width",
    )

    # sigma over time figure
    sigma_fig = figure(
        height=250, width=1000, x_axis_type="datetime", tools="pan,wheel_zoom,save,reset"
    )
    sigma_fig.toolbar.logo = None

    sigma_lines_source = ColumnDataSource(dict(x=[], sigma_bkg=[], sigma_env=[], sigma_spike=[]))
    sigma_fig.line(
        source=sigma_lines_source, y="sigma_bkg", line_color="green", legend_label="Background"
    )
    sigma_fig.line(
        source=sigma_lines_source, y="sigma_env", line_color="red", legend_label="Spectral envelope"
    )
    sigma_fig.line(
        source=sigma_lines_source,
        y="sigma_spike",
        line_color="purple",
        legend_label="Spectral spike width",
    )

    lags = []
    buffer_num_peaks = deque()

    def update_x(value, **_):
        nonlocal lags
        lags = value - value[int(value.size / 2)]
        buffer_num_peaks.clear()

    def update_y(value, **_):
        buffer_num_peaks.append(value)

    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)
    from_spinner = Spinner(title="From:", mode="float", value=0, disabled=True)
    to_spinner = Spinner(title="To:", mode="float", value=1, disabled=True)
    num_steps_spinner = Spinner(title="Number of steps:", mode="int", value=10, disabled=True)

    update_plots_periodic_callback = None

    def update_toggle_callback(_attr, _old, new):
        nonlocal update_plots_periodic_callback, lags, buffer_num_peaks
        pv_x = pvs_x[device_select.value]
        pv_y = pvs_y[device_select.value]
        if new:
            value = pv_x.value
            lags = value - value[int(value.size / 2)]
            buffer_num_peaks = deque(maxlen=num_shots_spinner.value)
            buffer_num_peaks.append(pv_y.value)

            pv_x.add_callback(update_x)
            pv_y.add_callback(update_y)

            update_plots_periodic_callback = doc.add_periodic_callback(_update_plots, 3000)

            device_select.disabled = True
            num_shots_spinner.disabled = True
            from_spinner.disabled = True
            to_spinner.disabled = True
            num_steps_spinner.disabled = True

            update_toggle.label = "Stop"
            update_toggle.button_type = "success"
        else:
            pv_x.clear_callbacks()
            pv_y.clear_callbacks()

            doc.remove_periodic_callback(update_plots_periodic_callback)

            device_select.disabled = False
            num_shots_spinner.disabled = False
            # from_spinner.disabled = False
            # to_spinner.disabled = False
            # num_steps_spinner.disabled = False

            update_toggle.label = "Update"
            update_toggle.button_type = "primary"

    update_toggle = Toggle(label="Update", button_type="primary")
    update_toggle.on_change("active", update_toggle_callback)

    async def _update_plots():
        if len(buffer_num_peaks) < 4:
            autocorr_lines_source.data.update(
                x=[], y_autocorr=[], y_fit=[], y_bkg=[], y_env=[], y_spike=[]
            )
            sigma_lines_source.data.update(x=[], sigma_bkg=[], sigma_env=[], sigma_spike=[])
            return

        num_peaks = np.array(buffer_num_peaks)
        y_autocorr = num_peaks.mean(axis=0)
        y_autocorr /= np.max(y_autocorr)

        result = model.fit(y_autocorr, params, x=lags)
        y_fit = result.best_fit

        components = result.eval_components(x=lags)
        y_bkg = components["bkg_"]
        y_env = components["env_"]
        y_spike = components["spike_"]

        # Convert sigma of autocorrelation to sigma of corresponding gaussian
        sigma_bkg = result.values["bkg_sigma"] / 1.4
        sigma_env = result.values["env_sigma"] / 1.4
        sigma_spike = result.values["spike_sigma"] / 1.4

        # update glyph sources
        autocorr_lines_source.data.update(
            x=lags, y_autocorr=y_autocorr, y_fit=y_fit, y_bkg=y_bkg, y_env=y_env, y_spike=y_spike
        )
        sigma_lines_source.stream(
            dict(
                x=[datetime.now()],
                sigma_bkg=[sigma_bkg],
                sigma_env=[sigma_env],
                sigma_spike=[sigma_spike],
            )
        )

    def device_select_callback(_attr, _old, _new):
        nonlocal lags
        # reset figures
        lags = []
        buffer_num_peaks.clear()
        doc.add_next_tick_callback(_update_plots)

    device_select = Select(title="Device:", options=devices)
    device_select.on_change("value", device_select_callback)
    device_select.value = devices[0]

    fig_layout = column(autocorr_fig, sigma_fig)
    tab_layout = column(
        fig_layout,
        row(
            device_select,
            num_shots_spinner,
            from_spinner,
            to_spinner,
            num_steps_spinner,
            column(Spacer(height=18), update_toggle),
        ),
    )

    return TabPanel(child=tab_layout, title=title)
