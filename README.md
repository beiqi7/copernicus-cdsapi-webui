# copernicus-cdsapi-webui
A simple downloader for Copernicus ERA5 Datasets

Mostly product by ChatGPT

You still need to place your API to "$HOME/.cdsapirc" in your environment

Updated to new beta CDSAPI, but now API download is taking longer time than web download, no recommond at this moment!

## Usage:
pip install flask

python era5.py

Or use your favorite reserved proxy and WSGI app to run it
***
Test: https://era5.akari.icu/

Official API Usage: https://cds.climate.copernicus.eu/api-how-to

CDS-API is now facing some internal problems, it will be unable to download data sometimes
https://forum.ecmwf.int/t/a-new-cds-soon-to-be-launched-expect-some-disruptions/1607
