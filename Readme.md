#Team Name: Swan River
#Flask OAuth with Microsoft365 and SQL Database Using Azure

##Website for this code: 
                                                                                                https://swan-river-group-project.azurewebsites.net/

This is a basic proof of concept for an authentication system with role-based access control using Office365 for authentication.

Easiest way to run this app:
  1. Download Docker Desktop: https://www.docker.com/products/docker-desktop/
  2. Open Docker Desktop app
  3. Download repository and open path in terminal
  4. Execute: docker build -t myapp .
  5. Execute: docker run -p 8000:8000 myapp
  6. Go to: http://localhost:8000

To run this app locally, you will need to have a database set up on your local host via sqlite, as well as an account on Microsoft Azure. Once you have these, you will need to edit `app.py` as follows:
                                                                                                Open a terminal (Command Prompt, PowerShell, or Git Bash on Windows; Terminal on macOS/Linux).
                                                                                                Run the git clone: `git clone https://github.com/jcwill23-uh/v0.4---Swan-River-Group-Project.git`
                                                                                                Go to directory: `cd Swan-River-Group-Project`
                                                                                                Create a Virtual Environment: `python -m venv venv`
                                                                                                Activate the Virtual Environment:
                                                                                                On Windows: `venv\Scripts\activate`
                                                                                                On macOS/Linux: `source venv/bin/activate`
                                                                                                Install dependencies: `pip install -r requirements.txt`
                                                                                                Run: `python app.py`

                                                                                                

In the line that reads `app.config['SQLALCHEMY_DATABASE_URI'] = engine.url`, replace `engine.url` with `sqlite:///{your_database_name}.db`. Next, change `CLIENT_ID`, `CLIENT_SECRET`, and `TENANT_ID` to your own client ID, client secret, and tenant ID. All three of these can be found in your Microsoft Azure account. Lastly, change `REDIRECT_URI` to `(http://localhost:8000)`.

Once these changes have been made, create a python virtual environment in this directory, activate it, install the requirements, and run `app.py`. The website should be active on your localhost.

For More Information about this repository go to: `UserManagement.md` file.

