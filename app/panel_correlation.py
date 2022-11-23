from collections import deque
from threading import Thread

import bsread
import numpy as np
from bokeh.layouts import column, row
from bokeh.models import Button, ColumnDataSource, Select, Spacer, Spinner, TabPanel, Toggle
from bokeh.plotting import curdoc, figure

from photodiag_web import DEVICES


def create():
    device_select = Select(title="Device:", value=DEVICES[0], options=DEVICES)
    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)
    device2_select = Select(title="Device #2:", value=DEVICES[1], options=DEVICES)

    # xcorr figure
    xcorr_plot = figure(
        x_axis_label="XPOS",
        y_axis_label="XPOS2",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    xcorr_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    xcorr_plot.circle(x="x", y="y", source=xcorr_even_scatter_source, legend_label="even")

    xcorr_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    xcorr_plot.circle(
        x="x",
        y="y",
        source=xcorr_odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    xcorr_plot.toolbar.logo = None
    xcorr_plot.plot.legend.click_policy = "hide"

    # ycorr figure
    ycorr_plot = figure(
        x_axis_label="YPOS",
        y_axis_label="YPOS2",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    ycorr_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    ycorr_plot.circle(x="x", y="y", source=ycorr_even_scatter_source, legend_label="even")

    ycorr_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    ycorr_plot.circle(
        x="x",
        y="y",
        source=ycorr_odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    ycorr_plot.toolbar.logo = None
    ycorr_plot.plot.legend.click_policy = "hide"

    # icorr figure
    icorr_plot = figure(
        x_axis_label="INT",
        y_axis_label="INT2",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    icorr_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    icorr_plot.circle(x="x", y="y", source=icorr_even_scatter_source, legend_label="even")

    icorr_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    icorr_plot.circle(
        x="x",
        y="y",
        source=icorr_odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    icorr_plot.toolbar.logo = None
    icorr_plot.plot.legend.click_policy = "hide"

    buffer = None

    def collect_data():
        nonlocal buffer
        buffer = deque(maxlen=num_shots_spinner.value)

        device_name = device_select.value
        device2_name = device2_select.value
        intensity = device_name + ":INTENSITY"
        intensity2 = device2_name + ":INTENSITY"
        xpos = device_name + ":XPOS"
        xpos2 = device2_name + ":XPOS"
        ypos = device_name + ":YPOS"
        ypos2 = device2_name + ":YPOS"

        with bsread.source(channels=[intensity, xpos, ypos, intensity2, xpos2, ypos2]) as stream:
            while update_toggle.active:
                message = stream.receive()
                is_odd = message.data.pulse_id % 2
                data = message.data.data
                buffer.append(
                    (
                        is_odd,
                        data[xpos].value,
                        data[ypos].value,
                        data[intensity].value,
                        data[xpos2].value,
                        data[ypos2].value,
                        data[intensity2].value,
                    )
                )

    async def update_plots():
        if not buffer:
            return

        data_array = np.array(buffer)
        is_even = data_array[:, 0] == 0
        data_even = data_array[is_even, :]
        data_odd = data_array[~is_even, :]

        xcorr_even_scatter_source.data.update(x=data_even[:, 1], y=data_even[:, 4])
        ycorr_even_scatter_source.data.update(x=data_even[:, 2], y=data_even[:, 5])
        icorr_even_scatter_source.data.update(x=data_even[:, 3], y=data_even[:, 6])

        xcorr_odd_scatter_source.data.update(x=data_odd[:, 1], y=data_odd[:, 4])
        ycorr_odd_scatter_source.data.update(x=data_odd[:, 2], y=data_odd[:, 5])
        icorr_odd_scatter_source.data.update(x=data_odd[:, 3], y=data_odd[:, 6])

    device_select = Select(title="Device:", value=DEVICES[0], options=DEVICES)
    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)

    update_plots_periodic_callback = None

    def update_toggle_callback(_attr, _old, new):
        nonlocal update_plots_periodic_callback
        if new:
            thread = Thread(target=collect_data)
            thread.start()

            update_plots_periodic_callback = curdoc().add_periodic_callback(update_plots, 1000)

            device_select.disabled = True
            device2_select.disabled = True
            num_shots_spinner.disabled = True

            update_toggle.label = "Stop"
            update_toggle.button_type = "success"
        else:
            curdoc().remove_periodic_callback(update_plots_periodic_callback)

            device_select.disabled = False
            device2_select.disabled = False
            num_shots_spinner.disabled = False

            update_toggle.label = "Update"
            update_toggle.button_type = "primary"

    update_toggle = Toggle(label="Update", button_type="primary")
    update_toggle.on_change("active", update_toggle_callback)

    push_elog_button = Button(label="Push elog", disabled=True)

    tab_layout = column(
        row(xcorr_plot, ycorr_plot, icorr_plot),
        row(
            device_select,
            device2_select,
            num_shots_spinner,
            column(Spacer(height=18), row(update_toggle, push_elog_button)),
        ),
    )

    return TabPanel(child=tab_layout, title="correlation")
