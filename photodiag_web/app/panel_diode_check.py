from collections import deque
from datetime import datetime
from threading import Thread

import bsread
import numpy as np
from bokeh.layouts import column, gridplot, row
from bokeh.models import ColumnDataSource, Select, Spacer, Spinner, TabPanel, Toggle
from bokeh.plotting import curdoc, figure
from cam_server_client import PipelineClient

from photodiag_web import DEVICES

client = PipelineClient()
DIODES = ["up", "down", "left", "right"]


def create():
    doc = curdoc()
    log = doc.logger
    device_name = ""
    diode_name = ""

    # figure #1
    fig1 = figure(title=" ", height=500, width=500, tools="pan,wheel_zoom,save,reset")

    fig1_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    fig1.circle(source=fig1_scatter_source, legend_label="data")

    fig1.plot.legend.click_policy = "hide"

    # figure #2
    fig2 = figure(title=" ", height=500, width=500, tools="pan,wheel_zoom,save,reset")

    fig2_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    fig2.circle(source=fig2_scatter_source, legend_label="data")

    fig2.plot.legend.click_policy = "hide"

    # figure #3
    fig3 = figure(title=" ", height=500, width=500, tools="pan,wheel_zoom,save,reset")

    fig3_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    fig3.circle(source=fig3_scatter_source, legend_label="data")

    fig3.plot.legend.click_policy = "hide"

    buffer = deque()

    def _collect_data():
        nonlocal buffer
        buffer = deque(maxlen=num_shots_spinner.value)
        config = client.get_pipeline_config(device_name + "_proc")
        diodes_ch = [config[diode] for diode in DIODES]
        i0_ind = DIODES.index(diode_name)

        try:
            with bsread.source(channels=diodes_ch) as stream:
                while update_toggle.active:
                    message = stream.receive()
                    values = [message.data.data[ch].value for ch in diodes_ch]
                    # Normalize by selected diode value (= i0)
                    if not (any(val is None for val in values) or values[i0_ind] == 0):
                        i0 = values.pop(i0_ind)
                        values = [val / i0 for val in values]
                        buffer.append((i0, *values))

        except Exception as e:
            log.error(e)

    async def _update_plots():
        if not buffer:
            fig1.title.text = " "
            fig2.title.text = " "
            fig3.title.text = " "

            fig1_scatter_source.data.update(x=[], y=[])
            fig2_scatter_source.data.update(x=[], y=[])
            fig3_scatter_source.data.update(x=[], y=[])

            return

        datetime_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = f"{device_name}, {datetime_now}"
        fig1.title.text = title
        fig2.title.text = title
        fig3.title.text = title

        data_array = np.array(buffer)
        x_val = data_array[:, 0]

        fig1_scatter_source.data.update(x=x_val, y=data_array[:, 1])
        fig2_scatter_source.data.update(x=x_val, y=data_array[:, 2])
        fig3_scatter_source.data.update(x=x_val, y=data_array[:, 3])

    def device_select_callback(_attr, _old, new):
        nonlocal device_name
        device_name = new

        # reset figures
        buffer.clear()
        doc.add_next_tick_callback(_update_plots)

    device_select = Select(title="Device:", options=DEVICES)
    device_select.on_change("value", device_select_callback)
    device_select.value = DEVICES[0]

    def diode_select_callback(_attr, _old, new):
        nonlocal diode_name
        diode_name = new

        # reset figures
        buffer.clear()
        doc.add_next_tick_callback(_update_plots)

    diode_select = Select(title="Diode:", options=DIODES)
    diode_select.on_change("value", diode_select_callback)
    diode_select.value = DIODES[0]

    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)

    update_plots_periodic_callback = None

    def update_toggle_callback(_attr, _old, new):
        nonlocal update_plots_periodic_callback
        if new:
            thread = Thread(target=_collect_data)
            thread.start()

            update_plots_periodic_callback = doc.add_periodic_callback(_update_plots, 1000)

            diodes = DIODES.copy()
            diodes.remove(diode_name)

            fig1.xaxis.axis_label = diode_name
            fig1.yaxis.axis_label = f"{diodes[0]} / {diode_name}"
            fig2.xaxis.axis_label = diode_name
            fig2.yaxis.axis_label = f"{diodes[1]} / {diode_name}"
            fig3.xaxis.axis_label = diode_name
            fig3.yaxis.axis_label = f"{diodes[2]} / {diode_name}"

            device_select.disabled = True
            diode_select.disabled = True
            num_shots_spinner.disabled = True

            update_toggle.label = "Stop"
            update_toggle.button_type = "success"
        else:
            doc.remove_periodic_callback(update_plots_periodic_callback)

            device_select.disabled = False
            diode_select.disabled = False
            num_shots_spinner.disabled = False

            update_toggle.label = "Update"
            update_toggle.button_type = "primary"

    update_toggle = Toggle(label="Update", button_type="primary")
    update_toggle.on_change("active", update_toggle_callback)

    fig_layout = gridplot([[fig1, fig2, fig3]], toolbar_options={"logo": None})
    tab_layout = column(
        fig_layout,
        row(
            device_select, diode_select, num_shots_spinner, column(Spacer(height=18), update_toggle)
        ),
    )

    return TabPanel(child=tab_layout, title="diode check")
