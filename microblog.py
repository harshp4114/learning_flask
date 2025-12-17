from app.models import User , Post
from app import db,cli,create_app

app=create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db':db,'User':User,'Post':Post}