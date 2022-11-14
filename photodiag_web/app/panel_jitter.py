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
    # yx_plot
    yx_plot = Plot(
        x_range=DataRange1d(),
        y_range=DataRange1d(),
        height=300,
        width=500,
        toolbar_location="left",
    )

    yx_plot.toolbar.logo = None

    yx_plot.add_layout(LinearAxis(axis_label="XPOS"), place="below")
    yx_plot.add_layout(
        LinearAxis(axis_label="YPOS", major_label_orientation="vertical"), place="left"
    )

    yx_plot.add_layout(Grid(dimension=0, ticker=BasicTicker()))
    yx_plot.add_layout(Grid(dimension=1, ticker=BasicTicker()))

    yx_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    yx_even_scatter = yx_plot.add_glyph(
        yx_even_scatter_source, Scatter(x="x", y="y", line_color="blue", fill_color="blue")
    )

    yx_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    yx_odd_scatter = yx_plot.add_glyph(
        yx_odd_scatter_source, Scatter(x="x", y="y", line_color="red", fill_color="red")
    )

    yx_plot.add_layout(
        Legend(
            items=[("even", [yx_even_scatter]), ("odd", [yx_odd_scatter])],
            location="top_left",
            click_policy="hide",
        )
    )

    # ix_plot
    ix_plot = Plot(
        x_range=DataRange1d(), y_range=DataRange1d(), height=300, width=500, toolbar_location="left"
    )

    ix_plot.toolbar.logo = None

    ix_plot.add_layout(LinearAxis(axis_label="INT"), place="below")
    ix_plot.add_layout(
        LinearAxis(axis_label="XPOS", major_label_orientation="vertical"), place="left"
    )

    ix_plot.add_layout(Grid(dimension=0, ticker=BasicTicker()))
    ix_plot.add_layout(Grid(dimension=1, ticker=BasicTicker()))

    ix_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    ix_even_scatter = ix_plot.add_glyph(
        ix_even_scatter_source, Scatter(x="x", y="y", line_color="blue", fill_color="blue")
    )

    ix_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    ix_odd_scatter = ix_plot.add_glyph(
        ix_odd_scatter_source, Scatter(x="x", y="y", line_color="red", fill_color="red")
    )

    ix_plot.add_layout(
        Legend(
            items=[("even", [ix_even_scatter]), ("odd", [ix_odd_scatter])],
            location="top_left",
            click_policy="hide",
        )
    )

    # iy_plot
    iy_plot = Plot(
        x_range=DataRange1d(),
        y_range=DataRange1d(),
        height=300,
        width=500,
        toolbar_location="left",
    )

    iy_plot.toolbar.logo = None

    iy_plot.add_layout(LinearAxis(axis_label="INT"), place="below")
    iy_plot.add_layout(
        LinearAxis(axis_label="YPOS", major_label_orientation="vertical"), place="left"
    )

    iy_plot.add_layout(Grid(dimension=0, ticker=BasicTicker()))
    iy_plot.add_layout(Grid(dimension=1, ticker=BasicTicker()))

    iy_even_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    iy_even_scatter = iy_plot.add_glyph(
        iy_even_scatter_source, Scatter(x="x", y="y", line_color="blue", fill_color="blue")
    )

    iy_odd_scatter_source = ColumnDataSource(dict(x=[], y=[]))
    iy_odd_scatter = iy_plot.add_glyph(
        iy_odd_scatter_source, Scatter(x="x", y="y", line_color="red", fill_color="red")
    )

    iy_plot.add_layout(
        Legend(
            items=[("even", [iy_even_scatter]), ("odd", [iy_odd_scatter])],
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
        row(yx_plot, ix_plot, iy_plot),
        row(
            device_select,
            num_shots_spinner,
            column(
                Spacer(height=18),
                row(
                    update_button,
                    column(Spacer(height=6), row(continuous_switch, continuous_div)),
                    push_elog_button,
                )
            )
        ),
    )

    return TabPanel(child=tab_layout, title="jitter")
