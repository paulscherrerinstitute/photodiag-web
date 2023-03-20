from collections import deque
from threading import Thread

import bsread
import numpy as np
from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, Select, Spacer, Spinner, TabPanel, Toggle
from bokeh.plotting import curdoc, figure
from scipy.signal import find_peaks


def create(title, devices):
    doc = curdoc()
    log = doc.logger

    device_name = ""
    device_channels = ("", "")

    # single shot spectrum figure
    single_shot_fig = figure(
        height=250, width=1000, x_axis_label="Photon energy [eV]", tools="pan,wheel_zoom,save,reset"
    )
    single_shot_fig.toolbar.logo = None

    single_shot_line_source = ColumnDataSource(dict(x=[], y=[]))
    single_shot_fig.line(source=single_shot_line_source, legend_label="Spectrum")

    single_shot_smooth_line_source = ColumnDataSource(dict(x=[], y=[]))
    single_shot_fig.line(
        source=single_shot_smooth_line_source, line_color="orange", legend_label="Smoothed"
    )

    # gradient figure
    gradient_fig = figure(
        height=250, width=1000, x_axis_label="Photon energy [eV]", tools="pan,wheel_zoom,save,reset"
    )
    gradient_fig.toolbar.logo = None

    gradient_line_source = ColumnDataSource(dict(x=[], y=[]))
    gradient_fig.line(source=gradient_line_source, legend_label="Abs of gradient")

    peak_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    gradient_fig.x(source=peak_scatter_source, color="orange", size=10, legend_label="Peaks")

    # number of peaks distribution figure
    num_peaks_dist_fig = figure(
        height=500,
        width=500,
        x_axis_label="Number of peaks",
        y_axis_label="Number of shots",
        tools="pan,wheel_zoom,save,reset",
    )
    num_peaks_dist_fig.toolbar.logo = None

    num_peaks_dist_quad_source = ColumnDataSource(dict(left=[], right=[], top=[]))
    num_peaks_dist_fig.quad(source=num_peaks_dist_quad_source, bottom=0)

    single_shot_cache = [[], [], [], [], 0]
    buffer_num_peaks = deque()

    def _collect_data():
        nonlocal single_shot_cache, buffer_num_peaks
        single_shot_cache = [[], [], [], [], 0]
        buffer_num_peaks = deque(maxlen=num_shots_spinner.value)

        kernel_size = kernel_size_spinner.value
        kernel = np.ones(kernel_size) / kernel_size
        peak_dist = peak_dist_spinner.value
        peak_height = peak_height_spinner.value

        try:
            with bsread.source(channels=device_channels) as stream:
                while update_toggle.active:
                    message = stream.receive()
                    values = [message.data.data[ch].value for ch in device_channels]
                    if not any(val is None for val in values):
                        spec_x, spec_y = values
                        spec_y = spec_y / np.max(spec_y)
                        spec_y_convolved = np.convolve(spec_y, kernel, mode="same")
                        spec_y_grad = np.abs(np.gradient(spec_y_convolved))
                        peaks, _ = find_peaks(spec_y_grad, distance=peak_dist, height=peak_height)

                        single_shot_cache = [spec_x, spec_y, spec_y_convolved, spec_y_grad, peaks]
                        buffer_num_peaks.append(len(peaks) / 2)

        except Exception as e:
            log.error(e)

    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)
    kernel_size_spinner = Spinner(title="Kernel size:", mode="int", value=100, low=1)
    peak_dist_spinner = Spinner(title="Peak min distance:", mode="int", value=100, low=1)
    peak_height_spinner = Spinner(title="Peak min height:", mode="float", value=0.002)

    update_plots_periodic_callback = None

    def update_toggle_callback(_attr, _old, new):
        nonlocal update_plots_periodic_callback
        if new:
            thread = Thread(target=_collect_data)
            thread.start()

            update_plots_periodic_callback = doc.add_periodic_callback(_update_plots, 1000)

            device_select.disabled = True
            num_shots_spinner.disabled = True
            kernel_size_spinner.disabled = True
            peak_dist_spinner.disabled = True
            peak_height_spinner.disabled = True

            update_toggle.label = "Stop"
            update_toggle.button_type = "success"
        else:
            doc.remove_periodic_callback(update_plots_periodic_callback)

            device_select.disabled = False
            num_shots_spinner.disabled = False
            kernel_size_spinner.disabled = False
            peak_dist_spinner.disabled = False
            peak_height_spinner.disabled = False

            update_toggle.label = "Update"
            update_toggle.button_type = "primary"

    update_toggle = Toggle(label="Update", button_type="primary")
    update_toggle.on_change("active", update_toggle_callback)

    async def _update_plots():
        if len(buffer_num_peaks) < 3:
            num_peaks_dist_quad_source.data.update(left=[], right=[], top=[])
            return

        spec_x, spec_y, spec_y_convolved, spec_y_grad, peaks = single_shot_cache

        num_peaks = np.array(buffer_num_peaks)
        # this way it includes the max number of peaks in the range
        bins = np.arange(num_peaks.min() - 0.25, num_peaks.max() + 0.5, 0.5)
        counts, edges = np.histogram(num_peaks, bins=bins)

        # update glyph sources
        single_shot_line_source.data.update(x=spec_x, y=spec_y)
        single_shot_smooth_line_source.data.update(x=spec_x, y=spec_y_convolved)
        gradient_line_source.data.update(x=spec_x, y=spec_y_grad)
        peak_scatter_source.data.update(x=spec_x[peaks], y=spec_y_grad[peaks])
        num_peaks_dist_quad_source.data.update(left=edges[:-1], right=edges[1:], top=counts)

    def device_select_callback(_attr, _old, new):
        nonlocal device_name, device_channels, single_shot_cache
        device_name = new
        device_channels = f"{device_name}:SPECTRUM_X", f"{device_name}:SPECTRUM_Y"

        # reset figures
        single_shot_cache = [[], [], [], [], 0]
        buffer_num_peaks.clear()
        doc.add_next_tick_callback(_update_plots)

    device_select = Select(title="Device:", options=devices)
    device_select.on_change("value", device_select_callback)
    device_select.value = devices[0]

    fig_layout = row(column(single_shot_fig, gradient_fig), num_peaks_dist_fig)
    tab_layout = column(
        fig_layout,
        row(
            device_select,
            num_shots_spinner,
            kernel_size_spinner,
            peak_dist_spinner,
            peak_height_spinner,
            column(Spacer(height=18), update_toggle),
        ),
    )

    return TabPanel(child=tab_layout, title=title)
