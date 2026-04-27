"""
POIM-PA codec: encodes and decodes Point-of-Interest Message – Parking
Availability (ETSI TS 103 916 v2.1.1) payloads using `asn1tools` UPER.

The ASN.1 schema is loaded from ``asn1/POIM-PA-Standalone.asn`` located next
to this file.  That file is self-contained — it inlines the necessary types
from ETSI-ITS-CDD (TS 102 894-2) so that no external ASN.1 dependency is
required at runtime.

Wire format
-----------
Because cube-its does not yet expose a dedicated POIM facility service, POIM
messages are carried over raw BTP port 2009.  The BTP payload is structured as:

    +----+----+--------+----+----+--    --+
    | 01 | 06 |stationId| 01 |len | block |
    +----+----+--------+----+----+--    --+
      1B   1B    4B      1B   2B    N B

  Byte 0   : protocolVersion  = 1
  Byte 1   : messageId        = 6  (poim, ETSI TS 102 894-2 §6.1.68)
  Bytes 2-5: stationId        (uint32, big-endian, 0 → stack fills in own ID)
  Byte 6   : poiType          = 1  (parkingAvailability)
  Bytes 7-8: blockLength      (uint16 big-endian, byte-length of UPER block)
  Bytes 9..: UPER-encoded ``ParkingAvailabilityBlock``

TimestampIts reference epoch
----------------------------
TimestampIts is in milliseconds elapsed since 2004-01-01 00:00:00.000 UTC
(GPS epoch, with leap seconds NOT subtracted — i.e. UTC-based).
"""

import os
import struct
import datetime

import asn1tools

# ---------------------------------------------------------------------------
# Load the ASN.1 schema once at import time
# ---------------------------------------------------------------------------

_ASN1_FILE = os.path.join(os.path.dirname(__file__), "asn1", "POIM-PA-Standalone.asn")
_DB = asn1tools.compile_files([_ASN1_FILE], codec="uper")

# ---------------------------------------------------------------------------
# POIM envelope constants
# ---------------------------------------------------------------------------

POIM_PROTOCOL_VERSION: int = 1
POIM_MESSAGE_ID: int = 6          # ETSI TS 102 894-2 §6.1.68
POIM_BTP_PORT: int = 2009          # ETSI TS 102 636-5-1 (assigned for POIM)
POI_TYPE_PARKING_AVAILABILITY: int = 1

# 9-byte fixed envelope: B B I B H  (total = 1+1+4+1+2 = 9)
_ENVELOPE_FMT = ">BBIBH"
_ENVELOPE_SIZE = struct.calcsize(_ENVELOPE_FMT)

# ---------------------------------------------------------------------------
# TimestampIts helpers
# ---------------------------------------------------------------------------

_TIMESTAMP_EPOCH = datetime.datetime(2004, 1, 1, tzinfo=datetime.timezone.utc)


def _now_timestamp_its() -> int:
    """Return current time as milliseconds since 2004-01-01 UTC."""
    delta = datetime.datetime.now(datetime.timezone.utc) - _TIMESTAMP_EPOCH
    return int(delta.total_seconds() * 1000)


# ---------------------------------------------------------------------------
# Scaling helpers (ETSI ITS conventions)
# ---------------------------------------------------------------------------

_LAT_SCALE = 1e7      # 1e-7 degrees per integer unit
_LON_SCALE = 1e7
_ALT_SCALE = 1e2      # 0.01 m per integer unit

_LAT_UNAVAILABLE = 900000001
_LON_UNAVAILABLE = 1800000001
_ALT_UNAVAILABLE = 800001


def _deg_to_lat(deg: float) -> int:
    v = round(deg * _LAT_SCALE)
    return v if -900000000 <= v <= 900000000 else _LAT_UNAVAILABLE


def _deg_to_lon(deg: float) -> int:
    v = round(deg * _LON_SCALE)
    return v if -1800000000 <= v <= 1800000000 else _LON_UNAVAILABLE


def _m_to_alt(m: float) -> int:
    v = round(m * _ALT_SCALE)
    return v if -100000 <= v <= 800000 else _ALT_UNAVAILABLE


def _lat_to_deg(raw: int):
    return raw / _LAT_SCALE if raw != _LAT_UNAVAILABLE else None


def _lon_to_deg(raw: int):
    return raw / _LON_SCALE if raw != _LON_UNAVAILABLE else None


