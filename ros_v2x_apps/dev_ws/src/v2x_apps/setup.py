from setuptools import find_packages, setup

import os
from glob import glob

package_name = 'v2x_apps'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'asn1'), glob('v2x_apps/asn1/*.asn')),
        (os.path.join('share', package_name, 'www'), glob('www/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Apostolos Georgiadis',
    maintainer_email='apostolos.georgiadis@nfiniity.com',
    description='Collection of V2X applications utilizing cube devices',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
                'btp_listener = v2x_apps.btp_listener:main',
                'btp_sender = v2x_apps.btp_sender:main',
                'cam_listener = v2x_apps.cam_listener:main',
                'denm_node = v2x_apps.denm_node:main',
                'cpm_provider = v2x_apps.cpm_provider:main',
                'vam_provider = v2x_apps.vam_provider:main',
                'stationary_vehicle = c2c.stationary_vehicle_trigger:main',
                'cpm_bridge = v2x_apps.cpm_bridge:main',
                'poim_provider = v2x_apps.poim_provider:main',
                'poim_listener = v2x_apps.poim_listener:main',
                'ldm_server = v2x_apps.ldm_server:main',
        ],
},
)
