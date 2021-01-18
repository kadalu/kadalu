from setuptools import setup


def version():
    with open("VERSION") as version_file:
        return version_file.read().strip()


setup(
    name="kadalu-quotad",
    version=version(),
    packages=["kadalu_quotad"],
    include_package_data=True,
    install_requires=["xxhash"],
    extras_require={
        "gluster": ["glustercli"]
    },
    entry_points={
        "console_scripts": [
            "kadalu-quotad = kadalu_quotad.quotad:start"
        ]
    },
    platforms="linux",
    zip_safe=False,
    author="Kadalu Authors",
    author_email="support@kadalu.io",
    description="Kadalu Quota Daemon",
    license="Apache-2.0",
    keywords="kadalu, container, kubernetes, kubectl, storage",
    url="https://github.com/kadalu/kadalu",
    long_description="""
    Kadalu Quota Daemon - , to be used when External storage
    is used with kadalu k8s operator.
    """,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "Environment :: Console",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
    ],
)
