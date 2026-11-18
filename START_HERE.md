# Start the Electricity Bill Planner

This is a local, single-user academic prototype. It starts with no personal history. No bill photos or real household records are included.

## Setup on another computer
Install Python 3.12, then open a terminal in this extracted folder:

    python3 -m venv .venv

Activate it (Mac/Linux):

    source .venv/bin/activate

On Windows use `.venv\Scripts\activate` and `python` instead of `python3`.

    python -m pip install -r requirements.txt
    python src/check_setup.py
    python -m streamlit run app.py --global.developmentMode false --server.headless true --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false

Open http://127.0.0.1:8501. Keep the terminal open. Stop with Control-C.

Package installation needs internet access. Forecast and OCR model files are included for local inference after setup. This package was tested after extraction with the existing verified Python environment; installation on a new computer has not been tested here.

## Login
For local username/password login, run `python src/create_login_accounts.py` once. The two passwords are saved privately in `.local/LOGIN_DETAILS.txt`. Share only the demo account. For a hosted app, deploy `cloud_app.py` and configure the private secret described in FREE_DEPLOYMENT.md. No credentials are included in this package.

## First use
Add your own monthly readings or photos in My bills. Six consecutive months are needed for a forecast. Add the rates/charges from your bill under Advanced details. The package never looks up official prices automatically. Plan my bill compares three concrete appliance routines and saves only when you accept one.

There are no demonstration bills. Do not treat invented entries as real household evidence. Forecasts and rupee amounts are approximate. The reader can require manual review. This is not a hosted link or multi-user service.

## Included components
App Python source, Streamlit theme, pinned runtime dependencies, frozen Extra Trees artifact with integrity metadata, and the local RapidOCR ONNX files already used by the project. requirements.txt uses upstream package names; third-party libraries/models retain their upstream licensing terms. Training datasets are not distributed here.
