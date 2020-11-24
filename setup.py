import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ringmaster.show",
    version="0.0.0",
    author="Geoff Williams",
    author_email="None",
    description="master of the ring!",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/declarativesystems/ringmaster",
    packages=setuptools.find_packages(),
    # pick from https://pypi.org/classifiers/
    classifiers=[
        "Development Status :: 1 - Planning",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points={
        "console_scripts": (['ringmaster=ringmaster.cli:main'],)
    },
    include_package_data=True,
    install_requires=[
        "python-dateutil",
        "boto3",
        "snakecase",
        "cfn_flip",

        # https://github.com/snowflakedb/snowflake-connector-python/issues/284
        "snowflake-connector-python-lite",
    ]
)
