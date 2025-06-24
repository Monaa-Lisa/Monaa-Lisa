from app import spawn

# Interface for gunicorn, handles splitting work of requests on multiple workers

app = spawn()

if __name__ == "__main__":
    app.run()