def _alt_to_m(raw: int):
    return raw / _ALT_SCALE if raw != _ALT_UNAVAILABLE else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def encode(
    *,
    # --- POIM envelope ---
    station_id: int = 0,
    # --- Management container ---
    provider_country_code: bytes = b"\x00\x00",   # 10-bit BIT STRING → 2 bytes (6 bits padding)
    provider_id: int = 0,
    block_id: int = 1,
    timestamp_its: int | None = None,
    # --- Place info ---
    facility_lat: float,
    facility_lon: float,
    facility_alt: float = 800001 / _ALT_SCALE,
    facility_name: str = "Parking",
    # --- Aggregated status ---
    opening_status: str = "open",
    total_spaces: int = 0,
    free_spaces: int = 0,
    occupancy_rate: int = 0,
    occupancy_trend: str = "unknown",
    occupancy_confidence: int = 101,          # 101 = unavailable
) -> bytes:
    """Encode a POIM-PA message as a BTP payload byte string.

    Returns the 9-byte POIM envelope followed by the UPER-encoded
    ``ParkingAvailabilityBlock``.

    Args:
        station_id: Own ITS station identifier.  ``0`` means the BTP stack
            fills it in automatically.
        provider_country_code: ISO 3166-1 country code packed as 2 bytes with
            6 zero padding bits (10 significant bits, MSB first). For example
            Germany ``0x36 0x40`` or just leave at the default ``0x00 0x00``.
        provider_id: 16-bit integer identifying the service provider within
            the country.
        block_id: Identifier of this POI Information Block (0–65535).  This
            is the same as ``poi_id`` in the previous implementation.
        timestamp_its: Generation timestamp in milliseconds since
            2004-01-01 UTC.  Defaults to the current time.
        facility_lat: Parking facility latitude in decimal degrees (WGS-84).
        facility_lon: Parking facility longitude in decimal degrees (WGS-84).
        facility_alt: Parking facility altitude in metres (WGS-84).
            Defaults to the ``AltitudeValue`` unavailable sentinel.
        facility_name: Human-readable name of the parking facility
            (1–31 UTF-8 characters).
        opening_status: One of ``"open"``, ``"closed"``, or ``"unknown"``.
        total_spaces: Total number of parking spaces (0–65535).
        free_spaces: Number of currently free spaces (0–65535).
        occupancy_rate: Occupancy percentage 0–100.
        occupancy_trend: One of ``"increasing"``, ``"stable"``,
            ``"decreasing"``, or ``"unknown"``.
        occupancy_confidence: Confidence level 0–100; ``101`` = unavailable.

    Returns:
        Encoded bytes (9-byte envelope + UPER block).
    """
    if timestamp_its is None:
        timestamp_its = _now_timestamp_its()

    block = {
        "managementContainer": {
            "serviceProviderId": {
                "countryCode": (provider_country_code, 10),   # (bytes, bit-length)
                "providerIdentifier": provider_id,
            },
            "blockIdentificationNumber": block_id,
            "timestamp": timestamp_its,
        },
        "placeInfo": {
            "position": {
                "latitude": _deg_to_lat(facility_lat),
                "longitude": _deg_to_lon(facility_lon),
                "altitude": _m_to_alt(facility_alt),
            },
            "name": facility_name[:31],
        },
        "aggregatedStatus": {
            "currentFacilityStatus": opening_status,
            "currentOccupancy": {
                "rate": max(0, min(100, occupancy_rate)),
                "trend": occupancy_trend,
                "freeSpaces": max(0, min(65535, free_spaces)),
                "totalSpaces": max(0, min(65535, total_spaces)),
                "confidence": max(0, min(101, occupancy_confidence)),
            },
        },
    }

    uper_block: bytes = _DB.encode("ParkingAvailabilityBlock", block)
    envelope = struct.pack(
        _ENVELOPE_FMT,
        POIM_PROTOCOL_VERSION,             # B
        POIM_MESSAGE_ID,                   # B
        station_id & 0xFFFFFFFF,           # I
        POI_TYPE_PARKING_AVAILABILITY,     # B
        len(uper_block),                   # H
    )
    return envelope + uper_block


def decode(data: bytes) -> dict:
    """Decode a POIM-PA BTP payload produced by :func:`encode`.

    Args:
        data: Raw bytes received on BTP port 2009.

    Returns:
        A dictionary with human-readable field values.

    Raises:
        ValueError: If the envelope is malformed or the UPER block cannot be
            decoded.
    """
    if len(data) < _ENVELOPE_SIZE:
        raise ValueError(
            f"POIM-PA payload too short: {len(data)} < {_ENVELOPE_SIZE} bytes"
        )

    proto_ver, msg_id, station_id, poi_type, block_len = struct.unpack_from(
        _ENVELOPE_FMT, data
    )
    uper_block = data[_ENVELOPE_SIZE: _ENVELOPE_SIZE + block_len]

    if len(uper_block) < block_len:
        raise ValueError(
            f"Truncated UPER block: expected {block_len} bytes, got {len(uper_block)}"
        )

    try:
        block = _DB.decode("ParkingAvailabilityBlock", uper_block)
    except Exception as exc:
        raise ValueError(f"UPER decode failed: {exc}") from exc

    mgmt = block["managementContainer"]
    place = block["placeInfo"]
    status = block["aggregatedStatus"]
    occ = status.get("currentOccupancy")

    pos = place["position"]
    return {
        "protocol_version": proto_ver,
        "message_id": msg_id,
        "station_id": station_id,
        "poi_type": poi_type,
        "provider_country_code": mgmt["serviceProviderId"]["countryCode"],
        "provider_id": mgmt["serviceProviderId"]["providerIdentifier"],
        "block_id": mgmt["blockIdentificationNumber"],
        "timestamp_its": mgmt["timestamp"],
        "facility_latitude_deg": _lat_to_deg(pos["latitude"]),
        "facility_longitude_deg": _lon_to_deg(pos["longitude"]),
        "facility_altitude_m": _alt_to_m(pos["altitude"]),
        "facility_name": place["name"],
        "opening_status": status["currentFacilityStatus"],
        "occupancy_rate": occ["rate"] if occ else None,
        "occupancy_trend": occ["trend"] if occ else None,
        "free_spaces": occ["freeSpaces"] if occ else None,
        "total_spaces": occ["totalSpaces"] if occ else None,
        "occupancy_confidence": occ["confidence"] if occ else None,
    }
