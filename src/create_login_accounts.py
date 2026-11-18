"""Create local owner/demo credentials; plaintext instructions stay in a private local file."""
from pathlib import Path
import json,os,secrets
from access_control import password_hash
ROOT=Path(__file__).resolve().parents[1]

def write_private(path,content):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(content)

def create():
    folder=ROOT/'.local';folder.mkdir(mode=0o700,exist_ok=True)
    if (folder/'auth.json').exists():raise ValueError('Login accounts already exist; they were not overwritten.')
    passwords={name:secrets.token_urlsafe(18) for name in ('owner','demo')}
    config=dict(version=1,accounts={name:dict(role=name,password=password_hash(password)) for name,password in passwords.items()})
    write_private(folder/'auth.json',json.dumps(config,indent=2))
    instructions='Energywise local login details\n\nKeep the OWNER password private. Share only the DEMO password with your teacher/classmates.\n\n'
    for name,password in passwords.items():instructions+=f'Username: {name}\nPassword: {password}\n\n'
    instructions+='Server auth.json contains salted hashes. Do not upload this file or LOGIN_DETAILS.txt to GitHub.\n'
    write_private(folder/'LOGIN_DETAILS.txt',instructions)
    # Streamlit Cloud accepts this as a private root-level secret, not a repo file.
    write_private(folder/'CLOUD_SECRETS.toml',"energy_auth_json = '''"+json.dumps(config)+"'''\n")
    print('Created local login accounts. Open .local/LOGIN_DETAILS.txt on your computer; no passwords printed.')
if __name__=='__main__':create()
