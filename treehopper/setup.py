from setuptools import setup, find_packages

setup(
    name="treehopperai-core",
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
            "th=treehopper.treehopper_cli:run",
        ],
    },
    author="Nitin Kumar Karma",
    description="TreehopperAI: is a local-first, agent-centric, fully open-source \
        automation framework for building intelligent workflows — from \
            edge AI agents to orchestrated micro-services and distributed chains",
    license="MIT",
)
