from collections import deque
from datetime import datetime
from threading import Thread

import bsread
import numpy as np
from bokeh.layouts import column, row
from bokeh.models import Button, ColumnDataSource, Select, Spacer, Spinner, TabPanel, Toggle
from bokeh.plotting import curdoc, figure

from photodiag_web import DEVICES, push_elog


def create():
    doc = curdoc()

    # xy figure
    xy_fig = figure(
        title=" ",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    even_scatter_source = ColumnDataSource(dict(x=[], y=[], i=[]))
    odd_scatter_source = ColumnDataSource(dict(x=[], y=[], i=[]))

    xy_fig.circle(x="x", y="y", source=even_scatter_source, legend_label="even")
    xy_fig.circle(
        x="x",
        y="y",
        source=odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    xy_fig.plot.toolbar.logo = None
    xy_fig.plot.legend.click_policy = "hide"

    # ix figure
    ix_fig = figure(
        title=" ",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    ix_fig.circle(x="i", y="x", source=even_scatter_source, legend_label="even")
    ix_fig.circle(
        x="i",
        y="x",
        source=odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    ix_fig.plot.toolbar.logo = None
    ix_fig.plot.legend.click_policy = "hide"

    # iy figure
    iy_fig = figure(
        title=" ",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    iy_fig.circle(x="i", y="y", source=even_scatter_source, legend_label="even")
    iy_fig.circle(
        x="i",
        y="y",
        source=odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    iy_fig.plot.toolbar.logo = None
    iy_fig.plot.legend.click_policy = "hide"

    buffer = None

    def collect_data():
        nonlocal buffer
        buffer = deque(maxlen=num_shots_spinner.value)

        device_name = device_select.value
        xpos = f"{device_name}:XPOS"
        ypos = f"{device_name}:YPOS"
        intensity = f"{device_name}:INTENSITY"

        with bsread.source(channels=[xpos, ypos, intensity]) as stream:
            while update_toggle.active:
                message = stream.receive()
                is_odd = message.data.pulse_id % 2
                data = message.data.data
                buffer.append((is_odd, data[xpos].value, data[ypos].value, data[intensity].value))

    async def update_plots():
        if not buffer:
            return

        device_name = device_select.value
        datetime_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = f"{device_name}, {datetime_now}"
        xy_fig.title.text = title
        ix_fig.title.text = title
        iy_fig.title.text = title

        data_array = np.array(buffer)
        is_even = data_array[:, 0] == 0
        data_even = data_array[is_even, :]
        data_odd = data_array[~is_even, :]

        even_scatter_source.data.update(x=data_even[:, 1], y=data_even[:, 2], i=data_even[:, 3])
        odd_scatter_source.data.update(x=data_odd[:, 1], y=data_odd[:, 2], i=data_odd[:, 3])

    device_select = Select(title="Device:", value=DEVICES[0], options=DEVICES)
    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)

    update_plots_periodic_callback = None

    def update_toggle_callback(_attr, _old, new):
        nonlocal update_plots_periodic_callback
        if new:
            thread = Thread(target=collect_data)
            thread.start()

            update_plots_periodic_callback = doc.add_periodic_callback(update_plots, 1000)

            device_name = device_select.value
            xpos = f"{device_name}:XPOS"
            ypos = f"{device_name}:YPOS"
            intensity = f"{device_name}:INTENSITY"

            xy_fig.xaxis.axis_label = xpos
            xy_fig.yaxis.axis_label = ypos
            ix_fig.xaxis.axis_label = intensity
            ix_fig.yaxis.axis_label = xpos
            iy_fig.xaxis.axis_label = intensity
            iy_fig.yaxis.axis_label = ypos

            device_select.disabled = True
            num_shots_spinner.disabled = True
            push_elog_button.disabled = True

            update_toggle.label = "Stop"
            update_toggle.button_type = "success"
        else:
            doc.remove_periodic_callback(update_plots_periodic_callback)

            device_select.disabled = False
            num_shots_spinner.disabled = False
            push_elog_button.disabled = False

            update_toggle.label = "Update"
            update_toggle.button_type = "primary"

    update_toggle = Toggle(label="Update", button_type="primary")
    update_toggle.on_change("active", update_toggle_callback)

    def push_elog_button_callback():
        push_elog(
            figures=((xy_fig, "xy.png"), (ix_fig, "ix.png"), (iy_fig, "iy.png")),
            message="",
            attributes={
                "Author": "sf-photodiag",
                "Entry": "Info",
                "Domain": "ARAMIS",
                "System": "Diagnostics",
                "Title": f"{device_select.value} jitter",
            },
        )

    push_elog_button = Button(label="Push elog")
    push_elog_button.on_click(push_elog_button_callback)

    tab_layout = column(
        row(xy_fig, ix_fig, iy_fig),
        row(
            device_select,
            num_shots_spinner,
            column(Spacer(height=18), row(update_toggle, push_elog_button)),
        ),
    )

    return TabPanel(child=tab_layout, title="jitter")
