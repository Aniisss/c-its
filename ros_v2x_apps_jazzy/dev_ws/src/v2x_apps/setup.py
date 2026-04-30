from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'v2x_apps'

setup(
    name=package_name,
    version='1.1.0',
    packages=find_packages(exclude=['test']),
    # Include the POIM ASN.1 schema so it is installed alongside the Python code
    package_data={
        package_name: ['asn1/*.asn'],
    },
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Apostolos Georgiadis',
    maintainer_email='apostolos.georgiadis@nfiniity.com',
    description='Collection of V2X applications for cube-its (ROS 2 Jazzy), '
                'including POIM provider and listener (ETSI TS 103 916 V2.1.1)',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # ── Existing apps ──────────────────────────────────────────────
            'btp_listener        = v2x_apps.btp_listener:main',
            'btp_sender          = v2x_apps.btp_sender:main',
            'cam_listener        = v2x_apps.cam_listener:main',
            'denm_node           = v2x_apps.denm_node:main',
            'cpm_provider        = v2x_apps.cpm_provider:main',
            'cpm_bridge          = v2x_apps.cpm_bridge:main',
            'vam_provider        = v2x_apps.vam_provider:main',
            'stationary_vehicle  = c2c.stationary_vehicle_trigger:main',
            # ── POIM facility (ETSI TS 103 916 V2.1.1) ────────────────────
            'poim_provider       = v2x_apps.poim_provider:main',
            'poim_listener       = v2x_apps.poim_listener:main',
        ],
    },
)
