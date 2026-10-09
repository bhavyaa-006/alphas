from setuptools import setup, find_packages

setup(
    name="alphapilot",
    version="1.0.0",
    packages=find_packages(include=["alphapilot", "alphapilot.*"]),
    install_requires=["requests>=2.31", "pandas>=2.0", "tqdm>=4.65", "PyYAML>=6.0",
                      "prompt_toolkit>=3.0.47", "rich>=13.7"],
    extras_require={"ai": ["httpx>=0.27"]},
    entry_points={"console_scripts": ["alphapilot=alphapilot.cli:main"]},
    python_requires=">=3.9",
)
