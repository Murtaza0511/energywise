"""Free Streamlit Community Cloud entry point: fail closed without login secrets."""
import os,runpy
from pathlib import Path
os.environ['ENERGY_REQUIRE_LOGIN']='true'
root=Path(__file__).resolve().parent
runpy.run_path(str(root/'app.py'),run_name='__main__')
