import logging
import sys
from io import StringIO

import panel_jitter  # pylint: disable=import-error
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import Tabs, TextAreaInput

doc = curdoc()

sys.stdout = StringIO()
stdout_textareainput = TextAreaInput(title="print output:", height=150, width=750)

bokeh_stream = StringIO()
bokeh_handler = logging.StreamHandler(bokeh_stream)
bokeh_handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
bokeh_logger = logging.getLogger("bokeh")
bokeh_logger.addHandler(bokeh_handler)
bokeh_log_textareainput = TextAreaInput(title="server output:", height=150, width=750)


# Final layout
doc.add_root(
    column(Tabs(tabs=[panel_jitter.create()]), row(stdout_textareainput, bokeh_log_textareainput))
)


def update_stdout():
    stdout_textareainput.value = sys.stdout.getvalue()
    bokeh_log_textareainput.value = bokeh_stream.getvalue()


doc.add_periodic_callback(update_stdout, 1000)
