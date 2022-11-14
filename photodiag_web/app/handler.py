from bokeh.application.handlers import Handler


class PhotodiagWebHandler(Handler):
    """Provides a mechanism for generic bokeh applications to build up new streamvis documents.
    """

    def __init__(self):
        """Initialize a photodiag handler for bokeh applications.
        Args:
            args (Namespace): Command line parsed arguments.
        """
        super().__init__()  # no-op

    def modify_document(self, doc):
        """Modify an application document with photodiag specific features.
        Args:
            doc (Document) : A bokeh Document to update in-place
        Returns:
            Document
        """
        doc.title = "photodiag-web"

        return doc
