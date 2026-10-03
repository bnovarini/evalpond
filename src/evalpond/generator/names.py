"""Fictional names. Everything here is invented; combinations are random and not real entities."""
from __future__ import annotations

import random

EMP_A = ["Harbor Lane", "Cedar Ridge", "Blue Finch", "Maple Quarry", "Northgate", "Copper Hollow",
         "Juniper Bay", "Stonebridge", "Lantern Row", "Willow Fork", "Granite Peak", "Silver Ash",
         "Amber Mill", "Kestrel", "Fernwood", "Oak Terrace", "Tidewater", "Brindle", "Quarry Hill",
         "Larkspur"]
EMP_B = ["Logistics", "Dental Group", "Foods", "Builders", "Staffing", "Print Works", "Cleaning Co",
         "Medical Supply", "Landscaping", "Electric", "Bakery", "Freight", "Design Studio",
         "Auto Care", "Hardware", "Catering", "Roofing", "Pet Supply"]
BANK_A = ["Northfield", "Lakeview", "Redwood", "Pinecrest", "Harborview", "Summit Oak", "Elmstead"]
BANK_B = ["Community Bank", "Savings & Trust", "Credit Union", "Federal Savings"]
FIRST = ["Alma", "Jonas", "Priya", "Marcus", "Ingrid", "Tomas", "Leona", "Dmitri", "Noelle", "Rafael",
         "Yuki", "Beatrix", "Omar", "Celeste", "Hugo", "Mina", "Teodor", "Wren", "Isaac", "Lucia"]
LAST = ["Ashworth", "Okonkwo", "Lindqvist", "Marlowe", "Castellan", "Brightwater", "Navarre",
        "Pemberton", "Quillfeather", "Ramsden", "Sobotka", "Thornquist", "Varga", "Whitlock",
        "Yarrow", "Zelenko", "Bellamy", "Corvin", "Delacroix-Hale", "Eastwick"]
STREETS = ["Pine Hollow Rd", "Mill Run Ln", "Alder Court", "Fox Glen Dr", "Quarry St", "Bay Lantern Way",
           "Cobble Row", "Heron Pass"]
CITIES = ["Fairmont", "Eastbrook", "Lakeshore", "Dunmore Falls", "Ridgeway", "Oakhaven", "Westford Bay"]
STATES = ["OH", "MN", "CO", "OR", "NC", "PA", "MI"]
STORES = ["GREENLEAF MARKET", "RIVERSIDE FUEL", "CORNER CAFE", "HOMESTEAD HARDWARE", "BLUE DOOR PHARMACY",
          "TRANSIT PASS", "STREAMING SERVICE", "CITY UTILITIES", "ALDER PROPERTY MGMT", "GYM MEMBERSHIP"]


def employer(rng: random.Random) -> str:
    return f"{rng.choice(EMP_A)} {rng.choice(EMP_B)}"


def bank(rng: random.Random) -> str:
    return f"{rng.choice(BANK_A)} {rng.choice(BANK_B)}"


def person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def address(rng: random.Random) -> str:
    return f"{rng.randint(10, 9899)} {rng.choice(STREETS)}, {rng.choice(CITIES)}, {rng.choice(STATES)} {rng.randint(10000, 99999)}"


def masked_id(rng: random.Random) -> str:
    return f"XXX-XX-{rng.randint(0, 9999):04d}"


def masked_acct(rng: random.Random) -> str:
    return f"****{rng.randint(0, 9999):04d}"
