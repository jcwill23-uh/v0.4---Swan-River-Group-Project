// auth.js

// MSAL Configuration
const msalConfig = {
    auth: {
        clientId: '7d3a3c1c-46ec-4247-9ed4-ef0d1526c5b9', // Replace with your Azure AD client ID
        authority: 'https://login.microsoftonline.com/organizations', // Use 'common' for multi-tenant
        redirectUri: 'https://jcwill23-uh.github.io/Swan-River-Group-Project/login.html', // Redirect URI
    },
    cache: {
        cacheLocation: 'sessionStorage', // Store tokens in sessionStorage
        storeAuthStateInCookie: false,
    },
};

// Initialize MSAL instance
const msalInstance = new msal.PublicClientApplication(msalConfig);

// Function to handle login
async function login() {
    try {
        const loginResponse = await msalInstance.loginPopup({
            scopes: ['User.Read'], // Add required scopes
        });
        // Save the authentication state in sessionStorage
        sessionStorage.setItem('isLoggedIn', 'true');
        sessionStorage.setItem('userName', loginResponse.account.name);
        // Redirect to admin page
        window.location.href = 'admin.html';
    } catch (error) {
        console.error('Login failed:', error);
    }
}

// Function to check authentication status
function checkAuth() {
    const isLoggedIn = sessionStorage.getItem('isLoggedIn');
    console.log('checkAuth called, isLoggedIn:', isLoggedIn);

    if (!isLoggedIn) {
        console.log('Not logged in, redirecting to index.html');
        window.location.href = 'index.html';
    }
}

// Function to log out
function logout() {
    msalInstance.logoutPopup()
        .then(() => {
            sessionStorage.removeItem('isLoggedIn');
            sessionStorage.removeItem('userName');
            window.location.href = 'index.html';
        })
        .catch(error => {
            console.error('Logout failed:', error);
        });
}


