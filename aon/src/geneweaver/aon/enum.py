"""Enumerations specifically for the GW AON API."""

from enum import Enum


class ReferenceGeneIDType(Enum):
    """Enum for defining gene reference id types."""

    AON = "aon"
    GW = "gw"


class InternalGeneIDType(Enum):
    """Enum for defining internal gene id types."""

    AON = "aon"
    GW = "gw"
