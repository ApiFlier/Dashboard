class UpstreamAPIError(Exception):
    def __init__(self, message="Error fetching data from upstream API"):
        self.message = message
        super().__init__(self.message)
