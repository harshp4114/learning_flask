from flask import render_template
from app import app

@app.route('/')
@app.route('/index')
def index():
    user={"username":"John Doe"}
    posts=[{'author':'John','body':'I love eating apples.'},{'author':'Sarah','body':'The Avengers movie was so cool!'}]
    return render_template("index.html",title="Home",user=user,posts=posts)