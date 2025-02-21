The website is hosted on Microsoft Azure and uses Office 365 authentication via Microsoft Graph API. Upon login, users are assigned a role as either admin or basic user.

Authentication & User Roles
  - Office 365 Login: Users authenticate using their Microsoft credentials.
  - Role Assignment:
      Admins: Have full user management privileges.
      Basic Users: Have limited access with no administrative controls.

Admin Functionalities
  - Admins have access to a user management dashboard where they can:
    
  - View all logged-in users, including their status (active/inactive).
  - Change user status (activate or deactivate accounts).
  - Delete users, ensuring they cannot log back in.
  - Promote basic users to admin roles.



