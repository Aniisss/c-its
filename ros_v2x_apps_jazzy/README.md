# ros_v2x_apps_jazzy – V2X Applications for cube-its (ROS 2 Jazzy)

This workspace provides ROS 2 sample applications for the **cube-its** framework,
targeted at **ROS 2 Jazzy** and cube-its ≥ v1.4.0.

It extends the original `ros_v2x_apps` workspace with a new POIM (Point of
Interest Message) facility that implements **ETSI TS 103 916 V2.1.1** parking
availability messaging on top of the cube-its BTP service.

---

## Contents

1. [cube-its overview](#cube-its-overview)
2. [Prerequisites](#prerequisites)
3. [Code examples](#code-examples)
   - 3.1 [CAM listener](#31-cooperative-awareness-message-listener)
   - 3.2 [DENM node](#32-decentralized-environmental-notification-message)
   - 3.3 [CPM provider](#33-collective-perception-message)
   - 3.4 [VAM provider](#34-vulnerable-road-user-awareness-message)
   - 3.5 [POIM provider & listener](#35-point-of-interest-message-poim--parking-availability) ← **new**
4. [Build and run](#build-and-run)

---

## cube-its overview

<img src="https://img.shields.io/badge/cube--its-≥v1.4.0-green"/>
<img src="https://img.shields.io/badge/ROS%202-jazzy-blue"/>

The **cube-its** framework integrates Intelligent Transportation Systems (ITS)
applications and V2X communication within ROS 2, using the
[Vanetza](https://www.vanetza.org/) library.

### Supported ETSI ITS messages

| Status | Acronym | Standard | Supported in cube-its | Facility pattern |
|---|---|---|---|---|
| ✅ | CAM | EN 302 637-2 V1.4.1 | ≥ v1.0.0 | Subscribe `/its/cam_received` |
| ✅ | DENM | EN 302 637-3 V1.3.1 | ≥ v1.0.0 | Service `/its/den_request` |
| ✅ | CPM | TS 103 324 V2.1.1 | ≥ v1.2.0 | Publish `/its/cpm_provided` |
| ✅ | VAM | TS 103 300-3 V2.2.1 | ≥ v1.3.0 | Publish `/its/vam_provided` |
| 🆕 | **POIM** | **TS 103 916 V2.1.1** | *user-space implementation* | **BTP service** (see §3.5) |

---

## Prerequisites

- A [cube device](https://www.nfiniity.com/#hardware-section) running cube-its ≥ v1.4.0
- Docker (recommended) **or** a native ROS 2 Jazzy installation
- Python package `asn1tools` (required for POIM):

  ```bash
  pip install asn1tools
  ```

### ROS 2 node visibility

```bash
# Allow cube-its and your nodes to discover each other
export ROS_LOCALHOST_ONLY=0

# Use the same domain as cube-its (default 42)
export ROS_DOMAIN_ID=42
```

---

## Code examples

```
dev_ws/src/v2x_apps/
├── v2x_apps/
│   ├── btp_listener.py
│   ├── btp_sender.py
│   ├── cam_listener.py
│   ├── cpm_bridge.py
│   ├── cpm_provider.py
│   ├── denm_node.py
│   ├── vam_provider.py
│   ├── poim_provider.py       ← new
│   ├── poim_listener.py       ← new
│   └── asn1/
│       └── poim_ts103916.asn  ← POIM ASN.1 schema (ETSI TS 103 916 V2.1.1)
└── c2c/
    └── stationary_vehicle_trigger.py
```

### 3.1 Cooperative Awareness Message listener

Subscribes to `/its/cam_received` and logs the station ID of every received CAM.

```bash
ros2 run v2x_apps cam_listener
```

### 3.2 Decentralized Environmental Notification Message

Sends and receives DENMs via the cube-its DEN service.

```bash
ros2 run v2x_apps denm_node
```

### 3.3 Collective Perception Message

Publishes CPMs to `/its/cpm_provided`; cube-its handles encoding and BTP transmission.

```bash
ros2 run v2x_apps cpm_provider
```

### 3.4 Vulnerable Road User Awareness Message

Publishes VAMs to `/its/vam_provided`.

```bash
ros2 run v2x_apps vam_provider
```

### 3.5 Point of Interest Message (POIM – Parking Availability)

**New** — implements the POIM facility layer (ETSI TS 103 916 V2.1.1) in user space.

Because cube-its does not yet have a native POIM facility, this node performs
the full encode-and-transmit cycle:

```
parking sensor  →  /parking/spaces_available  →  poim_provider
                                                       ↓
                                            ASN.1 UPER encode
                                                       ↓
                                          /vanetza/btp_request  →  cube-its  →  ITS-G5 radio
```

Run the provider:

```bash
ros2 run v2x_apps poim_provider
```

Publish a test parking availability value:

```bash
ros2 topic pub /parking/spaces_available std_msgs/msg/Int32 '{data: 42}' --once
```

Run the listener to receive POIM messages from other stations:

```bash
ros2 run v2x_apps poim_listener
```

📖 **For the full POIM documentation, see [POIM_README.md](./POIM_README.md).**

---

## Build and run

Navigate to the workspace root:

```bash
cd ros_v2x_apps_jazzy/dev_ws
```

Source the cube-its setup and build:

```bash
source /opt/cube/*/setup.bash
colcon build --packages-select v2x_apps
source install/setup.bash
```

Run any node:

```bash
ros2 run v2x_apps <node_name>
```

Available nodes:

| Node | Description |
|---|---|
| `cam_listener` | Print received CAMs |
| `denm_node` | Send / receive DENMs |
| `cpm_provider` | Provide CPMs with lidar data |
| `vam_provider` | Provide VAMs for a pedestrian |
| `btp_listener` | Print raw BTP packets |
| `btp_sender` | Send a raw BTP test packet |
| `poim_provider` | **Encode and transmit POIM (parking availability)** |
| `poim_listener` | **Receive and decode incoming POIM messages** |
