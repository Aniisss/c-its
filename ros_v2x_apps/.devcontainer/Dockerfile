# CUBE devcontainer
ARG WORKSPACE_VERSION="jazzy-develop"
FROM ghcr.io/cubesys-gmbh/workspace:${WORKSPACE_VERSION}

SHELL ["/bin/bash", "-c"]

USER root

# Ensure valid ROS2 public key
RUN wget -O /usr/share/keyrings/ros-archive-keyring.gpg \
    https://raw.githubusercontent.com/ros/rosdistro/master/ros.key

# Install required packages
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        sudo \
        git \
        python3-pip && \
    pip3 install --break-system-packages --ignore-installed \
        asn1tools \
        fastapi \
        "uvicorn[standard]" && \
    rm -rf /var/lib/apt/lists/*

# Arguments
ARG USERNAME="cube"
ARG USER_HOME_DIR=/home/${USERNAME}

# Give sudo privileges to the user
RUN usermod -aG sudo ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER ${USERNAME}

CMD ["bash"]