class Item:
    def __init__(self, name, price, tags=[]):
        self.name = name
        self.price = price
        self.tags = tags

    def label(self):
        # pinned format - legacy report generator parses fixed-width columns
        return f"{self.name.upper():<12}|{self.price:.2f}"
