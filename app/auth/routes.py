from flask import render_template, redirect, url_for, flash, request
from urllib.parse import urlparse as url_parse
from flask_login import current_user, login_user, logout_user, login_required
from app.auth import bp
from app import db
from app.models import Business, User
from app.forms import LoginForm, RegistrationForm


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if request.method == 'POST':
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if request.method == 'POST':
        # basic checks
        if form.password.data != form.password2.data:
            flash('Passwords do not match')
            return render_template('register.html', title='Register', form=form)
        if User.query.filter_by(username=form.username.data).first() or User.query.filter_by(email=form.email.data).first():
            flash('User or email already exists')
            return render_template('register.html', title='Register', form=form)
        if Business.query.filter_by(whatsapp_number=form.whatsapp_number.data).first():
            flash('WhatsApp number already exists')
            return render_template('register.html', title='Register', form=form)
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        business = Business(
            owner=user,
            name=form.business_name.data,
            whatsapp_number=form.whatsapp_number.data,
            city=form.city.data,
            country=form.country.data,
        )
        db.session.add(user)
        db.session.add(business)
        db.session.commit()
        flash('registered user')
        return redirect(url_for('auth.login'))
    return render_template('register.html', title='Register', form=form)
