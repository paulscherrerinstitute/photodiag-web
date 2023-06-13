import os
import tempfile
import time

import elog
import epics
import numpy as np
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


def _make_arrays(pvs, n_pulses):
    arrays = []
    for pv in pvs:
        val = pv.value

        dtype = val.dtype if isinstance(val, np.ndarray) else type(val)
        shape = val.shape if isinstance(val, np.ndarray) else tuple()
        shape = (n_pulses,) + shape

        arr = np.empty(shape, dtype)
        arrays.append(arr)

    return arrays


def epics_collect_data(channels, n_pulses=100, wait_time=0.5):
    pvs = [epics.PV(ch) for ch in channels]
    counters = np.zeros(len(channels), dtype=int)

    arrays = _make_arrays(pvs, n_pulses)

    def on_value_change(pv=None, ichannel=None, value=None, **_):
        ivalue = counters[ichannel]
        arrays[ichannel][ivalue] = value

        counters[ichannel] += 1

        if counters[ichannel] == n_pulses:
            pv.disconnect()

    for i, pv in enumerate(pvs):
        pv.add_callback(callback=on_value_change, pv=pv, ichannel=i)

    while not np.all(counters == n_pulses):
        time.sleep(wait_time)

    return arrays


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


def get_device_domain(device_name):
    if device_name[1:3] == "AR":
        domain = "ARAMIS"
    elif device_name[1:3] == "AT":
        domain = "ATHOS"
    else:
        domain = ""
    return domain
