import bsread
import numpy as np
import pandas as pd
from bokeh.layouts import column, row
from bokeh.models import Button, ColumnDataSource, Div, Select, Spacer, Spinner, Switch, TabPanel
from bokeh.plotting import figure

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
        device2_name = device2_select.value
        intensity = device_name + ":INTENSITY"
        intensity2 = device2_name + ":INTENSITY"
        xpos = device_name + ":XPOS"
        xpos2 = device2_name + ":XPOS"
        ypos = device_name + ":YPOS"
        ypos2 = device2_name + ":YPOS"

        data = _get_bs_data(
            [intensity, xpos, ypos, intensity2, xpos2, ypos2],
            numshots=int(num_shots_spinner.value),
        )
        data_even = data[data["Parity"] == "Even"]
        data_odd = data[data["Parity"] == "Odd"]

        xcorr_even_scatter_source.data.update(x=data_even[xpos], y=data_even[xpos2])
        ycorr_even_scatter_source.data.update(x=data_even[ypos], y=data_even[ypos2])
        icorr_even_scatter_source.data.update(x=data_even[intensity], y=data_even[intensity2])

        xcorr_odd_scatter_source.data.update(x=data_odd[xpos], y=data_odd[xpos2])
        ycorr_odd_scatter_source.data.update(x=data_odd[ypos], y=data_odd[ypos2])
        icorr_odd_scatter_source.data.update(x=data_odd[intensity], y=data_odd[intensity2])

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
        row(xcorr_plot, ycorr_plot, icorr_plot),
        row(
            device_select,
            device2_select,
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

    return TabPanel(child=tab_layout, title="correlation")
