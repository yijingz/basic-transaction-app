import datetime
from flask import Flask, request, render_template_string, render_template, redirect, url_for, flash
from flask_babelex import Babel
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref
from flask_user import current_user, login_required, roles_required, UserManager, UserMixin


# Class-based application configuration
class ConfigClass(object):
    """ Flask application config """

    # Flask settings
    SECRET_KEY = 'This is an INSECURE secret!! DO NOT use this in production!!'

    # Flask-SQLAlchemy settings
    SQLALCHEMY_DATABASE_URI = 'sqlite:///basic_app.sqlite'  # File-based SQL database
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Avoids SQLAlchemy warning

    # Flask-User settings
    USER_APP_NAME = "Flask-Simple Transaction Request Management"
    USER_ENABLE_EMAIL = False  # Enable email authentication
    USER_ENABLE_USERNAME = True  # Disable username authentication

def create_app():
    """ Flask application factory """

    # Create Flask app load app.config
    app = Flask(__name__)
    app.config.from_object(__name__ + '.ConfigClass')

    # Initialize Flask-BabelEx
    babel = Babel(app)

    # Initialize Flask-SQLAlchemy
    db = SQLAlchemy(app)

    # Define the User data-model.
    # NB: Make sure to add flask_user UserMixin !!!
    class User(db.Model, UserMixin):
        __tablename__ = 'users'
        id = db.Column(db.Integer, primary_key=True)
        active = db.Column('is_active', db.Boolean(), nullable=False, server_default='1')


        # User authentication information. The collation='NOCASE' is required
        # to search case insensitively when USER_IFIND_MODE is 'nocase_collation'.
        username = db.Column(db.String(255, collation='NOCASE'), nullable=False, unique=True)
        password = db.Column(db.String(255), nullable=False, server_default='')

        # Define the relationship to Role via UserRoles
        roles = db.relationship('Role', secondary='user_roles')
        transactions = db.relationship('Transactions', backref=backref('users', uselist=False))

    # Define the Role data-model
    class Role(db.Model):
        __tablename__ = 'roles'
        id = db.Column(db.Integer(), primary_key=True)
        name = db.Column(db.String(50), unique=True)

    # Define the UserRoles association table
    class UserRoles(db.Model):
        __tablename__ = 'user_roles'
        id = db.Column(db.Integer(), primary_key=True)
        user_id = db.Column(db.Integer(), db.ForeignKey('users.id', ondelete='CASCADE'))
        role_id = db.Column(db.Integer(), db.ForeignKey('roles.id', ondelete='CASCADE'))


    class Transactions(db.Model):
        __tablename__ = 'transactions'
        id = db.Column(db.Integer(), primary_key=True)
        company = db.Column(db.String(100, collation='NOCASE'), nullable=False, server_default='')
        amount = db.Column(db.Integer())
        status = db.Column(db.Integer())
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


    # Setup Flask-User and specify the User data-model
    user_manager = UserManager(app, db, User)

    # Create all database tables
    db.create_all()

    # Create 'user' user with no roles
    if not User.query.filter(User.username == 'user').first():
        user = User(
            username='user',
            password=user_manager.hash_password('Password1'),
        )

        user.transactions.append(Transactions(company='Apple', amount=10, status=0))
        user.transactions.append(Transactions(company='Apple', amount=20, status=0))
        db.session.add(user)
        db.session.commit()

    # Create 'admin' user with 'Admin' role
    if not User.query.filter(User.username == 'admin').first():
        user = User(
            username='admin',
            password=user_manager.hash_password('admin'),
        )
        user.roles.append(Role(name='Admin'))
        db.session.add(user)
        db.session.commit()

    if not User.query.filter(User.username == 'comp').first():
        user = User(
            username='comp',
            password=user_manager.hash_password('comp'),
        )
        user.roles.append(Role(name='Compliance'))
        db.session.add(user)
        db.session.commit()

    if not User.query.filter(User.username == 'user_test').first():
        user = User(
            username='user_test',
            password=user_manager.hash_password('user_test'),
        )
        user.roles.append(Role(name='User'))
        db.session.add(user)
        db.session.commit()

    # The Home page is accessible to anyone
    @app.route('/')
    def home_page():

        return render_template('home_page.html')

    @app.route('/user')
    @roles_required('User')
    def user_page():
        user_id = current_user.id
        lst = Transactions.query.filter(Transactions.status == 0).all()
        x = [i.user_id for i in lst]


        pending = Transactions.query.filter(Transactions.user_id == user_id, Transactions.status == 0).all()
        approved = Transactions.query.filter(Transactions.user_id == user_id, Transactions.status == 1).all()
        rejected = Transactions.query.filter(Transactions.user_id == user_id, Transactions.status == 2).all()


        return render_template('user_page.html', pending=pending, approved=approved, rejected=rejected)

    @app.route('/add_trans', methods=['POST'])
    def add_trans():
        company = request.form['company']
        num_shares = request.form['num_shares']

        user = User.query.filter(User.id == current_user.id).first()
        user.transactions.append(Transactions(company=company, amount=num_shares, status=0))
        db.session.commit()

        flash("Transaction Submitted!")

        return redirect(url_for('user_page'))




    # The Members page is only accessible to authenticated users
    @app.route('/compliance')
    @roles_required('Compliance')
    def member_page():
        pending = Transactions.query.filter(Transactions.status == 0).all()
        approved = Transactions.query.filter(Transactions.status == 1).all()
        rejected = Transactions.query.filter(Transactions.status == 2).all()

        return render_template('compliance_page.html', pending=pending, approved=approved, rejected=rejected)

    @app.route('/reject_trans', methods=['POST'])
    def reject_trans():
        trans_id = request.form['trans_id']
        decision = 1 if request.form['submit_button'] == "Approve" else 2

        trans = Transactions.query.filter(Transactions.id == trans_id).first()
        trans.status = decision
        db.session.commit()

        pending = Transactions.query.filter(Transactions.status == 0).all()
        approved = Transactions.query.filter(Transactions.status == 1).all()
        rejected = Transactions.query.filter(Transactions.status == 2).all()

        return render_template('compliance_page.html', pending=pending, approved=approved, rejected=rejected)

    # The Admin page requires an 'Admin' role.
    @app.route('/admin')
    @roles_required('Admin')  # Use of @roles_required decorator
    def admin_page():
        return render_template('admin_page.html')

    @app.route('/add_new', methods=['POST'])
    def add_new():
        role = request.form['role']
        username = request.form['username']
        password = request.form['password']


        if not User.query.filter(User.username == username).first():
            user = User(
                username=username,
                password=user_manager.hash_password(password),
            )
            stored_role = Role.query.filter(Role.name == role).first()

            user.roles.append(stored_role)
            db.session.add(user)
            db.session.commit()
            return render_template_string(role)
        else:
            return render_template_string('user exists')
    return app


# Start development web server
if __name__ == '__main__':
    app = create_app()
    app.run()