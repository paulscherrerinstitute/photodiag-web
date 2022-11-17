import bsread
import numpy as np
import pandas as pd
from bokeh.layouts import column, row
from bokeh.models import Button, ColumnDataSource, Div, Select, Spacer, Spinner, Switch, TabPanel
from bokeh.plotting import figure

from photodiag_web import DEVICES


def create():
    # yx figure
    yx_fig = figure(
        x_axis_label="XPOS",
        y_axis_label="YPOS",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    yx_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    yx_fig.circle(x="x", y="y", source=yx_even_scatter_source, legend_label="even")

    yx_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    yx_fig.circle(
        x="x",
        y="y",
        source=yx_odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    yx_fig.plot.toolbar.logo = None
    yx_fig.plot.legend.click_policy = "hide"

    # ix figure
    ix_fig = figure(
        x_axis_label="INT",
        y_axis_label="XPOS",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    ix_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    ix_fig.circle(x="x", y="y", source=ix_even_scatter_source, legend_label="even")

    ix_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    ix_fig.circle(
        x="x",
        y="y",
        source=ix_odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    ix_fig.plot.toolbar.logo = None
    ix_fig.plot.legend.click_policy = "hide"

    # iy figure
    iy_fig = figure(
        x_axis_label="INT",
        y_axis_label="YPOS",
        height=300,
        width=500,
        tools="pan,wheel_zoom,save,reset",
    )

    iy_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    iy_fig.circle(x="x", y="y", source=iy_even_scatter_source, legend_label="even")

    iy_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    iy_fig.circle(
        x="x",
        y="y",
        source=iy_odd_scatter_source,
        line_color="red",
        fill_color="red",
        legend_label="odd",
    )

    iy_fig.plot.toolbar.logo = None
    iy_fig.plot.legend.click_policy = "hide"

    def _get_bs_data(channels, numshots):
        tmp_data = np.zeros([numshots, len(channels) + 1])
        with bsread.source(channels=channels) as stream:
            for i in range(0, numshots):
                message = stream.receive()
                for ch_num, ch in enumerate(channels):
                    tmp_data[i, ch_num] = message.data.data[ch].value
                    tmp_data[i, len(channels)] = message.data.pulse_id

        data_out = pd.DataFrame(columns=channels)
        for ch_num, ch in enumerate(channels):
            data_out[ch] = tmp_data[:, ch_num]
        data_out["PulseID"] = tmp_data[:, len(channels)]

        # add parity
        vals = []
        for ID in data_out["PulseID"]:
            if ID % 2 == 0:
                vals.append("Even")
            else:
                vals.append("Odd")
        data_out["Parity"] = vals
        return data_out

    def update():
        device_name = device_select.value
        intensity = device_name + ":INTENSITY"
        xpos = device_name + ":XPOS"
        ypos = device_name + ":YPOS"

        data = _get_bs_data([intensity, xpos, ypos], numshots=int(num_shots_spinner.value))
        data_even = data[data["Parity"] == "Even"]
        data_odd = data[data["Parity"] == "Odd"]

        yx_even_scatter_source.data.update(x=data_even[xpos], y=data_even[ypos])
        ix_even_scatter_source.data.update(x=data_even[intensity], y=data_even[xpos])
        iy_even_scatter_source.data.update(x=data_even[intensity], y=data_even[ypos])

        yx_odd_scatter_source.data.update(x=data_odd[xpos], y=data_odd[ypos])
        ix_odd_scatter_source.data.update(x=data_odd[intensity], y=data_odd[xpos])
        iy_odd_scatter_source.data.update(x=data_odd[intensity], y=data_odd[ypos])

    device_select = Select(title="Device:", value=DEVICES[0], options=DEVICES)
    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)

    def update_toggle_callback():
        update()

    update_button = Button(label="Update", button_type="primary")
    update_button.on_click(update_toggle_callback)

    continuous_div = Div(text="Continuous")
    continuous_switch = Switch(active=False, disabled=True)

    push_elog_button = Button(label="Push elog", disabled=True)

    tab_layout = column(
        row(yx_fig, ix_fig, iy_fig),
        row(
            device_select,
            num_shots_spinner,
            column(
                Spacer(height=18),
                row(
                    update_button,
                    column(Spacer(height=6), row(continuous_switch, continuous_div)),
                    push_elog_button,
                ),
            ),
        ),
    )

    return TabPanel(child=tab_layout, title="jitter")
