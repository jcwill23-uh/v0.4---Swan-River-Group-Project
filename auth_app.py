from flask import Flask, redirect, url_for, session
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = 'secret_key'  
oauth = OAuth(app)

azure = oauth.register(
    name='SwanRiver',
    client_id='e6265ffc-86da-4716-985b-a0df698c90b7',
    client_secret='2OG8Q~~FF3kcyJCd3fp4MQa67FIbcZEmelrV4bHH',  
    authorize_url='https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
    token_url='https://login.microsoftonline.com/common/oauth2/v2.0/token',
    userinfo_endpoint='https://graph.microsoft.com/oidc/userinfo',
    client_kwargs={
        'scope': 'openid profile email'
    }
)

@app.route('/')
def index():
    return 'Welcome to the Flask app'

@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return azure.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = azure.authorize_access_token()
    user_info = azure.parse_id_token(token)
    session['user'] = user_info
    return f'Hello, {user_info["name"]}!'

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run()

