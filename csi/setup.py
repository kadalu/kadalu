from setuptools import setup


setup(
    name="glustercs-csi",
    version="0.9.4",
    packages=["."],
    include_package_data=True,
    install_requires=["grpcio"],
    entry_points={
        "console_scripts": [
            "glustercs-csi-controllerserver = controllerserver:main",
            "glustercs-csi-nodeserver = nodeserver:main",
            "glustercs-csi-identityserver = identityserver:main",
        ]
    },
    platforms="linux",
    zip_safe=False,
    author="Aravinda VK",
    author_email="mail@aravindavk.in",
    description="GlusterCS CSI drivers",
    license="Apache-2.0",
    keywords="gluster, container, kubernetes, glustercs",
    url="https://github.com/aravindavk/glustercs",
    long_description="""
    GlusterCS CSI drivers
    """,
)
