"""Login gate and isolated visitor workspaces; runs before household data loading."""
from pathlib import Path
import hashlib,json,os,tempfile,time
import streamlit as st
from access_control import validate_config,LoginVerifier

@st.cache_resource
def verifier():return LoginVerifier()

def configured_accounts(root):
    path=Path(os.environ.get('ENERGY_AUTH_CONFIG',str(Path(root)/'.local/auth.json')))
    raw=None
    if path.exists():raw=path.read_text()
    else:
        try:raw=st.secrets.get('energy_auth_json')
        except FileNotFoundError:pass
    required=os.environ.get('ENERGY_REQUIRE_LOGIN','').lower() in ('1','true','yes')
    if raw is None:
        if required:raise ValueError('Login is required but the server account configuration is missing.')
        return None,None
    config=validate_config(json.loads(raw));digest=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    return config,digest

def clear_login():
    workspace=st.session_state.get('_demo_workspace')
    if workspace is not None:workspace.cleanup()
    for key in list(st.session_state):del st.session_state[key]

def demo_workspace(root):
    if '_demo_workspace' not in st.session_state:
        from storage import save_records,save_settings,save_appliances
        seed=json.loads((Path(root)/'assets/demo_household.json').read_text())
        workspace=tempfile.TemporaryDirectory(prefix='energy-demo-')
        st.session_state['_demo_workspace']=workspace
        folder=Path(workspace.name)
        save_records(folder,seed['records']);save_settings(folder,seed['settings']);save_appliances(folder,seed['appliances'])
    return Path(st.session_state['_demo_workspace'].name)

def gate_access(root,owner_data):
    try:config,digest=configured_accounts(root)
    except (ValueError,OSError,KeyError,TypeError):
        st.error('Sign-in is not configured correctly. Please contact the app owner.');st.stop()
    from app_design import brand
    if config is None:
        brand();return owner_data
    identity=st.session_state.get('_identity')
    if identity and (identity.get('config_digest')!=digest or identity.get('expires',0)<time.time()):
        clear_login();identity=None
    if not identity:
        st.markdown('<div class="hero"><div class="hero-kicker">WELCOME TO ENERGYWISE</div><h1>A little insight.<br>A lighter bill.</h1><p>Sign in to explore your electricity use and find smarter ways to save.</p></div>',unsafe_allow_html=True)
        left,right=st.columns([1,1])
        with left.container(border=True):
            st.subheader('Sign in')
            with st.form('sign_in',clear_on_submit=True):
                username=st.text_input('Username',max_chars=128)
                password=st.text_input('Password',type='password',max_chars=1024)
                submitted=st.form_submit_button('Sign in',type='primary')
            if submitted:
                principal,error=verifier().authenticate(config,username,password)
                if error:st.error(error)
                else:
                    st.session_state['_identity']=dict(principal,config_digest=digest,expires=time.time()+7200)
                    st.rerun()
        with right:
            st.info('Have an invitation? Use the username and password shared by the app owner.')
            st.caption('Demo visitors get their own temporary workspace. Your changes cannot alter the owner’s saved household data.')
        st.stop()
    brand()
    st.sidebar.caption('Signed in as '+identity['username'])
    if st.sidebar.button('Sign out',key='sign_out'):
        clear_login();st.rerun()
    if identity['role']=='demo':
        st.info('Demo workspace · Public dataset history and illustrative prices. Changes apply only to your session and are cleared when you sign out. These are not the owner’s bills or a live forecast for your home.')
        return demo_workspace(root)
    return owner_data
