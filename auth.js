const msalConfig = {
    auth: {
        clientId: '7d3a3c1c-46ec-4247-9ed4-ef0d1526c5b9', // Replace with your Azure AD client ID
        authority: 'https://login.microsoftonline.com/organizations', // Use 'common' for multi-tenant
        redirectUri: 'https://jcwill23-uh.github.io/Swan-River-Group-Project/login.html', // Redirect URI
    },
    cache: {
        cacheLocation: 'localStorage', // Store tokens in localStorage
        storeAuthStateInCookie: false,
    },
};

const msalInstance = new msal.PublicClientApplication(msalConfig);

async function login() {
    try {
        const loginResponse = await msalInstance.loginPopup({
            scopes: ['User.Read'], // Add required scopes
        });
        // Save the authentication state
        localStorage.setItem('isLoggedIn', 'true');
        localStorage.setItem('userName', loginResponse.account.name);
        // Redirect to admin page
        window.location.href = 'admin.html';
    } catch (error) {
        console.error('Login failed:', error);
    }
}

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('service-worker.js')
        .then(registration => {
            console.log('Service Worker registered with scope:', registration.scope);
        })
        .catch(error => {
            console.error('Service Worker registration failed:', error);
        });
}

// auth.js
function checkAuth() {
    const isLoggedIn = localStorage.getItem('isLoggedIn');
    console.log('checkAuth called, isLoggedIn:', isLoggedIn);

    if (!isLoggedIn) {
        console.log('Not logged in, redirecting to index.html');
        window.location.href = 'index.html';
    }
}


