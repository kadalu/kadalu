from setuptools import setup

def version():
    with open("VERSION") as version_file:
        return version_file.read().strip()


setup(
    name="kubectl-kadalu",
    version=version(),
    packages=["kubectl_kadalu"],
    include_package_data=True,
    install_requires=["PyYAML"],
    entry_points={
        "console_scripts": [
            "kubectl-kadalu = kubectl_kadalu.main:main",
            "oc-kadalu = kubectl_kadalu.main:main"
        ]
    },
    platforms="linux",
    zip_safe=False,
    author="Kadalu Authors",
    author_email="support@kadalu.io",
    description="Kadalu Kubectl Plugin",
    license="Apache-2.0",
    keywords="kadalu, container, kubernetes, kubectl",
    url="https://github.com/kadalu/kadalu",
    long_description="""
    Kadalu Kubectl Plugin
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
