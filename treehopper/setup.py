from setuptools import setup, find_packages

setup(
    name="treehopper",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi",
        "uvicorn",
        "httpx",
        "python-dotenv",
        "chromadb",
        "PyMuPDF",
    ],
    entry_points={
        "console_scripts": [
            "treehopper=treehopper.treehopper_cli:run",
        ],
    },
    author="Nitin",
    description="Treehopper: A modular agentic automation framework",
    license="MIT",
)
