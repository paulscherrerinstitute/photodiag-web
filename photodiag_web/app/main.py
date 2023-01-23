import logging

from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import Div, Tabs, TextAreaInput

from photodiag_web.app import panel_calibration, panel_correlation, panel_jitter, panel_spect_corr

doc = curdoc()
doc.title = "photodiag-web"

title_img = Div(text="""<img src="/app/static/aramis.png" width="40%">""")

# In app_hooks.py a StreamHandler was added to "photodiag_web" and "bokeh" loggers
stream = logging.getLogger("photodiag_web").handlers[0].stream
bokeh_stream = logging.getLogger("bokeh").handlers[0].stream

log_textareainput = TextAreaInput(title="logging output:", height=150, width=750)
bokeh_log_textareainput = TextAreaInput(title="server output:", height=150, width=750)


# Final layout
doc.add_root(
    column(
        title_img,
        Tabs(
            tabs=[
                panel_calibration.create(),
                panel_correlation.create(),
                panel_jitter.create(),
                panel_spect_corr.create(),
            ]
        ),
        row(log_textareainput, bokeh_log_textareainput),
    )
)


def update_stdout():
    log_textareainput.value = stream.getvalue()
    bokeh_log_textareainput.value = bokeh_stream.getvalue()


doc.add_periodic_callback(update_stdout, 1000)
