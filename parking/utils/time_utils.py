from math import ceil
from datetime import datetime


def calculate_hours(start, end):
    return ceil((end - start).total_seconds() / 3600)


def calculate_price(base_price, price_increment, hours):
    return base_price + (price_increment * hours)
