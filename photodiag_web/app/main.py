import logging
from io import StringIO

from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import Div, Tabs, TextAreaInput

from photodiag_web.app import panel_calibration, panel_correlation, panel_jitter

doc = curdoc()
doc.title = "photodiag-web"

title_img = Div(text="""<img src="/app/static/aramis.png" width=1000>""")

stream = StringIO()
handler = logging.StreamHandler(stream)
handler.setFormatter(
    logging.Formatter(fmt="%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger = logging.getLogger(str(id(doc)))
logger.propagate = False
logger.setLevel(logging.INFO)
logger.addHandler(handler)
log_textareainput = TextAreaInput(title="print output:", height=150, width=750)

doc.logger = logger

bokeh_stream = StringIO()
bokeh_handler = logging.StreamHandler(bokeh_stream)
bokeh_handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
bokeh_logger = logging.getLogger("bokeh")
bokeh_logger.setLevel(logging.WARNING)
bokeh_logger.addHandler(bokeh_handler)
bokeh_log_textareainput = TextAreaInput(title="server output:", height=150, width=750)


# Final layout
doc.add_root(
    column(
        title_img,
        Tabs(tabs=[panel_calibration.create(), panel_correlation.create(), panel_jitter.create()]),
        row(log_textareainput, bokeh_log_textareainput),
    )
)


def update_stdout():
    log_textareainput.value = stream.getvalue()
    bokeh_log_textareainput.value = bokeh_stream.getvalue()


doc.add_periodic_callback(update_stdout, 1000)
