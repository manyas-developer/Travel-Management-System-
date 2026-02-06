from flask import Flask, render_template, request, redirect, url_for, flash, session
from db import get_connection
from functools import wraps
import plotly.graph_objects as go

app = Flask(__name__)
app.secret_key = "MTECH_PROJECT_SECRET_KEY"


# ============================================================
# SIMPLE EMAIL / SMS NOTIFIER (DUMMY FUNCTION)
# ============================================================
def send_payment_notification(to_email, amount, status, customer_name):
    print(f"[NOTIFICATION] Payment {status} | Amount={amount} | Customer={customer_name} | Email={to_email}")


# ============================================================
# LOGIN REQUIRED DECORATOR
# ============================================================
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            flash("Please login first.", "error")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


# ============================================================
# LOGIN
# ============================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form.get("username")
        pwd = request.form.get("password")

        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (uname, pwd))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session.clear()
            session["username"] = uname
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials.", "error")

    return render_template("login.html")


# ============================================================
# REGISTER
# ============================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        uname = request.form.get("username")
        pwd = request.form.get("password")

        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute("INSERT INTO users(username, password) VALUES (%s, %s)", (uname, pwd))
            conn.commit()
            flash("Registration successful!", "success")
            return redirect(url_for("login"))
        except Exception as e:
            conn.rollback()
            flash(str(e), "error")
        finally:
            cur.close()
            conn.close()

    return render_template("register.html")


# ============================================================
# LOGOUT
# ============================================================
@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))


# ============================================================
# DASHBOARD PAGE
# ============================================================
@app.route("/")
@login_required
def index():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # ---------- BASIC STATS ----------
    cur.execute("SELECT COUNT(*) AS cnt FROM Customer")
    cust_cnt = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) AS cnt FROM Destination")
    dest_cnt = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) AS cnt FROM Booking")
    booking_cnt = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) AS cnt FROM Payment")
    payment_cnt = cur.fetchone()["cnt"]

    cur.execute("SELECT SUM(amount) AS revenue FROM Payment WHERE status='SUCCESS'")
    revenue = cur.fetchone()["revenue"] or 0

    cur.execute("SELECT COUNT(*) AS pending FROM Payment WHERE status='PENDING'")
    pending_payments = cur.fetchone()["pending"]

    cur.execute("SELECT COUNT(*) AS today_bookings FROM Booking WHERE booking_date = CURDATE()")
    today_bookings = cur.fetchone()["today_bookings"]

    # ---------- MONTHLY REVENUE ----------
    cur.execute("""
        SELECT MONTH(pay_date) AS month, SUM(amount) AS total
        FROM Payment
        WHERE status='SUCCESS'
        GROUP BY MONTH(pay_date)
        ORDER BY month
    """)
    rev_rows = cur.fetchall()

    monthly_revenue = [0] * 12
    for r in rev_rows:
        monthly_revenue[r["month"] - 1] = float(r["total"])

    # ---------- MONTHLY BOOKINGS ----------
    cur.execute("""
        SELECT MONTH(booking_date) AS month, COUNT(*) AS total
        FROM Booking
        GROUP BY MONTH(booking_date)
        ORDER BY month
    """)
    book_rows = cur.fetchall()

    monthly_bookings = [0] * 12
    for r in book_rows:
        monthly_bookings[r["month"] - 1] = r["total"]

    # ---------- PIE CHART ----------
    cur.execute("""
        SELECT d.dest_name, COUNT(*) AS total
        FROM Booking b
        JOIN Destination d ON b.dest_id = d.dest_id
        GROUP BY d.dest_id
    """)
    pie_rows = cur.fetchall()

    pie_labels = [r["dest_name"] for r in pie_rows]
    pie_values = [r["total"] for r in pie_rows]

    cur.close()
    conn.close()

    return render_template(
        "index.html",
        cust_cnt=cust_cnt,
        dest_cnt=dest_cnt,
        booking_cnt=booking_cnt,
        payment_cnt=payment_cnt,
        revenue=revenue,
        pending_payments=pending_payments,
        today_bookings=today_bookings,
        monthly_revenue=monthly_revenue,
        monthly_bookings=monthly_bookings,
        pie_labels=pie_labels,
        pie_values=pie_values
    )


