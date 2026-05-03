# CF Checker

A Django-based Codeforces handle checker and visualization tool.

## Features
- Check Codeforces handles.
- View user statistics and problem-solving history.
- Responsive design for mobile and desktop.

## Local Development

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd cf-checker
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Run the development server:**
   ```bash
   python manage.py runserver
   ```

## Deployment on Render

This project is configured for easy deployment on [Render](https://render.com/).

### Steps to Deploy:

1.  **Create a new Web Service** on Render.
2.  **Connect your GitHub repository**.
3.  **Environment:** `Python 3`.
4.  **Build Command:** `./build.sh` (Ensure the file is executable: `chmod a+x build.sh`).
5.  **Start Command:** `gunicorn cf_checker_project.wsgi`
6.  **Add Environment Variables:**
    -   `SECRET_KEY`: A long, random string.
    -   `DEBUG`: `False`
    -   `ALLOWED_HOSTS`: Your Render domain (e.g., `cf-checker.onrender.com`).
    -   `DATABASE_URL`: (Optional) Your PostgreSQL database URL. If not provided, it will use SQLite (note: SQLite data is not persistent on Render's free tier unless using a Disk).

### Static Files
The project uses **WhiteNoise** to serve static files in production. `collectstatic` is automatically run during the build process via `build.sh`.

## License
MIT
