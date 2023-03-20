from collections import deque
from datetime import datetime
from threading import Thread

import bsread
import numpy as np
from bokeh.layouts import column, gridplot, row
from bokeh.models import Button, ColumnDataSource, Select, Spacer, Spinner, TabPanel, Toggle
from bokeh.plotting import curdoc, figure

from photodiag_web import DEVICES, push_elog


def create():
    doc = curdoc()
    log = doc.logger
    device1_name = ""
    device1_channels = ("", "", "")
    device2_name = ""
    device2_channels = ("", "", "")

    # xcorr figure
    xcorr_fig = figure(title=" ", height=500, width=500, tools="pan,wheel_zoom,save,reset")

    xcorr_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    xcorr_fig.circle(source=xcorr_even_scatter_source, legend_label="even")

    xcorr_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    xcorr_fig.circle(
        source=xcorr_odd_scatter_source, line_color="red", fill_color="red", legend_label="odd"
    )

    xcorr_fig.plot.legend.click_policy = "hide"

    # ycorr figure
    ycorr_fig = figure(title=" ", height=500, width=500, tools="pan,wheel_zoom,save,reset")

    ycorr_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    ycorr_fig.circle(source=ycorr_even_scatter_source, legend_label="even")

    ycorr_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    ycorr_fig.circle(
        source=ycorr_odd_scatter_source, line_color="red", fill_color="red", legend_label="odd"
    )

    ycorr_fig.plot.legend.click_policy = "hide"

    # icorr figure
    icorr_fig = figure(title=" ", height=500, width=500, tools="pan,wheel_zoom,save,reset")

    icorr_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    icorr_fig.circle(source=icorr_even_scatter_source, legend_label="even")

    icorr_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    icorr_fig.circle(
        source=icorr_odd_scatter_source, line_color="red", fill_color="red", legend_label="odd"
    )

    icorr_fig.plot.legend.click_policy = "hide"

    buffer = deque()

    def _collect_data():
        nonlocal buffer
        buffer = deque(maxlen=num_shots_spinner.value)
        channels = (*device1_channels, *device2_channels)

        try:
            with bsread.source(channels=channels) as stream:
                while update_toggle.active:
                    msg_data = stream.receive().data
                    is_odd = msg_data.pulse_id % 2
                    values = [msg_data.data.get(ch).value for ch in channels]

                    # Normalize values of the second device by values of the first device
                    if not (any(val is None for val in values) or 0 in values[:3]):
                        values[3] /= values[0]
                        values[4] /= values[1]
                        values[5] /= values[2]
                        buffer.append((is_odd, *values))

        except Exception as e:
            log.error(e)

    async def _update_plots():
        if not buffer:
            xcorr_fig.title.text = " "
            ycorr_fig.title.text = " "
            icorr_fig.title.text = " "

            xcorr_even_scatter_source.data.update(x=[], y=[])
            ycorr_even_scatter_source.data.update(x=[], y=[])
            icorr_even_scatter_source.data.update(x=[], y=[])

            xcorr_odd_scatter_source.data.update(x=[], y=[])
            ycorr_odd_scatter_source.data.update(x=[], y=[])
            icorr_odd_scatter_source.data.update(x=[], y=[])
            return

        datetime_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = f"{device2_name} vs {device1_name}, {datetime_now}"
        xcorr_fig.title.text = title
        ycorr_fig.title.text = title
        icorr_fig.title.text = title

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

    def device1_select_callback(_attr, _old, new):
        nonlocal device1_name, device1_channels
        device1_name = new
        device1_channels = f"{new}:XPOS", f"{new}:YPOS", f"{new}:INTENSITY"

        # reset figures
        buffer.clear()
        doc.add_next_tick_callback(_update_plots)

    device1_select = Select(title="Device #1:", options=DEVICES)
    device1_select.on_change("value", device1_select_callback)
    device1_select.value = DEVICES[0]

    def device2_select_callback(_attr, _old, new):
        nonlocal device2_name, device2_channels
        device2_name = new
        device2_channels = f"{new}:XPOS", f"{new}:YPOS", f"{new}:INTENSITY"

        # reset figures
        buffer.clear()
        doc.add_next_tick_callback(_update_plots)

    device2_select = Select(title="Device #2:", options=DEVICES)
    device2_select.on_change("value", device2_select_callback)
    device2_select.value = DEVICES[1]

    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)

    update_plots_periodic_callback = None

    def update_toggle_callback(_attr, _old, new):
        nonlocal update_plots_periodic_callback
        if new:
            thread = Thread(target=_collect_data)
            thread.start()

            update_plots_periodic_callback = doc.add_periodic_callback(_update_plots, 1000)

            xpos1_ch, ypos1_ch, i01_ch = device1_channels
            xpos2_ch, ypos2_ch, i02_ch = device2_channels

            xcorr_fig.xaxis.axis_label = xpos1_ch
            xcorr_fig.yaxis.axis_label = f"{xpos2_ch} / {xpos1_ch}"
            ycorr_fig.xaxis.axis_label = ypos1_ch
            ycorr_fig.yaxis.axis_label = f"{ypos2_ch} / {ypos1_ch}"
            icorr_fig.xaxis.axis_label = i01_ch
            icorr_fig.yaxis.axis_label = f"{i02_ch} / {i01_ch}"

            device1_select.disabled = True
            device2_select.disabled = True
            num_shots_spinner.disabled = True
            push_elog_button.disabled = True

            update_toggle.label = "Stop"
            update_toggle.button_type = "success"
        else:
            doc.remove_periodic_callback(update_plots_periodic_callback)

            device1_select.disabled = False
            device2_select.disabled = False
            num_shots_spinner.disabled = False
            push_elog_button.disabled = False

            update_toggle.label = "Update"
            update_toggle.button_type = "primary"

    update_toggle = Toggle(label="Update", button_type="primary")
    update_toggle.on_change("active", update_toggle_callback)

    def push_elog_button_callback():
        msg_id = push_elog(
            figures=((fig_layout, "correlation.png"),),
            message="",
            attributes={
                "Author": "sf-photodiag",
                "Entry": "Info",
                "Domain": "ARAMIS",
                "System": "Diagnostics",
                "Title": f"{device2_name} vs {device1_name} correlation",
            },
        )
        log.info(
            f"Logbook entry created for {device2_name} vs {device1_name} correlation: "
            f"https://elog-gfa.psi.ch/SF-Photonics-Data/{msg_id}"
        )

    push_elog_button = Button(label="Push elog")
    push_elog_button.on_click(push_elog_button_callback)

    fig_layout = gridplot([[xcorr_fig, ycorr_fig, icorr_fig]], toolbar_options={"logo": None})
    tab_layout = column(
        fig_layout,
        row(
            device1_select,
            device2_select,
            num_shots_spinner,
            column(Spacer(height=18), row(update_toggle, push_elog_button)),
        ),
    )

    return TabPanel(child=tab_layout, title="correlation")
