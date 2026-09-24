from setuptools import setup, find_packages

setup(
    name="alphapilot",
    version="1.0.0",
    packages=find_packages(include=["alphapilot", "alphapilot.*"]),
    install_requires=["requests>=2.31", "pandas>=2.0", "tqdm>=4.65", "PyYAML>=6.0"],
    entry_points={"console_scripts": ["alphapilot=alphapilot.cli:main"]},
    python_requires=">=3.9",
)
