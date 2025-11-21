from flask import Flask, render_template, redirect, url_for, request, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from io import BytesIO
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    username = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))


class Credit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(15))
    description = db.Column(db.String(255))
    amount = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class Debit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(15))
    description = db.Column(db.String(255))
    amount = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        password = request.form.get('password')

        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Username already exists. Please choose another.', 'error')
            return redirect(url_for('register'))

        new_user = User(name=name, username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        entry_type = request.form.get('entry_type')
        description = request.form.get('description')
        amount = request.form.get('amount')

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            flash('Amount must be a number.', 'error')
            return redirect(url_for('dashboard'))

        today = datetime.date.today().strftime('%d-%m-%Y')

        if entry_type == 'credit':
            credit = Credit(date=today, description=description, amount=amount, user_id=current_user.id)
            db.session.add(credit)
            db.session.commit()
            flash('Credit entry added!', 'success')
        elif entry_type == 'debit':
            debit = Debit(date=today, description=description, amount=amount, user_id=current_user.id)
            db.session.add(debit)
            db.session.commit()
            flash('Debit entry added!', 'success')

    credits = Credit.query.filter_by(user_id=current_user.id).all()
    debits = Debit.query.filter_by(user_id=current_user.id).all()

    total_credit = sum(c.amount for c in credits)
    total_debit = sum(d.amount for d in debits)
    available_amount = total_credit - total_debit

    user_obj = User.query.get(current_user.id)
    display_name = user_obj.name if user_obj and user_obj.name else current_user.username

    return render_template('dashboard.html', user=display_name, credits=credits, debits=debits,
                           total_credit=total_credit, total_debit=total_debit, available_amount=available_amount)

# Delete Credit
@app.route('/delete_credit/<int:credit_id>', methods=['POST'])
@login_required
def delete_credit(credit_id):
    credit = Credit.query.get_or_404(credit_id)
    db.session.delete(credit)
    db.session.commit()
    flash('Credit entry deleted!', 'success')
    return redirect(url_for('dashboard'))

# Delete Debit
@app.route('/delete_debit/<int:debit_id>', methods=['POST'])
@login_required
def delete_debit(debit_id):
    debit = Debit.query.get_or_404(debit_id)
    db.session.delete(debit)
    db.session.commit()
    flash('Debit entry deleted!', 'success')
    return redirect(url_for('dashboard'))

# Download as PDF
@app.route('/download_pdf')
@login_required
def download_pdf():
    credits = Credit.query.filter_by(user_id=current_user.id).all()
    debits = Debit.query.filter_by(user_id=current_user.id).all()
    user_obj = User.query.get(current_user.id)
    user_name = user_obj.name if user_obj else current_user.username

    buffer = BytesIO()
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle, Paragraph, SimpleDocTemplate, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=40, leftMargin=40, topMargin=60, bottomMargin=60)
    elements = []
    styles = getSampleStyleSheet()
    styleH = styles['Heading1']
    styleN = styles['Normal']
    style_signature = styles['Italic']

    # User Name as Title
    elements.append(Paragraph(f"User: {user_name}", styleH))
    elements.append(Spacer(1, 12))

    # Credit table data
    credit_data = [['Date', 'Description', 'Money']]
    for c in credits:
        credit_data.append([c.date, c.description, f"₹{c.amount}"])
    if len(credits) == 0:
        credit_data.append(['-', 'No credit entries', '-'])
    credit_table = Table(credit_data, colWidths=[70, 280, 80])
    credit_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgreen),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke)
    ]))
    elements.append(Paragraph("Credit Entries", styleN))
    elements.append(credit_table)
    elements.append(Spacer(1, 24))

    # Debit table data
    debit_data = [['Date', 'Description', 'Money']]
    for d in debits:
        debit_data.append([d.date, d.description, f"₹{d.amount}"])
    if len(debits) == 0:
        debit_data.append(['-', 'No debit entries', '-'])
    debit_table = Table(debit_data, colWidths=[70, 280, 80])
    debit_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.pink),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke)
    ]))
    elements.append(Paragraph("Debit Entries", styleN))
    elements.append(debit_table)

    # Signature for each page
    def addSignature(canvasDoc, doc):
        canvasDoc.saveState()
        canvasDoc.setFont('Helvetica-Oblique', 10)
        canvasDoc.setFillColorRGB(0.97, 0.75, 0.09)  # gold
        canvasDoc.drawString(40, 30, "@vaibhavprajapati")
        canvasDoc.restoreState()

    doc.build(elements, onLaterPages=addSignature, onFirstPage=addSignature)

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='finance_report.pdf', mimetype='application/pdf')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)