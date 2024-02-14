"""An entrypoint to application startup."""

from geneweaver.aon.factory import create_app

if __name__ == "__main__":
    app = create_app()
    app.run()
