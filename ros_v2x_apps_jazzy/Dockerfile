ARG WORKSPACE_VERSION="jazzy-develop"
FROM ghcr.io/cubesys-gmbh/workspace:${WORKSPACE_VERSION}

USER cube

# Install the ASN.1 encoding library required by the POIM provider and listener.
# asn1tools provides standards-compliant UPER / PER / OER encoding for the
# POIM ASN.1 schema defined in dev_ws/src/v2x_apps/v2x_apps/asn1/poim_ts103916.asn
RUN pip install --no-cache-dir asn1tools

COPY --chown=cube dev_ws/src /home/cube/dev_ws/src
WORKDIR /home/cube/dev_ws
RUN source /opt/cube/*/setup.bash && colcon build

COPY --chmod=755 <<EOF entrypoint.bash
#!/bin/bash
source /home/cube/dev_ws/install/setup.bash
exec "$@"
EOF
ENTRYPOINT ["/home/cube/dev_ws/entrypoint.bash"]
CMD ["ros2", "run", "v2x_apps", "cam_listener"]
