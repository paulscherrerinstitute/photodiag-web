import bsread
import numpy as np
import pandas as pd
from bokeh.layouts import column, row
from bokeh.models import (
    BasicTicker,
    Button,
    ColumnDataSource,
    DataRange1d,
    Div,
    Grid,
    Legend,
    LinearAxis,
    Plot,
    Scatter,
    Select,
    Spacer,
    Spinner,
    Switch,
    TabPanel,
)

from photodiag_web import DEVICES


def create():
    device_select = Select(title="Device:", value=DEVICES[0], options=DEVICES)
    num_shots_spinner = Spinner(title="Number shots:", mode="int", value=100, step=100, low=100)
    device2_select = Select(title="Device #2:", value=DEVICES[1], options=DEVICES)

    # xcorr_plot
    xcorr_plot = Plot(
        x_range=DataRange1d(),
        y_range=DataRange1d(),
        height=300,
        width=500,
        toolbar_location="left",
    )

    xcorr_plot.toolbar.logo = None

    xcorr_plot.add_layout(LinearAxis(axis_label="XPOS"), place="below")
    xcorr_plot.add_layout(
        LinearAxis(axis_label="XPOS2", major_label_orientation="vertical"), place="left"
    )

    xcorr_plot.add_layout(Grid(dimension=0, ticker=BasicTicker()))
    xcorr_plot.add_layout(Grid(dimension=1, ticker=BasicTicker()))

    xcorr_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    xcorr_even_scatter = xcorr_plot.add_glyph(
        xcorr_even_scatter_source, Scatter(x="x", y="y", line_color="blue", fill_color="blue")
    )

    xcorr_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    xcorr_odd_scatter = xcorr_plot.add_glyph(
        xcorr_odd_scatter_source, Scatter(x="x", y="y", line_color="red", fill_color="red")
    )

    xcorr_plot.add_layout(
        Legend(
            items=[("even", [xcorr_even_scatter]), ("odd", [xcorr_odd_scatter])],
            location="top_left",
            click_policy="hide",
        )
    )

    # ycorr_plot
    ycorr_plot = Plot(
        x_range=DataRange1d(), y_range=DataRange1d(), height=300, width=500, toolbar_location="left"
    )

    ycorr_plot.toolbar.logo = None

    ycorr_plot.add_layout(LinearAxis(axis_label="YPOS"), place="below")
    ycorr_plot.add_layout(
        LinearAxis(axis_label="YPOS2", major_label_orientation="vertical"), place="left"
    )

    ycorr_plot.add_layout(Grid(dimension=0, ticker=BasicTicker()))
    ycorr_plot.add_layout(Grid(dimension=1, ticker=BasicTicker()))

    ycorr_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    ycorr_even_scatter = ycorr_plot.add_glyph(
        ycorr_even_scatter_source, Scatter(x="x", y="y", line_color="blue", fill_color="blue")
    )

    ycorr_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    ycorr_odd_scatter = ycorr_plot.add_glyph(
        ycorr_odd_scatter_source, Scatter(x="x", y="y", line_color="red", fill_color="red")
    )

    ycorr_plot.add_layout(
        Legend(
            items=[("even", [ycorr_even_scatter]), ("odd", [ycorr_odd_scatter])],
            location="top_left",
            click_policy="hide",
        )
    )

    # icorr_plot
    icorr_plot = Plot(
        x_range=DataRange1d(),
        y_range=DataRange1d(),
        height=300,
        width=500,
        toolbar_location="left",
    )

    icorr_plot.toolbar.logo = None

    icorr_plot.add_layout(LinearAxis(axis_label="INT"), place="below")
    icorr_plot.add_layout(
        LinearAxis(axis_label="INT2", major_label_orientation="vertical"), place="left"
    )

    icorr_plot.add_layout(Grid(dimension=0, ticker=BasicTicker()))
    icorr_plot.add_layout(Grid(dimension=1, ticker=BasicTicker()))

    icorr_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    icorr_even_scatter = icorr_plot.add_glyph(
        icorr_even_scatter_source, Scatter(x="x", y="y", line_color="blue", fill_color="blue")
    )

    icorr_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    icorr_odd_scatter = icorr_plot.add_glyph(
        icorr_odd_scatter_source, Scatter(x="x", y="y", line_color="red", fill_color="red")
    )

    icorr_plot.add_layout(
        Legend(
            items=[("even", [icorr_even_scatter]), ("odd", [icorr_odd_scatter])],
            location="top_left",
            click_policy="hide",
        )
    )

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
