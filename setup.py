from setuptools import setup, find_packages

setup(
    name="vg_api",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "asyncpg",
        "pydantic",
        "pydantic-settings",
    ],
) 