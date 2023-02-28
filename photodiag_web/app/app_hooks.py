def on_session_destroyed(session_context):
    for pv in session_context._document.pvs:
        pv.clear_callbacks()
