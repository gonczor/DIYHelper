class ActiveIngestionTaskError(Exception):
    def __init__(self, source: str, target_month: str) -> None:
        self.source = source
        self.target_month = target_month
        super().__init__(f"an active {source} task already exists for {target_month}")
