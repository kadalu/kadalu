from setuptools import setup


setup(
    name="glustercs",
    version="0.9.4",
    packages=["kubectl_gluster"],
    include_package_data=True,
    install_requires=["jinja2", "PyYAML", "requests"],
    entry_points={
        "console_scripts": [
            "kubectl-gluster = kubectl_gluster.main:main"
        ]
    },
    platforms="linux",
    zip_safe=False,
    author="Gluster Developers",
    author_email="gluster-devel@gluster.org",
    description="GlusterCS deployment tool",
    license="GPLv2",
    keywords="gluster, container, kubernetes, glustercs",
    url="https://github.com/aravindavk/kubectl-gluster",
    long_description="""
    GlusterCS deployment tool
    """,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "Environment :: Console",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
    ],
)
