from flask import Flask, redirect, url_for, session, request, render_template
from flask_oauthlib.client import OAuth
from functools import wraps

app = Flask(__name__)
app.secret_key = 'swanRiver'  # Replace with a strong, random secret key

oauth = OAuth(app)
azure = oauth.remote_app(
    'azure',
    consumer_key='7d3a3c1c-46ec-4247-9ed4-ef0d1526c5b9',  # Replace with your Application (client) ID
    consumer_secret='1pF8Q~cPp9z-i_1N3gkeN4FN4t3gT9_7fcl-Tcek',  # Replace with your Client Secret
    request_token_params={
        'scope': 'User.Read'
    },
    base_url='https://graph.microsoft.com/v1.0/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://login.microsoftonline.com/170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259/oauth2/token',  # Replace {tenant_id} with your Directory (tenant) ID
    authorize_url='https://login.microsoftonline.com/170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259/oauth2/v2.0/authorize'  # Replace {tenant_id} with your Directory (tenant) ID
)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'azure_token' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'azure_token' in session:
        return redirect(url_for('admin'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/login/authorize')
def login_authorize():
    return azure.authorize(callback=url_for('authorized', _external=True))

@app.route('/logout')
def logout():
    session.pop('azure_token', None)
    return redirect(url_for('index'))

@app.route('/authorized')
@azure.authorized_handler
def authorized(resp):
    if resp is None or 'access_token' not in resp:
        return redirect(url_for('login'))
    session['azure_token'] = resp['access_token']
    return redirect('https://jcwill23-uh.github.io/Swan-River-Group-Project/admin.html')

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')

@azure.tokengetter
def get_azure_token():
    return session.get('azure_token')

if __name__ == '__main__':
    app.run(debug=True)
