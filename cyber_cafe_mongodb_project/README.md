# Cyber Cafe Management System - MongoDB Version

## Folder structure
- backend/app.py
- backend/requirements.txt
- frontend/index.html
- frontend/config.js
- frontend/app.js
- frontend/style.css

## MongoDB Atlas choice
Choose **Connect to your application**.
Then select:
- Driver: Python
- Version: current recommended version

Copy the connection string and replace the username/password placeholders.

## Render deployment
Root Directory:
`backend`

Build Command:
`pip install -r requirements.txt`

Start Command:
`gunicorn app:app`

Environment variables:
`MONGODB_URI=mongodb+srv://USERNAME:PASSWORD@CLUSTER_URL/?retryWrites=true&w=majority`
`MONGODB_DB=cyber_cafe_db`

The backend automatically creates the database and collections when it first runs. It also inserts 10 terminals and one Standard rate if the collections are empty.

## Frontend
After the backend is deployed, copy the Render backend URL into:
`frontend/config.js`

Example:
`const API_BASE_URL = "https://your-service.onrender.com";`

Do not put MONGODB_URI in frontend files.
