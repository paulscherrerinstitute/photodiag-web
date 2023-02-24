import logging
from collections import deque
from datetime import datetime
from threading import Thread

import bsread
import numpy as np
from bokeh.layouts import column, gridplot, row
from bokeh.models import Button, ColumnDataSource, Select, Spacer, Spinner, TabPanel, Toggle
from bokeh.plotting import curdoc, figure

from photodiag_web import DEVICES, push_elog

log = logging.getLogger(__name__)


def create():
    doc = curdoc()
    device_name = ""

    # xy figure
    xy_fig = figure(title=" ", height=500, width=500, tools="pan,wheel_zoom,save,reset")

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

    xy_fig.plot.legend.click_policy = "hide"

    # ix figure
    ix_fig = figure(title=" ", height=500, width=500, tools="pan,wheel_zoom,save,reset")

    ix_fig.circle(x="i", y="x", source=even_scatter_source, legend_label="even")
    ix_fig.circle(
        x="i",
        y="x",
        source=odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    ix_fig.plot.legend.click_policy = "hide"

    # iy figure
    iy_fig = figure(title=" ", height=500, width=500, tools="pan,wheel_zoom,save,reset")

    iy_fig.circle(x="i", y="y", source=even_scatter_source, legend_label="even")
    iy_fig.circle(
        x="i",
        y="y",
        source=odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    iy_fig.plot.legend.click_policy = "hide"

    buffer = deque()

    def _collect_data():
        nonlocal buffer
        buffer = deque(maxlen=num_shots_spinner.value)

        xpos_ch = f"{device_name}:XPOS"
        ypos_ch = f"{device_name}:YPOS"
        i0_ch = f"{device_name}:INTENSITY"

        with bsread.source(channels=[xpos_ch, ypos_ch, i0_ch]) as stream:
            while update_toggle.active:
                message = stream.receive()
                is_odd = message.data.pulse_id % 2
                data = message.data.data
                buffer.append((is_odd, data[xpos_ch].value, data[ypos_ch].value, data[i0_ch].value))

    async def _update_plots():
        if not buffer:
            xy_fig.title.text = " "
            ix_fig.title.text = " "
            iy_fig.title.text = " "

            even_scatter_source.data.update(x=[], y=[], i=[])
            odd_scatter_source.data.update(x=[], y=[], i=[])
            return

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

    def device_select_callback(_attr, _old, new):
        nonlocal device_name
        device_name = new

        # reset figures
        buffer.clear()
        doc.add_next_tick_callback(_update_plots)

    device_select = Select(title="Device:", options=DEVICES)
    device_select.on_change("value", device_select_callback)
    device_select.value = DEVICES[0]

    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)

    update_plots_periodic_callback = None

    def update_toggle_callback(_attr, _old, new):
        nonlocal update_plots_periodic_callback
        if new:
            thread = Thread(target=_collect_data)
            thread.start()

            update_plots_periodic_callback = doc.add_periodic_callback(_update_plots, 1000)

            xpos_ch = f"{device_name}:XPOS"
            ypos_ch = f"{device_name}:YPOS"
            i0_ch = f"{device_name}:INTENSITY"

            xy_fig.xaxis.axis_label = xpos_ch
            xy_fig.yaxis.axis_label = ypos_ch
            ix_fig.xaxis.axis_label = i0_ch
            ix_fig.yaxis.axis_label = xpos_ch
            iy_fig.xaxis.axis_label = i0_ch
            iy_fig.yaxis.axis_label = ypos_ch

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
        msg_id = push_elog(
            figures=((fig_layout, "jitter.png"),),
            message="",
            attributes={
                "Author": "sf-photodiag",
                "Entry": "Info",
                "Domain": "ARAMIS",
                "System": "Diagnostics",
                "Title": f"{device_name} jitter",
            },
        )
        log.info(
            f"Logbook entry created for {device_name} jitter: "
            f"https://elog-gfa.psi.ch/SF-Photonics-Data/{msg_id}"
        )

    push_elog_button = Button(label="Push elog")
    push_elog_button.on_click(push_elog_button_callback)

    fig_layout = gridplot([[xy_fig, ix_fig, iy_fig]], toolbar_options={"logo": None})
    tab_layout = column(
        fig_layout,
        row(
            device_select,
            num_shots_spinner,
            column(Spacer(height=18), row(update_toggle, push_elog_button)),
        ),
    )

    return TabPanel(child=tab_layout, title="jitter")
