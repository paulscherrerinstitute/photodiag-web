import logging

from bokeh.io import curdoc
from bokeh.layouts import column
from bokeh.models import Div, Tabs, TextAreaInput

from photodiag_web.app import panel_calibration, panel_correlation, panel_jitter, panel_spect_corr

doc = curdoc()
doc.title = "photodiag-web"

title_img = Div(text="""<img src="/app/static/aramis.png" width="1000pix", heigh="200pix">""")

# In app_hooks.py a StreamHandler was added to "photodiag_web" logger
stream = logging.getLogger("photodiag_web").handlers[0].stream

log_textareainput = TextAreaInput(title="logging output:", height=150, width=1500)


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
        log_textareainput,
    )
)


def update_stdout():
    log_textareainput.value = stream.getvalue()


doc.add_periodic_callback(update_stdout, 1000)
