/**
 * Authentication module - Firebase-connected version
 */
var auth = (function () {
    "use strict";

    const SESSION_KEY = "pinevision_session";
    const REMEMBER_KEY = "pinevision_remember";

    // Firebase configuration
    const firebaseConfig = {
        apiKey: "AIzaSyBQT2B0OHvBeoDgEWGt9dnMfpeu_D1T34c",
        authDomain: "pinevision-632aa.firebaseapp.com",
        projectId: "pinevision-632aa",
        storageBucket: "pinevision-632aa.firebasestorage.app",
        messagingSenderId: "409081336673",
        appId: "1:409081336673:web:bf1ae3924437753f60eb20",
        measurementId: "G-QYX398ZYRZ"
    };

    // Initialize Firebase (only if not already initialized)
    if (!firebase.apps.length) {
        firebase.initializeApp(firebaseConfig);
    }

    const firebaseAuth = firebase.auth();
    const db = firebase.firestore();

    /**
     * Show error message in the UI
     */
    function showError(message) {
        const errorDiv = document.getElementById("error-message");
        const errorText = document.getElementById("error-text");
        if (errorDiv && errorText) {
            errorText.textContent = message;
            errorDiv.style.display = "flex";
            setTimeout(function () {
                errorDiv.style.display = "none";
            }, 5000);
        }
    }

    /**
     * Show loading state on login button
     */
    function setLoading(loading) {
        const btn = document.getElementById("login-btn");
        if (!btn) return;

        const btnText = btn.querySelector(".btn-text");
        const btnLoader = btn.querySelector(".btn-loader");

        if (loading) {
            btn.disabled = true;
            if (btnText) btnText.style.display = "none";
            if (btnLoader) btnLoader.style.display = "flex";
        } else {
            btn.disabled = false;
            if (btnText) btnText.style.display = "block";
            if (btnLoader) btnLoader.style.display = "none";
        }
    }

    /**
     * Save session data
     */
    function saveSession(user, remember) {
        const sessionData = {
            uid: user.uid,
            email: user.email,
            role: user.role,
            fullName: user.fullName,
            username: user.username,
            loginTime: new Date().toISOString(),
        };

        sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));

        if (remember) {
            localStorage.setItem(REMEMBER_KEY, JSON.stringify(sessionData));
        }
    }

    /**
     * Get current session
     */
    function getSession() {
        const session = sessionStorage.getItem(SESSION_KEY);
        if (session) return JSON.parse(session);

        const remembered = localStorage.getItem(REMEMBER_KEY);
        if (remembered) {
            const data = JSON.parse(remembered);
            sessionStorage.setItem(SESSION_KEY, remembered);
            return data;
        }

        return null;
    }

    /**
     * Check if user is logged in and redirect if on login page
     */
    function checkExistingSession() {
        const session = getSession();
        if (session && window.location.pathname.includes("index.html")) {
            redirectToDashboard(session.role);
        }
    }

    /**
     * Redirect to appropriate dashboard based on role
     */
    function redirectToDashboard(role) {
        if (role === "admin") {
            window.location.href = "/admin/dashboard.html";
        } else {
            window.location.href = "/client/dashboard.html";
        }
    }

    /**
     * Require authentication - redirect to login if not logged in
     */
    function requireAuth() {
        const session = getSession();
        if (!session) {
            window.location.href = "/index.html";
            return false;
        }
        return true;
    }

    /**
     * Require admin role - redirect if not admin
     */
    function requireAdmin() {
        if (!requireAuth()) return false;
        const session = getSession();
        if (session.role !== "admin") {
            window.location.href = "/client/dashboard.html";
            return false;
        }
        return true;
    }

    /**
     * Login function - connects to Firebase
     * Accepts username OR email
     */
    async function login(usernameOrEmail, password, remember) {
        setLoading(true);

        try {
            let email = usernameOrEmail;

            // Check if input is a username (no @ sign)
            if (usernameOrEmail.indexOf('@') === -1) {
                console.log('Username detected, looking up email...');

                const usersSnapshot = await db.collection('users')
                    .where('username', '==', usernameOrEmail)
                    .limit(1)
                    .get();

                if (usersSnapshot.empty) {
                    throw new Error('Invalid username or password');
                }

                const userData = usersSnapshot.docs[0].data();
                email = userData.email;
                console.log('Found email:', email);
            }

            // Now sign in with email and password
            const userCredential = await firebaseAuth.signInWithEmailAndPassword(email, password);
            const firebaseUser = userCredential.user;

            // Get user data from Firestore
            const userDoc = await db.collection("users").doc(firebaseUser.uid).get();

            if (!userDoc.exists) {
                throw new Error("User data not found in database");
            }

            const userData = userDoc.data();

            // Check if account is disabled
            if (userData.status === "disabled") {
                await firebaseAuth.signOut();
                throw new Error("Your account has been disabled. Please contact an administrator.");
            }

            // Update last login time in Firestore
            await db.collection("users").doc(firebaseUser.uid).update({
                lastLogin: firebase.firestore.FieldValue.serverTimestamp()
            });

            // Prepare user data for session
            const user = {
                uid: firebaseUser.uid,
                email: userData.email,
                fullName: userData.fullName,
                username: userData.username,
                role: userData.role,
                permissions: userData.permissions || []
            };

            // Save session
            saveSession(user, remember);

            // ⭐ LOG THE LOGIN ACTIVITY ⭐
            try {
                await db.collection('activity_logs').add({
                    userId: user.uid,
                    user: user.username,
                    action: 'login',
                    timestamp: firebase.firestore.FieldValue.serverTimestamp(),
                    status: 'success',
                    email: user.email,
                    role: user.role
                });
                console.log('✅ Login activity logged to Firestore');
            } catch (logError) {
                console.error('Failed to log activity:', logError);
            }

            // Redirect based on role
            setTimeout(function () {
                redirectToDashboard(user.role);
            }, 500);

        } catch (error) {
            setLoading(false);

            let userIP = 'unknown';
            try {
                const ipResponse = await fetch('https://api.ipify.org?format=json');
                const ipData = await ipResponse.json();
                userIP = ipData.ip;
            } catch (ipError) {
                console.log('Could not fetch IP');
            }

            // ⭐ LOG FAILED LOGIN ATTEMPT ⭐
            try {
                await db.collection('activity_logs').add({
                    user: usernameOrEmail,
                    action: 'login_failed',
                    timestamp: firebase.firestore.FieldValue.serverTimestamp(),
                    status: 'error',
                    email: usernameOrEmail,
                    role: 'unknown',
                    details: 'Failed login attempt — ' + (error.code || 'unknown'),
                    ip: userIP,
                    device: navigator.userAgent || 'Unknown device',
                    errorCode: error.code || 'unknown'
                });
                console.log('❌ Failed login attempt logged');
            } catch (logError) {
                console.error('Could not log failed attempt:', logError);
            }

            // ⭐ CREATE ALERT FOR FAILED LOGIN ⭐
            try {
                // Track failed attempts in sessionStorage (no Firestore read needed)
                var attemptKey = 'failed_attempts_' + usernameOrEmail;
                var attempts = parseInt(sessionStorage.getItem(attemptKey) || '0') + 1;
                sessionStorage.setItem(attemptKey, attempts);

                console.log('Failed attempts for ' + usernameOrEmail + ':', attempts);

                await db.collection('alerts').add({
                    alertId: 'alert_' + Date.now(),
                    severity: attempts >= 3 ? 'critical' : 'warning',
                    type: 'Failed Login',
                    title: attempts >= 3 ? 'Multiple Failed Login Attempts' : 'Failed Login Attempt',
                    user: usernameOrEmail,
                    ip: userIP,
                    timestamp: firebase.firestore.FieldValue.serverTimestamp(),
                    resolved: false,
                    details: attempts >= 3
                        ? attempts + ' failed login attempts detected'
                        : 'Invalid login credentials provided',
                    device: navigator.userAgent
                });

                console.log(attempts >= 3 ? '🚨 Critical alert created' : '⚠️ Warning alert created');
            } catch (alertError) {
                console.error('Failed to create alert:', alertError);
            }

            // Handle specific Firebase errors
            let errorMessage = "Login failed. Please try again.";

            if (error.code === "auth/user-not-found" ||
                error.code === "auth/wrong-password" ||
                error.code === "auth/invalid-login-credentials") {
                errorMessage = "Invalid username or password. Please try again.";
            } else if (error.code === "auth/too-many-requests") {
                errorMessage = "Too many failed attempts. Please try again later.";
            } else if (error.code === "auth/network-request-failed") {
                errorMessage = "Network error. Please check your connection";
            } else if (error.message) {
                errorMessage = error.message;
            }

            showError(errorMessage);
            console.error("Login error:", error);
        }
    }

    /**
     * Logout function
     */
    async function logout() {
        try {
            await firebaseAuth.signOut();
            sessionStorage.removeItem(SESSION_KEY);
            localStorage.removeItem(REMEMBER_KEY);
            window.location.href = "/index.html";
        } catch (error) {
            console.error("Logout error:", error);
            // Force logout even if Firebase fails
            sessionStorage.removeItem(SESSION_KEY);
            localStorage.removeItem(REMEMBER_KEY);
            window.location.href = "/index.html";
        }
    }

    /**
     * Get current user info
     */
    function getCurrentUser() {
        return getSession();
    }

    function confirmLogout() {
        if (confirm('Are you sure you want to logout?')) {
            logout();
        }
    }
    // Public API
    return {
        login: login,
        logout: logout,
        confirmLogout: confirmLogout,
        requireAuth: requireAuth,
        requireAdmin: requireAdmin,
        checkExistingSession: checkExistingSession,
        getCurrentUser: getCurrentUser,
        getSession: getSession,
        checkAuth: requireAuth,
    };
})();