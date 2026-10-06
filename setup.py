from setuptools import setup, find_packages

setup(
    name="brazilian-rates-intelligence",
    version="0.1.0",
    description="A quantitative framework for understanding the Brazilian yield curve",
    author="Brazilian Rates Intelligence Desk",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "scikit-learn>=1.2.0",
        "statsmodels>=0.14.0",
        "streamlit>=1.28.0",
        "plotly>=5.15.0",
        "yfinance>=0.2.20",
        "python-bcb>=0.2.0",
        "pyettj>=0.1.0",
    ],
)
