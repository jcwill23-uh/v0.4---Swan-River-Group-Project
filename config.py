import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Azure AD Configuration
class Config:
  CLIENT_ID = "7fbeba40-e221-4797-8f8a-dc364de519c7"
  CLIENT_SECRET = "x2T8Q~yVzAOoC~r6FYtzK6sqCJQR_~RCVH5-dcw8"
  TENANT_ID = "170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259"
  AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
  REDIRECT_URI = "https://swan-river-group-project.azurewebsites.net/auth/callback"
  SCOPE = ['User.Read']
  
