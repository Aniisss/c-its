# CUBE devcontainer (Jazzy)
ARG WORKSPACE_VERSION="jazzy-develop"
FROM ghcr.io/cubesys-gmbh/workspace:${WORKSPACE_VERSION}

SHELL ["/bin/bash", "-c"]

# Switch to root for package installation
USER root

# Ensure a valid ROS 2 public key
RUN wget -O /usr/share/keyrings/ros-archive-keyring.gpg \
    https://raw.githubusercontent.com/ros/rosdistro/master/ros.key

# Install required system packages
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get -y install --no-install-recommends sudo git && \
    rm -rf /var/lib/apt/lists/*

ARG USERNAME="cube"
ARG USER_HOME_DIR=/home/${USERNAME}

# Grant sudo to the workspace user
RUN usermod -aG sudo ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Install asn1tools for POIM ASN.1 encoding
RUN pip install --no-cache-dir asn1tools

USER ${USERNAME}

CMD ["bash"]
