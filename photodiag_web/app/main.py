import logging
from io import StringIO

from bokeh.io import curdoc
from bokeh.layouts import column
from bokeh.models import Div, TabPanel, Tabs, TextAreaInput

from photodiag_web.app import (
    panel_calibration,
    panel_correlation,
    panel_diode_check,
    panel_jitter,
    panel_spect_autocorr,
    panel_spect_int_corr,
    panel_spect_peaks,
)

doc = curdoc()
doc.title = "photodiag-web"
doc.pvs = []

stream = StringIO()
handler = logging.StreamHandler(stream)
handler.setFormatter(
    logging.Formatter(fmt="%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger = logging.getLogger(str(id(doc)))
logger.setLevel(logging.INFO)
logger.addHandler(handler)
# Add logger before creating panels!
doc.logger = logger

log_textareainput = TextAreaInput(title="logging output:", height=150, width=1500)

position_img = Div(text="""<img src="/app/static/aramis.png" width="1000" height="200">""")
position_tabs = Tabs(
    tabs=[
        panel_calibration.create(),
        panel_correlation.create(),
        panel_jitter.create(),
        panel_diode_check.create(),
    ]
)
position_panel = TabPanel(child=column(position_img, position_tabs), title="Position")

spectral_img = Div(text="""<img src="/app/static/sf_spectral.png" width="1000" height="200">""")
spectral_tabs = Tabs(
    tabs=[
        panel_spect_int_corr.create(),
        panel_spect_peaks.create("Aramis Spectral peaks analysis", ["SARFE10-PSSS059"]),
        panel_spect_peaks.create(
            "Athos Spectral peaks analysis", ["SATOP21-PMOS127-2D", "SATOP31-PMOS132-2D"]
        ),
        panel_spect_autocorr.create("Aramis/Athos Spectral autocorrelation"),
    ]
)
spectral_panel = TabPanel(child=column(spectral_img, spectral_tabs), title="Spectral")

# Final layout
doc.add_root(
    column(
        Tabs(
            tabs=[position_panel, spectral_panel],
            stylesheets=[".bk-tab {font-weight: bold; font-size: 20px;}"],
        ),
        log_textareainput,
    )
)


def update_stdout():
    log_textareainput.value = stream.getvalue()


doc.add_periodic_callback(update_stdout, 1000)