# ============================================================
# CUSTOMERS CRUD (FULLY FIXED)
# ============================================================
@app.route("/customers")
@login_required
def customers():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM Customer ORDER BY cust_id")
    customers = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("customers.html", customers=customers)


# ----- SHOW ADD CUSTOMER FORM (GET) -----
@app.route("/customers/add", methods=["GET"])
@login_required
def show_add_customer_form():
    return render_template("customer_form.html", action="Add", customer=None)


# ----- ADD CUSTOMER (POST) -----
@app.route("/customers/add", methods=["POST"])
@login_required
def add_customer():
    name = request.form["cust_name"]
    email = request.form["email"]
    city = request.form["city"]

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO Customer(cust_name, email, city) VALUES (%s, %s, %s)",
                    (name, email, city))
        conn.commit()
        flash("Customer added!", "success")
    except Exception as e:
        conn.rollback()
        flash(str(e), "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("customers"))


# ----- EDIT CUSTOMER -----
@app.route("/customers/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_customer(id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["cust_name"]
        email = request.form["email"]
        city = request.form["city"]

        try:
            cur.execute("""
                UPDATE Customer
                SET cust_name=%s, email=%s, city=%s
                WHERE cust_id=%s
            """, (name, email, city, id))
            conn.commit()
            flash("Customer updated!", "success")
        except Exception as e:
            conn.rollback()
            flash(str(e), "error")
        finally:
            cur.close()
            conn.close()

        return redirect(url_for("customers"))

    cur.execute("SELECT * FROM Customer WHERE cust_id=%s", (id,))
    customer = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("customer_form.html", action="Edit", customer=customer)


# ----- DELETE CUSTOMER -----
@app.route("/customers/delete/<int:id>")
@login_required
def delete_customer(id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            DELETE p FROM Payment p
            JOIN Booking b ON p.booking_id=b.booking_id
            WHERE b.cust_id=%s
        """, (id,))

        cur.execute("DELETE FROM Booking WHERE cust_id=%s", (id,))
        cur.execute("DELETE FROM Customer WHERE cust_id=%s", (id,))

        conn.commit()
        flash("Customer deleted!", "success")
    except Exception as e:
        conn.rollback()
        flash(str(e), "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("customers"))


# ============================================================
# DESTINATIONS CRUD
# ============================================================
@app.route("/destinations")
@login_required
def destinations():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM Destination ORDER BY dest_id")
    destinations = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("destinations.html", destinations=destinations)


@app.route("/destinations/add", methods=["GET", "POST"])
@login_required
def add_destination():
    if request.method == "POST":
        name = request.form["dest_name"]
        country = request.form["country"]
        price = request.form["base_price"]
        season = request.form["season"]

        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO Destination (dest_name, country, base_price, season)
                VALUES (%s, %s, %s, %s)
            """, (name, country, price, season))
            conn.commit()
            flash("Destination added!", "success")
            return redirect(url_for("destinations"))
        except Exception as e:
            conn.rollback()
            flash(str(e), "error")
        finally:
            cur.close()
            conn.close()

    return render_template("destination_form.html", action="Add", dest=None)


@app.route("/destinations/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_destination(id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["dest_name"]
        country = request.form["country"]
        price = request.form["base_price"]
        season = request.form["season"]

        try:
            cur.execute("""
                UPDATE Destination
                SET dest_name=%s, country=%s, base_price=%s, season=%s
                WHERE dest_id=%s
            """, (name, country, price, season, id))
            conn.commit()
            flash("Destination updated!", "success")
            return redirect(url_for("destinations"))
        except Exception as e:
            conn.rollback()
            flash(str(e), "error")
        finally:
            cur.close()
            conn.close()

    cur.execute("SELECT * FROM Destination WHERE dest_id=%s", (id,))
    dest = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("destination_form.html", action="Edit", dest=dest)


@app.route("/destinations/delete/<int:id>")
@login_required
def delete_destination(id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            DELETE p FROM Payment p
            JOIN Booking b ON p.booking_id=b.booking_id
            WHERE b.dest_id=%s
        """, (id,))

        cur.execute("DELETE FROM Booking WHERE dest_id=%s", (id,))
        cur.execute("DELETE FROM Destination WHERE dest_id=%s", (id,))

        conn.commit()
        flash("Destination deleted!", "success")
    except Exception as e:
        conn.rollback()
        flash(str(e), "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("destinations"))


# ============================================================
# BOOKINGS
# ============================================================
@app.route("/bookings")
@login_required
def bookings():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            b.booking_id,
            b.booking_date,
            b.num_persons,
            c.cust_name,
            d.dest_name,
            (b.num_persons * d.base_price) AS final_price,
            CASE
                WHEN SUM(p.status='SUCCESS') > 0 THEN 'PAID'
                WHEN SUM(p.status='PENDING') > 0 THEN 'PENDING'
                ELSE 'NOT PAID'
            END AS payment_status
        FROM Booking b
        JOIN Customer c ON b.cust_id=c.cust_id
        JOIN Destination d ON b.dest_id=d.dest_id
        LEFT JOIN Payment p ON b.booking_id=p.booking_id
        GROUP BY b.booking_id
        ORDER BY b.booking_id
    """)
    booking_rows = cur.fetchall()

    cur.execute("SELECT cust_id, cust_name FROM Customer")
    customers = cur.fetchall()

    cur.execute("SELECT dest_id, dest_name FROM Destination")
    destinations = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "bookings.html",
        bookings=booking_rows,
        customers=customers,
        destinations=destinations
    )


@app.route("/bookings/add", methods=["POST"])
@login_required
def add_booking():
    cust_id = request.form["cust_id"]
    dest_id = request.form["dest_id"]
    bdate = request.form["booking_date"]
    persons = request.form["num_persons"]

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO Booking(cust_id, dest_id, booking_date, num_persons, payment_status)
            VALUES (%s, %s, %s, %s, 'NOT PAID')
        """, (cust_id, dest_id, bdate, persons))
        conn.commit()
        flash("Booking created!", "success")
    except Exception as e:
        conn.rollback()
        flash(str(e), "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("bookings"))


@app.route("/bookings/delete/<int:id>")
@login_required
def delete_booking(id):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM Payment WHERE booking_id=%s", (id,))
        cur.execute("DELETE FROM Booking WHERE booking_id=%s", (id,))
        conn.commit()
        flash("Booking deleted!", "success")
    except Exception as e:
        conn.rollback()
        flash(str(e), "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("bookings"))


# ============================================================
# PAYMENTS
# ============================================================
@app.route("/payments")
@login_required
def payments():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT p.*, c.cust_name, b.num_persons, d.base_price
        FROM Payment p
        JOIN Booking b ON p.booking_id=b.booking_id
        JOIN Customer c ON b.cust_id=c.cust_id
        JOIN Destination d ON b.dest_id=d.dest_id
        ORDER BY p.pay_id
    """)
    payments = cur.fetchall()

    cur.execute("""
        SELECT 
            b.booking_id,
            b.num_persons,
            d.base_price,
            (b.num_persons * d.base_price) AS final_price
        FROM Booking b
        JOIN Destination d ON b.dest_id=d.dest_id
    """)
    bookings_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("payments.html", payments=payments, bookings=bookings_list)


@app.route("/payments/add", methods=["POST"])
@login_required
def add_payment():
    booking_id = request.form["booking_id"]
    amount = request.form["amount"]
    mode = request.form["pay_mode"]
    status = request.form["status"]

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("SELECT * FROM Payment WHERE booking_id=%s AND status='SUCCESS'", (booking_id,))
        exists = cur.fetchone()

        if exists and status == "SUCCESS":
            flash("This booking is already fully paid!", "error")
            return redirect(url_for("payments"))

        cur.execute("""
            INSERT INTO Payment (booking_id, amount, pay_mode, status)
            VALUES (%s, %s, %s, %s)
        """, (booking_id, amount, mode, status))

        new_status = "PAID" if status == "SUCCESS" else "PENDING" if status == "PENDING" else "NOT PAID"

        cur.execute("UPDATE Booking SET payment_status=%s WHERE booking_id=%s", (new_status, booking_id))

        if status == "SUCCESS":
            cur.execute("""
                SELECT c.cust_name, c.email 
                FROM Booking b 
                JOIN Customer c ON b.cust_id=c.cust_id
                WHERE b.booking_id=%s
            """, (booking_id,))
            cust = cur.fetchone()
            send_payment_notification(cust["email"], amount, status, cust["cust_name"])

        conn.commit()
        flash("Payment recorded successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(str(e), "error")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("payments"))


@app.route("/payments/delete/<int:id>")
@login_required
def delete_payment(id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("SELECT booking_id FROM Payment WHERE pay_id=%s", (id,))
        row = cur.fetchone()
        booking_id = row["booking_id"] if row else None

        cur.execute("DELETE FROM Payment WHERE pay_id=%s", (id,))

        if booking_id:
            cur.execute("""
                SELECT SUM(status='SUCCESS') AS paid, SUM(status='PENDING') AS pending
                FROM Payment
                WHERE booking_id=%s
            """, (booking_id,))
            status_row = cur.fetchone()

            if status_row["paid"] > 0:
                new_status = "PAID"
            elif status_row["pending"] > 0:
                new_status = "PENDING"
            else:
                new_status = "NOT PAID"

            cur.execute("UPDATE Booking SET payment_status=%s WHERE booking_id=%s", (new_status, booking_id))

        conn.commit()
        flash("Payment deleted!", "success")

    except Exception as e:
        conn.rollback()
        flash(str(e), "error")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("payments"))


# ============================================================
# RECEIPT PAGE
# ============================================================
@app.route("/receipt/<int:booking_id>")
@login_required
def booking_receipt(booking_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            b.booking_id, b.booking_date, b.num_persons, b.payment_status,
            c.cust_name, c.email, c.city,
            d.dest_name, d.country, d.base_price
        FROM Booking b
        JOIN Customer c ON b.cust_id=c.cust_id
        JOIN Destination d ON b.dest_id=d.dest_id
        WHERE b.booking_id=%s
    """, (booking_id,))
    booking = cur.fetchone()

    if not booking:
        flash("Booking not found.", "error")
        return redirect(url_for("bookings"))

    cur.execute("""
        SELECT pay_id, amount, pay_mode, status, pay_date
        FROM Payment
        WHERE booking_id=%s
        ORDER BY pay_id
    """, (booking_id,))
    payments = cur.fetchall()

    cur.close()
    conn.close()

    final_price = booking["num_persons"] * float(booking["base_price"])
    paid_amount = sum(float(p["amount"]) for p in payments if p["status"] == "SUCCESS")
    pending_amount = final_price - paid_amount

    return render_template(
        "receipt.html",
        booking=booking,
        payments=payments,
        final_price=final_price,
        paid_amount=paid_amount,
        pending_amount=pending_amount
    )


# ============================================================
# REPORTS PAGE
# ============================================================
@app.route("/reports")
@login_required
def reports():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT d.dest_name, SUM(p.amount) AS total_revenue
        FROM Payment p
        JOIN Booking b ON p.booking_id = b.booking_id
        JOIN Destination d ON b.dest_id = d.dest_id
        WHERE p.status = 'SUCCESS'
        GROUP BY d.dest_id
    """)
    revenue = cur.fetchall()

    cur.execute("""
        SELECT d.dest_name, COUNT(*) AS total_bookings
        FROM Booking b
        JOIN Destination d ON b.dest_id = d.dest_id
        GROUP BY d.dest_id
    """)
    most_booked = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "reports.html",
        reports={
            "revenue": revenue,
            "most_booked": most_booked
        }
    )


# ============================================================
# RUN APP
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)
