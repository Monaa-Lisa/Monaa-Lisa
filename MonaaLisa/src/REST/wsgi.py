from app import spawn

# Schnittstelle für gunicorn, ermöglicht verteilung von Requests auf mehrere Worker

app = spawn()

if __name__ == "__main__":
    app.run()
