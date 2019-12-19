from setuptools import setup


setup(
    name="kadalu_quotad",
    version="0.1.0",
    packages=["kadalu_quotad"],
    include_package_data=True,
    install_requires=[""],
    entry_points={
        "console_scripts": [
            "kadalu_quotad = quotad.start:main"
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
