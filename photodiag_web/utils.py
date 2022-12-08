import os
import tempfile

import elog
import urllib3
from bokeh.io import export_png

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # suppress elog warning


DEVICES = [
    "SARFE10-PBPS053",
    "SAROP11-PBPS110",
    "SAROP11-PBPS122",
    "SAROP21-PBPS103",
    "SAROP21-PBPS133",
    "SAROP31-PBPS113",
    "SAROP31-PBPS149",
]


def push_elog(figures, message, attributes):
    """Push an entry to elog at https://elog-gfa.psi.ch/SF-Photonics-Data.

    Args:
        figures (Iterable): an Iterable of tuples of bokeh Plot instances and a corresponding file
            names
        message (str): elog entry message text
        attributes (dict): elog entry attributes dictionary
    """
    logbook = elog.open(
        "https://elog-gfa.psi.ch/SF-Photonics-Data", user="sf-photodiag", password=""
    )

    attachments = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for figure, figure_name in figures:
            figure_path = os.path.join(temp_dir, figure_name)
            export_png(figure, filename=figure_path)
            attachments.append(figure_path)

        msg_id = logbook.post(
            message,
            attributes=attributes,
            attachments=attachments,
            suppress_email_notification=True,
        )

    return msg_id
