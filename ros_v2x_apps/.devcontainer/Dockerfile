# CUBE devcontainer
ARG WORKSPACE_VERSION="jazzy-develop"
FROM ghcr.io/cubesys-gmbh/workspace:${WORKSPACE_VERSION}

SHELL ["/bin/bash", "-c"]

# Switch to root
USER root

# Ensure valid ROS2 public key
RUN wget -O /usr/share/keyrings/ros-archive-keyring.gpg \
    https://raw.githubusercontent.com/ros/rosdistro/master/ros.key

# Install required packages (sudo + git)
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get -y install --no-install-recommends sudo git && \
    rm -rf /var/lib/apt/lists/*

# Arguments
ARG USERNAME="cube"
ARG USER_HOME_DIR=/home/${USERNAME}

# Give sudo privileges to the user
RUN usermod -aG sudo ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Switch back to normal user
USER ${USERNAME}

# Default command
CMD ["bash"]