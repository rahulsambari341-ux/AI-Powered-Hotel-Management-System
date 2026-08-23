// Deployment configuration for the customer voice UI.
//
// LOCAL DEV: leave as-is - matches the backend's default `uvicorn` port.
// PRODUCTION: change this to your deployed backend's real HTTPS URL,
// e.g. "https://api.yourhotel.com". This is the ONLY file that needs
// editing to point the frontend at a different backend - script.js reads
// this value instead of hardcoding a URL.
window.HOTEL_API_BASE = "http://localhost:8000";
