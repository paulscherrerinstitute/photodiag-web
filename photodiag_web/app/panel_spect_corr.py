import logging
from collections import deque
from threading import Thread

import bsread
import numpy as np
from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, Spacer, Spinner, TabPanel, Toggle
from bokeh.plotting import curdoc, figure

log = logging.getLogger(__name__)


def pearson_1D(spectra, I0):
    diff1 = spectra - np.mean(spectra, axis=0)
    diff2 = I0[:, np.newaxis] - np.mean(I0)
    res = np.sum(diff1 * diff2, axis=0) / np.sqrt(np.sum(diff1**2, axis=0) * np.sum(diff2**2))
    return res


def spectra_bin_I0(I0, I0_bins, spectra):
    spectra_len = spectra.shape[1]
    spec_zero = np.zeros(spectra_len)
    spec_binned = np.empty((len(I0_bins), spectra_len))

    digi = np.digitize(I0, I0_bins)
    for i in range(0, len(I0_bins)):
        ind = digi == i + 1
        spec_binned[i, :] = spectra[ind, :].mean(axis=0) if any(ind) else spec_zero

    return spec_binned


def create():
    doc = curdoc()

    # correlation coefficient figure
    corr_coef_fig = figure(
        height=250,
        width=500,
        x_axis_label="Photon energy [eV]",
        y_axis_label="Correlation coefficient",
        tools="pan,wheel_zoom,save,reset",
    )
    corr_coef_fig.toolbar.logo = None

    corr_coef_line_source = ColumnDataSource(dict(x=[], y=[]))
    corr_coef_fig.line(source=corr_coef_line_source)

    # spectral instensity figure
    spec_int_fig = figure(
        height=250,
        width=500,
        x_axis_label="Photon energy [eV]",
        y_axis_label="Spectral intensity [arb]",
        tools="pan,wheel_zoom,save,reset",
    )
    spec_int_fig.toolbar.logo = None

    spec_int_line1_source = ColumnDataSource(dict(x=[], y=[]))
    spec_int_line2_source = ColumnDataSource(dict(x=[], y=[]))
    spec_int_line3_source = ColumnDataSource(dict(x=[], y=[]))
    spec_int_fig.line(source=spec_int_line1_source, legend_label="Max I0 bin")
    spec_int_fig.line(source=spec_int_line2_source, line_color="red", legend_label="Mid I0 bin")
    spec_int_fig.line(source=spec_int_line3_source, line_color="green", legend_label="Min I0 bin")

    # single shot intensity figure
    single_int_fig = figure(
        height=500,
        width=1000,
        x_axis_label="Photon energy [eV]",
        y_axis_label="Single shot intensity [arb]",
        tools="pan,wheel_zoom,save,reset",
    )
    single_int_fig.toolbar.logo = None

    single_int_image_source = ColumnDataSource(dict(image=[], x=[], y=[], dw=[], dh=[]))
    single_int_fig.image(source=single_int_image_source, palette="Magma256")

    cache_spec_x = []
    buffer_spec_y = deque()
    buffer_i0 = deque()

    def _collect_data():
        nonlocal cache_spec_x, buffer_spec_y, buffer_i0
        cache_spec_x = []
        buffer_spec_y = deque(maxlen=num_shots_spinner.value)
        buffer_i0 = deque(maxlen=num_shots_spinner.value)

        spec_x_ch = "SARFE10-PSSS059:SPECTRUM_X"
        spec_y_ch = "SARFE10-PSSS059:SPECTRUM_Y"
        i0_ch = "SARFE10-PBPS053:INTENSITY"

        with bsread.source(channels=[spec_x_ch, spec_y_ch, i0_ch]) as stream:
            while update_toggle.active:
                message = stream.receive()
                data = message.data.data
                spec_x = data[spec_x_ch].value
                spec_y = data[spec_y_ch].value
                i0 = data[i0_ch].value
                if spec_x is not None and spec_y is not None and i0 is not None:
                    cache_spec_x = spec_x
                    buffer_spec_y.append(spec_y)
                    buffer_i0.append(i0)

    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)

    update_plots_periodic_callback = None

    def update_toggle_callback(_attr, _old, new):
        nonlocal update_plots_periodic_callback
        if new:
            thread = Thread(target=_collect_data)
            thread.start()

            update_plots_periodic_callback = doc.add_periodic_callback(_update_plots, 1000)

            num_shots_spinner.disabled = True

            update_toggle.label = "Stop"
            update_toggle.button_type = "success"
        else:
            doc.remove_periodic_callback(update_plots_periodic_callback)

            num_shots_spinner.disabled = False

            update_toggle.label = "Update"
            update_toggle.button_type = "primary"

    update_toggle = Toggle(label="Update", button_type="primary")
    update_toggle.on_change("active", update_toggle_callback)

    async def _update_plots():
        if len(buffer_spec_y) < 3:
            corr_coef_line_source.data.update(x=[], y=[])
            spec_int_line1_source.data.update(x=[], y=[])
            spec_int_line2_source.data.update(x=[], y=[])
            spec_int_line3_source.data.update(x=[], y=[])
            single_int_image_source.data.update(image=[], x=[], y=[], dw=[], dh=[])
            return

        spec_x = cache_spec_x
        spec_y = np.array(buffer_spec_y)
        i0 = np.array(buffer_i0)

        min_int_bin = np.min(i0)
        max_int_bin = np.max(i0)
        bins = np.linspace(min_int_bin, max_int_bin, 20)
        mid_bin_ind = int(len(bins) / 2)

        pearson_coeff = pearson_1D(spec_y, i0)
        spectra_binned = spectra_bin_I0(i0, bins, spec_y)

        # update glyph sources
        corr_coef_line_source.data.update(x=spec_x, y=pearson_coeff)

        max_spectra = np.max(spectra_binned)
        spec_int_line1_source.data.update(x=spec_x, y=spectra_binned[-1, :] / max_spectra)
        spec_int_line2_source.data.update(x=spec_x, y=spectra_binned[mid_bin_ind, :] / max_spectra)
        spec_int_line3_source.data.update(x=spec_x, y=spectra_binned[0, :] / max_spectra)

        single_int_image_source.data.update(
            image=[spectra_binned],
            x=[spec_x[0]],
            dw=[spec_x[-1] - spec_x[0]],
            y=[min_int_bin],
            dh=[max_int_bin - min_int_bin],
        )

    fig_layout = row(column(corr_coef_fig, spec_int_fig), single_int_fig)
    tab_layout = column(
        fig_layout, row(num_shots_spinner, column(Spacer(height=18), update_toggle))
    )

    return TabPanel(child=tab_layout, title="spect-intensity corr")
