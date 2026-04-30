# POIM – Point of Interest Message (Parking Availability)
### ETSI TS 103 916 V2.1.1 Facility Layer for cube-its

---

## Table of Contents

1. [Background](#1-background)
2. [ETSI TS 103 916 – Standard Overview](#2-etsi-ts-103-916--standard-overview)
   - 2.1 [POIM Structure](#21-poim-structure)
   - 2.2 [ASN.1 Schema](#22-asn1-schema)
   - 2.3 [Protocol Parameters](#23-protocol-parameters)
3. [Why a Separate Facility Layer?](#3-why-a-separate-facility-layer)
4. [Architecture](#4-architecture)
5. [Nodes](#5-nodes)
   - 5.1 [poim_provider](#51-poim_provider)
   - 5.2 [poim_listener](#52-poim_listener)
6. [ROS 2 Interface Reference](#6-ros-2-interface-reference)
   - 6.1 [Topics](#61-topics)
   - 6.2 [Parameters](#62-parameters)
7. [ASN.1 Encoding Details](#7-asn1-encoding-details)
8. [Build and Run](#8-build-and-run)
9. [Verifying Standard Compliance](#9-verifying-standard-compliance)
10. [Extending the Implementation](#10-extending-the-implementation)

---

## 1. Background

The **cube-its** platform provides native facility layers for the following
ETSI ITS message types:

| Facility | Standard | cube-its topic |
|---|---|---|
| CAM | EN 302 637-2 | `/its/cam_received` |
| DENM | EN 302 637-3 | `/its/den_request` |
| CPM | TS 103 324 | `/its/cpm_provided` |
| VAM | TS 103 300-3 | `/its/vam_provided` |

**POIM** (Point of Interest Message for Parking Availability) is defined in
**ETSI TS 103 916 V2.1.1** but is not yet part of cube-its.
This package adds the missing facility layer entirely in user space, on top
of the raw BTP service that cube-its already exposes.

---

## 2. ETSI TS 103 916 – Standard Overview

> **Reference document:**
> ETSI TS 103 916 V2.1.1 – *Intelligent Transport Systems (ITS);
> ITS application layer; Point of Interest Message for Parking Availability*
>
> ASN.1 module: <https://forge.etsi.org/rep/ITS/asn1/poim_ts103916>

### 2.1 POIM Structure

A POIM packet consists of three layers:

```
POIM (top-level PDU)
├── ItsPduHeader
│   ├── protocolVersion   INTEGER  (0..255)
│   ├── messageID         INTEGER  (0..255)   ← POIM-specific ID
│   └── stationID         INTEGER  (0..4 294 967 295)
└── PoiBody
    ├── generationDeltaTime   GenerationDeltaTime  ← ms since 2004-01-01, mod 65 536
    └── poiContainers         SEQUENCE (SIZE 1..8) OF PoiContainer
        └── PoiContainer ::= CHOICE
            └── parkingFacility  ParkingFacilityContainer
                ├── poiID                   INTEGER (0..65535)   ← facility identifier
                ├── referencePosition       ReferencePosition    ← WGS-84 lat/lon/alt
                ├── parkingSpacesAvailable  INTEGER (0..65535)   ← free spaces (mandatory)
                ├── parkingSpacesTotal      INTEGER (0..65535)   ← capacity (OPTIONAL)
                ├── parkingSpacesOccupied   INTEGER (0..65535)   ← used spaces (OPTIONAL)
                └── validityDuration        INTEGER (0..86400)   ← seconds (OPTIONAL)
```

The `ReferencePosition` type follows the ETSI CDD
(ETSI TS 102 894-2) coordinate convention:

| Field | Unit | Unavailable sentinel |
|---|---|---|
| latitude | 1/10 µ° (×10⁷) | 900 000 001 |
| longitude | 1/10 µ° (×10⁷) | 1 800 000 001 |
| semiMajorConfidence | cm (×10²) | 4 094 |
| semiMinorConfidence | cm (×10²) | 4 094 |
| semiMajorOrientation | 0.1° steps from WGS-84 North | 3 601 |
| altitudeValue | cm (×10²) | 800 001 |

### 2.2 ASN.1 Schema

The schema file bundled with this package is:

```
dev_ws/src/v2x_apps/v2x_apps/asn1/poim_ts103916.asn
```

It defines all POIM types in a single self-contained ASN.1 module
(`POIM-PDU-Descriptions`) and is loaded at node start-up by the
[`asn1tools`](https://pypi.org/project/asn1tools/) library.

> **Important:** The schema in this repository is a faithful reconstruction
> based on ETSI TS 103 916 V2.1.1.  Before deploying in a production
> environment, compare it against the official ASN.1 files on the ETSI Forge
> and update any type definitions, constraints, or field names if they differ.

### 2.3 Protocol Parameters

These values come from the standard and are exposed as ROS 2 parameters so
nothing is hardcoded:

| Parameter | Standard reference | Default |
|---|---|---|
| `btp_port` | ETSI TS 103 916 §7 (Communication Profile) Table 1 | **2019** |
| `message_id` | ETSI TS 102 894-2 (CDD) messageID registry | **26** |
| `protocol_version` | ETSI TS 103 916 §5 | **2** |

> **Verify these values against the published standard before using.**
> Use `ros2 run v2x_apps poim_provider --ros-args -p btp_port:=<correct_port>`
> to override without modifying the source code.

---

## 3. Why a Separate Facility Layer?

In cube-its, the CPM facility layer works like this:

```
Your node  ──publish──►  /its/cpm_provided  ──►  cube-its (encodes + sends BTP)
```

For POIM, cube-its does not yet expose a `/its/poim_provided` topic.
Instead, this package uses the lower-level BTP service that cube-its
already provides:

```
poim_provider  ──ASN.1 encode──►  raw bytes  ──BTP service──►  cube-its  ──►  radio
```

This approach:
- Requires **no changes to cube-its**
- Is fully standards-compliant (proper ASN.1 UPER encoding)
- Keeps all protocol parameters configurable via ROS 2 parameters

---

## 4. Architecture

```
                        ┌──────────────────────────────────────────────┐
                        │              cube-its container               │
  /its/position_vector ◄┤  GNSS / Kinematics                           │
                        │                                               │
  /vanetza/btp_request ►┤  Vanetza BTP service  ──► ITS-G5 radio      │
 /vanetza/btp_indication┤◄ Vanetza BTP service  ◄── ITS-G5 radio      │
                        └──────────────────────────────────────────────┘
                                         ▲ ▼
                        ┌──────────────────────────────────────────────┐
                        │         ros_v2x_apps_jazzy container          │
                        │                                               │
  /its/position_vector ─┼──► poim_provider                             │
  /parking/spaces_*    ─┼──►   │  build POIM struct                   │
                        │      │  encode ASN.1 UPER (asn1tools)         │
                        │      └──► /vanetza/btp_request (BTP-B)       │
                        │                                               │
 /vanetza/btp_indication┼──► poim_listener                             │
                        │      │  filter by BTP port                   │
                        │      │  decode ASN.1 UPER                    │
                        │      └──► /parking/received/*                │
                        └──────────────────────────────────────────────┘
```

---

## 5. Nodes

### 5.1 `poim_provider`

Generates and transmits POIM messages at a configurable rate.

**What it does:**

1. Subscribes to `/its/position_vector` (published by cube-its) to obtain the
   station's current WGS-84 position and confidence information.
2. Subscribes to `/parking/spaces_available` to receive real-time parking data.
3. Optionally subscribes to `/parking/spaces_total` and
   `/parking/spaces_occupied` for richer data.
4. Every publish cycle it:
   - Reads the current parameter values (BTP port, message ID, etc.)
   - Converts all coordinates with the ETSI CDD scaling factors
   - Builds the complete `POIM` ASN.1 structure
   - Encodes it with UPER using `asn1tools`
   - Sends the raw bytes to cube-its via `/vanetza/btp_request`

**Key design decisions:**

- All protocol constants (BTP port, message ID, protocol version) are ROS 2
  parameters – never hardcoded.
- The ASN.1 schema is loaded from a separate `.asn` file, making it easy to
  update when the official schema is published.
- `OPTIONAL` fields are omitted automatically when no value is available,
  keeping the encoding compact.

### 5.2 `poim_listener`

Receives POIM messages from other ITS stations and republishes the parking data.

**What it does:**

1. Subscribes to `/vanetza/btp_indication` (all BTP packets received by cube-its).
2. Filters packets by the POIM BTP-B port (configurable parameter).
3. Decodes each matching packet as a POIM using `asn1tools`.
4. Publishes the extracted parking data on dedicated ROS 2 topics.

---

## 6. ROS 2 Interface Reference

### 6.1 Topics

#### `poim_provider` subscriptions

| Topic | Type | Description |
|---|---|---|
| `/its/position_vector` | `vanetza_msgs/PositionVector` | Own WGS-84 position from cube-its |
| `/parking/spaces_available` | `std_msgs/Int32` | Number of free parking spaces |
| `/parking/spaces_total` | `std_msgs/Int32` | Total capacity (optional) |
| `/parking/spaces_occupied` | `std_msgs/Int32` | Number of occupied spaces (optional) |

#### `poim_listener` subscriptions

| Topic | Type | Description |
|---|---|---|
| `/vanetza/btp_indication` | `vanetza_msgs/BtpDataIndication` | All incoming BTP packets |

#### `poim_listener` publications

| Topic | Type | Description |
|---|---|---|
| `/parking/received/spaces_available` | `std_msgs/Int32` | Free spaces from received POIM |
| `/parking/received/spaces_total` | `std_msgs/Int32` | Total capacity from received POIM |
| `/parking/received/spaces_occupied` | `std_msgs/Int32` | Occupied spaces from received POIM |

### 6.2 Parameters

All parameters for both nodes are listed below with their default values.
Every value can be overridden on the command line using `--ros-args -p <name>:=<value>`.

#### `poim_provider` parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `btp_port` | int | `2019` | BTP-B destination port (ETSI TS 103 916 Table 1) |
| `message_id` | int | `26` | `ItsPduHeader.messageID` for POIM |
| `protocol_version` | int | `2` | `ItsPduHeader.protocolVersion` |
| `poi_id` | int | `1` | Unique identifier of this parking facility |
| `parking_total` | int | `0` | Static total capacity; `0` = omit field |
| `validity_duration` | int | `600` | Information validity in seconds; `0` = omit |
| `publish_rate_hz` | float | `1.0` | POIM generation frequency |
| `transport_type` | str | `'SHB'` | `'SHB'` (single hop) or `'GBC'` (geo-broadcast) |
| `asn1_schema_path` | str | `''` | Override path to `.asn` schema file |

#### `poim_listener` parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `btp_port` | int | `2019` | BTP-B port to filter incoming packets on |
| `asn1_schema_path` | str | `''` | Override path to `.asn` schema file |

---

## 7. ASN.1 Encoding Details

### Encoding rule

ETSI ITS application-layer messages are encoded with
**UPER (Unaligned Packed Encoding Rules)** as standardised in
ISO/IEC 8825-2 and referenced throughout the ETSI ITS suite.

The `asn1tools` library is used:

```python
import asn1tools
db = asn1tools.compile_files('poim_ts103916.asn', codec='uper')

encoded_bytes = db.encode('POIM', poim_dict)
decoded_dict  = db.decode('POIM', encoded_bytes)
```

### `CHOICE` encoding in `asn1tools`

The `PoiContainer` type is a `CHOICE`.  `asn1tools` represents CHOICE
values as Python tuples `(choice_name: str, value: dict)`:

```python
# Building a PoiContainer for a parking facility
container = ('parkingFacility', {
    'poiId': 42,
    'referencePosition': { ... },
    'parkingSpacesAvailable': 15,
    'parkingSpacesTotal': 100,
    'validityDuration': 600,
})
```

### `GenerationDeltaTime`

```python
epoch_2004_ms  = 1_072_915_200_000   # 2004-01-01T00:00:00Z in Unix ms
gen_delta_time = (int(time.time() * 1000) - epoch_2004_ms) % 65536
```

### Coordinate conversion

```python
lat_encoded = int(round(latitude_degrees * 1e7))   # e.g.  48.1234° → 481234000
lon_encoded = int(round(longitude_degrees * 1e7))
alt_encoded = int(round(altitude_meters  * 1e2))   # e.g.  100 m    → 10000
semi_major  = int(round(semi_major_m     * 1e2))   # e.g.  0.5 m    → 50
```

---

## 8. Build and Run

### Prerequisites

- cube-its ≥ v1.4.0 running on the same host (or same network with the same
  `ROS_DOMAIN_ID`)
- ROS 2 Jazzy workspace from cube-its
- Python package `asn1tools` ≥ 0.162.0:

```bash
pip install asn1tools
```

### Build

```bash
cd ros_v2x_apps_jazzy/dev_ws
source /opt/cube/*/setup.bash        # source the cube-its workspace
colcon build --packages-select v2x_apps
source install/setup.bash
```

### Run the POIM provider (transmit side)

```bash
# With all defaults (reads parking data from /parking/spaces_available)
ros2 run v2x_apps poim_provider

# Override protocol parameters without touching source code
ros2 run v2x_apps poim_provider --ros-args \
    -p btp_port:=2019 \
    -p message_id:=26 \
    -p poi_id:=7 \
    -p parking_total:=200 \
    -p validity_duration:=300 \
    -p publish_rate_hz:=0.5 \
    -p transport_type:=SHB
```

### Publish test parking data

```bash
# Publish a static parking availability value
ros2 topic pub /parking/spaces_available std_msgs/msg/Int32 '{data: 42}' --once

# Publish continuously (simulating a parking sensor)
ros2 topic pub /parking/spaces_available std_msgs/msg/Int32 '{data: 15}' --rate 1
```

### Run the POIM listener (receive side)

```bash
ros2 run v2x_apps poim_listener
```

### Expected output – provider

```
[INFO] [poim_provider]: Node "poim_provider" started
[INFO] [poim_provider]: POIM ASN.1 schema loaded from: .../asn1/poim_ts103916.asn
[INFO] [poim_provider]: POIM sent: poi_id=1, available=42, payload=28 bytes, btp_port=2019
```

### Expected output – listener

```
[INFO] [poim_listener]: Received BTP indication on port 2019, 28 bytes – attempting POIM decode
[INFO] [poim_listener]: POIM from station 84281098: poi_id=1, available=42, total=200
```

### Using Docker

```bash
# Build the container image
docker build \
    --build-arg WORKSPACE_VERSION=jazzy-develop-1.4.0 \
    -t v2x-apps-jazzy \
    ros_v2x_apps_jazzy/

# Run the POIM provider
docker run --rm --net=host \
    -e ROS_DOMAIN_ID=42 \
    -e ROS_LOCALHOST_ONLY=0 \
    v2x-apps-jazzy \
    ros2 run v2x_apps poim_provider
```

---

## 9. Verifying Standard Compliance

### BTP port and message ID

Compare the defaults in this implementation against the values published in:

- **ETSI TS 103 916 V2.1.1**, Table 1 (Communication Profile) → `btp_port`
- **ETSI TS 102 894-2** (CDD), messageID registry → `message_id`

Both values are configurable ROS 2 parameters and can be corrected without
modifying the source code:

```bash
ros2 run v2x_apps poim_provider --ros-args \
    -p btp_port:=<correct_port> \
    -p message_id:=<correct_id>
```

### ASN.1 schema

Download the official schema from the ETSI Forge:

```
https://forge.etsi.org/rep/ITS/asn1/poim_ts103916
```

Compare it with `dev_ws/src/v2x_apps/v2x_apps/asn1/poim_ts103916.asn` in
this repository and update any type definitions or constraints that differ.
The node will automatically pick up the updated schema on the next start-up
because it compiles the schema at runtime.

If you need to use a schema file at a custom path:

```bash
ros2 run v2x_apps poim_provider --ros-args \
    -p asn1_schema_path:=/path/to/your/poim_ts103916.asn
```

### End-to-end validation

Use a packet analyser (e.g. Wireshark with the ETSI ITS dissector) or the
ETSI ITS conformance test suite (ETSI TR 103 099) to validate that transmitted
POIM packets are correctly formed.

---

## 10. Extending the Implementation

### Adding EV charging station support

ETSI TS 103 916 defines additional POI container types (EV charging stations,
fuel stations, …).  To add support for a new type:

1. Add the new type to `asn1/poim_ts103916.asn` under `PoiContainer ::= CHOICE`:

   ```asn1
   PoiContainer ::= CHOICE {
       parkingFacility      ParkingFacilityContainer,
       evChargingStation    EvChargingStationContainer   -- new
   }
   ```

2. Define `EvChargingStationContainer` in the same schema file following the
   structure in the standard.

3. In `poim_provider.py`, build and append the new container type:

   ```python
   container = ('evChargingStation', {
       'poiId': ev_poi_id,
       'referencePosition': ref_pos,
       'chargersAvailable': chargers_free,
   })
   ```

4. Add new ROS 2 subscriptions and parameters as needed.

### Connecting a real parking sensor

Replace the manual `ros2 topic pub` command with a node that reads from your
actual parking sensor and publishes to `/parking/spaces_available`.
`poim_provider` will automatically include the latest value in the next POIM.

### Adjusting the publish rate

Increase the rate for highly dynamic parking environments or reduce it to
minimise channel load:

```bash
ros2 run v2x_apps poim_provider --ros-args -p publish_rate_hz:=2.0
```
