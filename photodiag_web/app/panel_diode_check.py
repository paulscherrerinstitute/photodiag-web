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

        with bsread.source(channels=diodes_ch) as stream:
            while update_toggle.active:
                message = stream.receive()
                data = message.data.data

                i0 = data[config[diode_name]].value
                if i0 is None or i0 == 0:
                    # Normalization is not possible
                    buffer.append((None, None, None, None))
                    continue

                ratios = []
                for diode in DIODES:
                    if diode == diode_name:
                        continue  # i0 case

                    # Normalize by values of the selected diode
                    val = data[config[diode]].value
                    ratios.append(None if val is None else val / i0)

                buffer.append((i0, *ratios))

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
