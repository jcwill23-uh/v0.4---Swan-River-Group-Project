This is a basic proof of concept for an authentication system with role-based access control using Office365 for authentication.

To run this app locally, you will need to have a database set up on your local host via sqlite, as well as an account on Microsoft Azure. Once you have these, you will need to edit `app.py` as follows.

In the line that reads `app.config['SQLALCHEMY_DATABASE_URI'] = engine.url`, replace `engine.url` with `sqlite:///{your_database_name}.db`. Next, change `CLIENT_ID`, `CLIENT_SECRET`, and `TENANT_ID` to your own client ID, client secret, and tenant ID. All three of these can be found in your Microsoft Azure account. Lastly, change `REDIRECT_URI` to `localhost:{port}`.

Once these changes have been made, create a python virtual environment in this directory, activate it, install the requirements, and run `app.py`. The website should be active on your localhost.

Team Name: Swan River
