# -*- coding: utf-8 -*-
from setuptools import setup


setup(
    name="kadalu",
    version="0.8.4",
    packages=["kadalu", "kadalu.operator", "kadalu.csi", "kadalu.server", "kadalu.common"],
    include_package_data=True,
    install_requires=["xxhash", "jinja2", "pyxattr", "uvicorn", "fastapi"],
    entry_points={
        "console_scripts": [
            "kadalu-operator = kadalu.operator.start:main",
            "kadalu-csi = kadalu.csi.start:main",
            "kadalu-server = kadalu.server.server:start_server_process",
        ]
    },
    platforms="linux",
    zip_safe=False,
    author="Kadalu Authors",
    author_email="engineering@kadalu.tech",
    description="Kadalu Storage K8S integration"
)
